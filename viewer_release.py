import sys
import os
import numpy as np
import pydicom
from PIL import Image

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QSlider, QLineEdit, QFileDialog, QTextEdit,
    QMenuBar, QMenu, QMessageBox, QSizePolicy, QComboBox, QDialog, QGridLayout,
    QStackedWidget
)
from PySide6.QtCore import Qt, Signal, QSize, QRectF
from PySide6.QtGui import QPixmap, QImage, QPainter, QMouseEvent, QWheelEvent, QFont, QColor

# --- 1. 定数・ヘルパー関数 ---
NON_COMPRESSED_UIDS = {'1.2.840.1.2', '1.2.840.1.2.1'}

def numpy_to_qimage(array_255: np.ndarray) -> QImage:
    if array_255.dtype != np.uint8:
        array_255 = array_255.astype(np.uint8)
        
    height, width = array_255.shape
    qimage = QImage(array_255.data, width, height, width, QImage.Format_Grayscale8)
    return qimage


# --- 2. カスタム画像表示ウィジェット（W/L, ズーム, パン, 参照線対応） ---
class ImageDisplayWidget(QLabel):
    wwl_changed = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.OpenHandCursor)
        self.setSizePolicy(
            QSizePolicy.Expanding, 
            QSizePolicy.Expanding
        )
        
        self.img_data_255 = None
        self.image_size = (0, 0)
        self.slice_info = "" 
        
        self.current_slice_indices = None
        self.current_plane = "Axial"
        self._is_mpr_view = False
        
        self.ww, self.wl = 400.0, 40.0
        self._last_mouse_pos = None

        self.zoom_factor = 1.0
        self.pan_x, self.pan_y = 0, 0
        
        self.setMouseTracking(True)
        
    def set_image_data(self, data_255: np.ndarray, ww, wl, slice_info="", indices=None, plane=None, is_mpr=False):
        self.img_data_255 = data_255
        self.ww, self.wl = ww, wl
        self.slice_info = slice_info
        self.image_size = data_255.shape[::-1]
        
        self.current_slice_indices = indices
        self.current_plane = plane if plane else "Axial"
        self._is_mpr_view = is_mpr
        
        self.update()

    def paintEvent(self, event):
        if self.img_data_255 is None:
            super().paintEvent(event)
            return

        painter = QPainter(self)
        try:
            rect = self.contentsRect()
            
            qimage = numpy_to_qimage(self.img_data_255)
            
            img_w, img_h = self.image_size
            scale = min(rect.width() / img_w, rect.height() / img_h) if img_w > 0 and img_h > 0 else 1.0
            
            new_w = int(img_w * scale * self.zoom_factor)
            new_h = int(img_h * scale * self.zoom_factor)
            
            paste_x = (rect.width() - new_w) // 2 + self.pan_x
            paste_y = (rect.height() - new_h) // 2 + self.pan_y
            
            # 1. 画像の描画
            pixmap = QPixmap.fromImage(qimage.scaled(new_w, new_h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            painter.drawPixmap(paste_x, paste_y, pixmap)
            
            # 2. 参照線とスライス情報の描画
            is_mpr_view = self._is_mpr_view
            
            # ★★★ 修正ロジック ★★★
            view_container = self.parent() # ViewContainer (QWidget)
            if view_container:
                 mpr_widget = view_container.parent() # MPRViewWidgetを取得
            else:
                 mpr_widget = None

            hu_data = None
            if mpr_widget and hasattr(mpr_widget, 'all_slices_hu'):
                 hu_data = mpr_widget.all_slices_hu

            # 参照線描画の条件チェック (強制表示)
            if is_mpr_view and self.current_slice_indices is not None and self.image_size != (0, 0) and hu_data is not None:
                
                painter.setRenderHint(QPainter.Antialiasing)
                img_rect = QRectF(paste_x, paste_y, new_w, new_h)
                z, y, x = self.current_slice_indices
                max_z, max_y, max_x = hu_data.shape

                # 参照線
                painter.setPen(QColor(255, 0, 0))
                
                if self.current_plane == "Axial":
                    y_pos = img_rect.top() + (y / max_y) * img_rect.height()
                    x_pos = img_rect.left() + (x / max_x) * img_rect.width()
                    painter.drawLine(img_rect.left(), y_pos, img_rect.right(), y_pos)
                    painter.drawLine(x_pos, img_rect.top(), x_pos, img_rect.bottom())
                elif self.current_plane == "Coronal":
                    z_pos = img_rect.top() + (z / max_z) * img_rect.height()
                    x_pos = img_rect.left() + (x / max_x) * img_rect.width()
                    painter.drawLine(img_rect.left(), z_pos, img_rect.right(), z_pos)
                    painter.drawLine(x_pos, img_rect.top(), x_pos, img_rect.bottom())
                elif self.current_plane == "Sagittal":
                    z_pos = img_rect.top() + (z / max_z) * img_rect.height()
                    y_pos = img_rect.left() + (y / max_y) * img_rect.width()
                    painter.drawLine(img_rect.left(), z_pos, img_rect.right(), z_pos)
                    painter.drawLine(y_pos, img_rect.top(), y_pos, img_rect.bottom())

            # スライス情報テキスト (左下)
            if self.slice_info:
                painter.setPen(QColor(255, 255, 0))
                font = QFont("Arial", 16, QFont.Bold)
                painter.setFont(font)
                text_x = paste_x + 10
                text_y = paste_y + new_h - 10
                painter.drawText(text_x, text_y, self.slice_info)

        finally:
            painter.end()

    # --- マウス操作 (MPRパネル内でのW/L調整を可能にするため、ここではイベントを処理) ---
    def mousePressEvent(self, event: QMouseEvent):
        self._last_mouse_pos = event.pos()
        
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.ClosedHandCursor)
        elif event.button() == Qt.RightButton:
            self.setCursor(Qt.SizeAllCursor)
                
    def mouseMoveEvent(self, event: QMouseEvent):
        if self._last_mouse_pos is None: return

        dx = event.x() - self._last_mouse_pos.x()
        dy = event.y() - self._last_mouse_pos.y()

        if event.buttons() & Qt.LeftButton:
            self.ww += dx
            self.wl -= dy
            self.wwl_changed.emit(self.ww, self.wl)
            
        elif event.buttons() & Qt.RightButton:
            self.pan_x += dx
            self.pan_y += dy
            self.update()
            
        self._last_mouse_pos = event.pos()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._last_mouse_pos = None
        self.setCursor(Qt.OpenHandCursor)

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        factor = 1.1 if delta > 0 else 1 / 1.1
        self.zoom_factor *= factor
        self.update()


# --- 3. MPRビューコンテナウィジェット (メインウィンドウに格納) ---
class MPRViewWidget(QWidget):
    def __init__(self, parent: 'PyQtDicomViewer'):
        super().__init__(parent)
        self.parent = parent
        self.all_slices_hu = None
        self.current_indices = None
        
        self.setup_ui()

    def setup_ui(self):
        grid_layout = QGridLayout(self)
        
        dummy_shape = (1, 1, 1) 
        self.axial_container = self._create_view_container("Axial", dummy_shape)
        self.coronal_container = self._create_view_container("Coronal", dummy_shape)
        self.sagittal_container = self._create_view_container("Sagittal", dummy_shape)
        
        self.axial_view = self.axial_container.findChild(ImageDisplayWidget)
        self.coronal_view = self.coronal_container.findChild(ImageDisplayWidget)
        self.sagittal_view = self.sagittal_container.findChild(ImageDisplayWidget)
        
        # レイアウト
        grid_layout.addWidget(QLabel("Axial", alignment=Qt.AlignCenter), 0, 0)
        grid_layout.addWidget(QLabel("Coronal", alignment=Qt.AlignCenter), 0, 1)
        grid_layout.addWidget(self.axial_container, 1, 0)
        grid_layout.addWidget(self.coronal_container, 1, 1)
        
        grid_layout.addWidget(QLabel("Sagittal", alignment=Qt.AlignCenter), 2, 0, 1, 2)
        grid_layout.addWidget(self.sagittal_container, 3, 0, 1, 2)
        
        # 拡張設定
        grid_layout.setRowStretch(1, 1) 
        grid_layout.setRowStretch(3, 1)
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)

    def _create_view_container(self, plane_name, shape):
        """ImageDisplayWidgetとスクロールバーを結合したコンテナを作成"""
        container = QWidget(self)
        h_layout_main = QHBoxLayout(container)
        h_layout_main.setContentsMargins(0, 0, 0, 0)
        h_layout_main.setSpacing(0)
        
        view = ImageDisplayWidget(container)
        view.current_plane = plane_name
        view._is_mpr_view = True
        
        # 垂直スライダー (左側に縦置き)
        v_slider = QSlider(Qt.Vertical)
        v_slider.setInvertedAppearance(True) 
        v_slider.setRange(0, shape[1] - 1)
        v_slider.valueChanged.connect(lambda v: self._update_mpr_index_from_slider(plane_name, 'y' if plane_name == 'Axial' else 'z', v))
        h_layout_main.addWidget(v_slider, 0)
        
        # 画像と水平スライダーのコンテナ (QVBoxLayout)
        v_container = QVBoxLayout()
        v_container.setContentsMargins(0, 0, 0, 0)
        v_container.setSpacing(0)
        
        view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) # 明示的に拡張ポリシーを設定
        v_container.addWidget(view, 1) 
        
        # 水平スライダー (画像の下に横置き)
        h_slider = QSlider(Qt.Horizontal)
        h_slider.setRange(0, shape[2] - 1)
        h_slider.valueChanged.connect(lambda v: self._update_mpr_index_from_slider(plane_name, 'x' if plane_name != 'Sagittal' else 'y', v))
        v_container.addWidget(h_slider, 0)

        h_layout_main.addLayout(v_container, 1)
        
        setattr(view, 'v_slider', v_slider)
        setattr(view, 'h_slider', h_slider)
        
        view.wwl_changed.connect(self.parent.update_wwl_from_mouse)
        
        return container

    def load_mpr_data(self, hu_data_3d):
        self.all_slices_hu = hu_data_3d
        z, y, x = hu_data_3d.shape[0] // 2, hu_data_3d.shape[1] // 2, hu_data_3d.shape[2] // 2
        self.current_indices = [z, y, x]
        
        # スライダーのレンジをデータサイズに合わせて更新
        self.axial_view.v_slider.setRange(0, hu_data_3d.shape[1] - 1)
        self.axial_view.h_slider.setRange(0, hu_data_3d.shape[2] - 1)
        
        self.coronal_view.v_slider.setRange(0, hu_data_3d.shape[0] - 1)
        self.coronal_view.h_slider.setRange(0, hu_data_3d.shape[2] - 1)
        
        self.sagittal_view.v_slider.setRange(0, hu_data_3d.shape[0] - 1)
        self.sagittal_view.h_slider.setRange(0, hu_data_3d.shape[1] - 1)

        self.update_all_views()

    def _update_mpr_index_from_slider(self, plane, axis, value):
        if self.current_indices is None: return
        
        new_indices = list(self.current_indices)
        
        if axis == 'z':
            new_indices[0] = value
        elif axis == 'y':
            new_indices[1] = value
        elif axis == 'x':
            new_indices[2] = value
            
        self.current_indices = new_indices
        self.update_all_views()

    def update_all_views(self):
        if self.all_slices_hu is None or self.current_indices is None: return
        
        z, y, x = self.current_indices
        ww, wl = self.parent.ww, self.parent.wl
        lower, upper = wl - ww / 2, wl + ww / 2
        
        views_map = {
            "Axial": (self.axial_view, z),
            "Coronal": (self.coronal_view, y),
            "Sagittal": (self.sagittal_view, x),
        }
        
        for plane, (view, index) in views_map.items():
            if plane == "Axial":
                hu_slice = self.all_slices_hu[index, :, :]
                view.v_slider.setValue(y) 
                view.h_slider.setValue(x)
            elif plane == "Coronal":
                hu_slice = self.all_slices_hu[:, index, :]
                view.v_slider.setValue(z)
                view.h_slider.setValue(x)
            elif plane == "Sagittal":
                hu_slice = self.all_slices_hu[:, :, index]
                view.v_slider.setValue(z)
                view.h_slider.setValue(y)
            
            # W/L適用ロジック
            display_array = np.clip(hu_slice, lower, upper)
            display_array = (display_array - lower) / ww * 255
            img_data_255 = display_array.astype(np.uint8)
            
            slice_info = f"{plane} | Z:{z}, Y:{y}, X:{x}"
            
            # ビューを更新
            view.set_image_data(img_data_255, ww, wl, 
                                slice_info=slice_info, 
                                indices=self.current_indices,
                                plane=plane,
                                is_mpr=True)


# --- 4. メインビューワーウィンドウ (PyQtDicomViewer) ---
class PyQtDicomViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced DICOM Viewer")
        self.setGeometry(100, 100, 1200, 800)
        
        self.files, self.ds = [], None
        self.index = 0
        self.pixel_min, self.pixel_max = 0, 4095
        self.hu_data = None
        self.all_slices_hu = None
        self.current_plane = "Axial"
        self.show_mpr_lines = True
        
        self.ww, self.wl = 400.0, 40.0

        self.create_menu()
        self.setup_ui()
        
    def create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("ファイル")
        
        open_folder_action = file_menu.addAction("フォルダを開く...")
        open_folder_action.triggered.connect(self.load_dicom_folder_dialog)
        file_menu.addSeparator()
        file_menu.addAction("終了").triggered.connect(self.close)
        
        view_menu = menubar.addMenu("表示")
        view_menu.addAction("DICOMヘッダ全体を表示").triggered.connect(self.show_full_dicom_header)
        view_menu.addSeparator()
        self.single_view_action = view_menu.addAction("単断面表示")
        self.mpr_view_action = view_menu.addAction("多断面比較")
        
        self.single_view_action.triggered.connect(lambda: self.switch_view_mode(0))
        self.mpr_view_action.triggered.connect(lambda: self.switch_view_mode(1))
        
        self.mpr_view_action.setEnabled(False)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        splitter = QSplitter(Qt.Horizontal)
        central_layout = QVBoxLayout(central_widget)
        central_layout.addWidget(splitter)

        # --- 左パネル (Left Pane) ---
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_pane.setMaximumWidth(350)
        
        title_font = QFont("Arial", 14) 
        title_label = QLabel("Advanced DICOM Viewer")
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(title_label)

        # 情報表示エリア
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.info_text.setMaximumHeight(200)
        left_layout.addWidget(self.info_text)

        # コントロール
        control_frame = QWidget()
        control_layout = QVBoxLayout(control_frame)
        
        control_layout.addWidget(QPushButton("自動輝度調整", clicked=self.auto_adjust_wwl))
        
        # WW スライダー
        control_layout.addWidget(QLabel("ウィンドウ幅 (WW)"))
        self.ww_slider = QSlider(Qt.Horizontal)
        self.ww_slider.setRange(1, 4095)
        self.ww_slider.setValue(int(self.ww))
        self.ww_slider.valueChanged.connect(lambda v: self.set_wwl_from_slider(v, self.wl_slider.value()))
        control_layout.addWidget(self.ww_slider)
        
        # WL スライダー
        control_layout.addWidget(QLabel("ウィンドウレベル (WL)"))
        self.wl_slider = QSlider(Qt.Horizontal)
        self.wl_slider.setRange(-1024, 3071)
        self.wl_slider.setValue(int(self.wl))
        self.wl_slider.valueChanged.connect(lambda v: self.set_wwl_from_slider(self.ww_slider.value(), v))
        control_layout.addWidget(self.wl_slider)
        
        # 断面切り替えドロップダウンリスト (シングルビュー用)
        control_layout.addWidget(QLabel("断面選択"))
        self.plane_selector = QComboBox()
        self.plane_selector.addItems(["Axial", "Coronal", "Sagittal"])
        self.plane_selector.currentTextChanged.connect(self.on_plane_change)
        control_layout.addWidget(self.plane_selector)
        
        left_layout.addWidget(control_frame)
        left_layout.addStretch(1)
        splitter.addWidget(left_pane)

        # --- 右パネル (Right Pane) ---
        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)
        
        # QStackedWidgetの導入
        self.view_stack = QStackedWidget()
        right_layout.addWidget(self.view_stack, 8)
        
        # 1. シングルビュー (Index 0)
        self.single_view_widget = QWidget()
        single_layout = QVBoxLayout(self.single_view_widget)
        self.image_widget = ImageDisplayWidget(self)
        self.image_widget.wwl_changed.connect(self.update_wwl_from_mouse)
        single_layout.addWidget(self.image_widget)
        self.view_stack.addWidget(self.single_view_widget)

        # 2. MPRビュー (Index 1)
        self.mpr_view_widget = MPRViewWidget(self)
        self.view_stack.addWidget(self.mpr_view_widget)

        # スライススライダー (共通)
        self.slice_slider = QSlider(Qt.Horizontal)
        self.slice_slider.setRange(0, 0)
        self.slice_slider.valueChanged.connect(self.on_slider_change)
        right_layout.addWidget(self.slice_slider)
        
        # ボタンフレーム
        button_frame = QWidget()
        button_layout = QHBoxLayout(button_frame)
        
        prev_btn = QPushButton("← 前へ", clicked=self.prev_image)
        next_btn = QPushButton("次へ →", clicked=self.next_image)
        
        button_size = QSize(120, 40)
        prev_btn.setFixedSize(button_size)
        next_btn.setFixedSize(button_size)
        
        button_layout.addStretch(1)
        button_layout.addWidget(prev_btn)
        button_layout.addWidget(next_btn)
        button_layout.addStretch(1)
        
        right_layout.addWidget(button_frame)

        splitter.addWidget(right_pane)
        splitter.setSizes([300, 900])

        self.addAction("Prev", self.prev_image, Qt.Key_Left)
        self.addAction("Next", self.next_image, Qt.Key_Right)
        
    def addAction(self, name, method, shortcut):
        action = self.menuBar().addAction(name)
        action.triggered.connect(method)
        action.setShortcut(shortcut)


    def switch_view_mode(self, index):
        """ビューモードを切り替える (0: 単断面, 1: MPR)"""
        if index == 1 and self.all_slices_hu is None:
             QMessageBox.information(self, "情報", "DICOMシリーズを先に読み込んでください。")
             return
             
        self.view_stack.setCurrentIndex(index)
        
        if index == 1:
            self.mpr_view_widget.load_mpr_data(self.all_slices_hu)
            self.plane_selector.setVisible(False)
            self.slice_slider.setVisible(False)
            self.set_window_title("多断面比較")
        else:
            self.plane_selector.setVisible(True)
            self.slice_slider.setVisible(True)
            self.on_plane_change(self.current_plane)
            self.set_window_title("単断面表示")
            
    def toggle_mpr_lines(self):
        pass


    # --- データの読み込みと更新 (Load) ---

    def load_dicom_folder_dialog(self):
        folder_path = QFileDialog.getExistingDirectory(self, "DICOMフォルダを選択", os.path.expanduser("~"))
        if folder_path:
            self.load_dicom_folder(folder_path)
            
    def load_dicom_folder(self, folder_path):
        self.files = sorted([os.path.join(folder_path, f) 
                             for f in os.listdir(folder_path) 
                             if f.lower().endswith('.dcm')])
        if not self.files:
            QMessageBox.critical(self, "エラー", "DICOMファイルが見つかりませんでした。")
            return
        
        try:
            slices = []
            for filepath in self.files:
                ds = pydicom.dcmread(filepath)
                raw_array = ds.pixel_array
                is_big_endian = not ds.file_meta.TransferSyntaxUID.is_little_endian
                if is_big_endian:
                    raw_array = raw_array.byteswap().newbyteorder('S')
                
                pixel_array = raw_array.astype(np.float32)
                slope = getattr(ds, 'RescaleSlope', 1.0)
                intercept = getattr(ds, 'RescaleIntercept', 0.0)
                slices.append(pixel_array * slope + intercept)
            
            self.all_slices_hu = np.stack(slices)
            self.ds = ds
            
            self.index = 0
            self.slice_slider.setRange(0, self.all_slices_hu.shape[0] - 1)
            self.mpr_view_action.setEnabled(True)
            self.load_image(is_new_series=True)
            self.set_window_title("単断面表示")
            
        except Exception as e:
            QMessageBox.critical(self, "3D読み込みエラー", f"DICOMシリーズの読み込み中にエラーが発生しました: {e}")
            self.files = []
            self.all_slices_hu = None
            return


    def on_plane_change(self, plane_name):
        if self.all_slices_hu is None: return
        
        self.current_plane = plane_name
        self.index = 0
        
        if plane_name == "Axial":
            max_index = self.all_slices_hu.shape[0] - 1
        elif plane_name == "Coronal":
            max_index = self.all_slices_hu.shape[1] - 1
        elif plane_name == "Sagittal":
            max_index = self.all_slices_hu.shape[2] - 1
        
        self.slice_slider.setRange(0, max_index)
        self.load_image()


    def load_image(self, is_new_series=False):
        if self.all_slices_hu is None: return
        
        if self.current_plane == "Axial":
            self.hu_data = self.all_slices_hu[self.index, :, :]
        elif self.current_plane == "Coronal":
            self.hu_data = self.all_slices_hu[:, self.index, :]
        elif self.current_plane == "Sagittal":
            self.hu_data = self.all_slices_hu[:, :, self.index]
        
        if is_new_series:
            self.pixel_min = int(self.all_slices_hu.min())
            self.pixel_max = int(self.all_slices_hu.max())
            
            self.wl_slider.setRange(self.pixel_min, self.pixel_max)
            self.ww_slider.setRange(1, self.pixel_max - self.pixel_min)
            self.auto_adjust_wwl()
        else:
            self.update_image()
        
        self.slice_slider.setValue(self.index)
        self.image_widget.zoom_factor, self.image_widget.pan_x, self.image_widget.pan_y = 1.0, 0, 0
        self.update_info_panel() 


    # --- W/L 関連のメソッド ---

    def auto_adjust_wwl(self):
        if self.all_slices_hu is None: return
        
        p1 = np.percentile(self.all_slices_hu, 1)
        p99 = np.percentile(self.all_slices_hu, 99)
        
        new_ww = p99 - p1
        new_wl = (p99 + p1) / 2
        
        self.set_wwl(new_ww, new_wl)
        
    def set_wwl_from_slider(self, ww, wl):
        self.set_wwl(float(ww), float(wl))
        
    def update_wwl_from_mouse(self, ww, wl):
        self.set_wwl(ww, wl, update_slider=True)
        
    def set_wwl(self, new_ww, new_wl, update_slider=False):
        self.ww = max(1.0, float(new_ww))
        self.wl = float(new_wl)
        
        if update_slider:
            safe_ww = int(np.clip(self.ww, self.ww_slider.minimum(), self.ww_slider.maximum()))
            safe_wl = int(np.clip(self.wl, self.wl_slider.minimum(), self.wl_slider.maximum()))
            
            self.ww_slider.setValue(safe_ww)
            self.wl_slider.setValue(safe_wl)

        self.update_image()
        self.update_info_panel()


    def update_image(self):
        if self.hu_data is None: return
        
        lower, upper = self.wl - self.ww / 2, self.wl + self.ww / 2
        
        display_array = self.hu_data.copy()
        np.clip(display_array, lower, upper, out=display_array)
        
        if self.ww > 0:
            display_array = (display_array - lower) / self.ww * 255
        else:
            display_array.fill(0)
            
        img_data_255 = display_array.astype(np.uint8)

        slice_info_str = f"{self.index + 1}/{self.slice_slider.maximum() + 1} ({self.current_plane})"
        
        if self.all_slices_hu is not None:
            max_z, max_y, max_x = self.all_slices_hu.shape
            if self.current_plane == "Axial":
                current_indices = [self.index, max_y // 2, max_x // 2]
            elif self.current_plane == "Coronal":
                current_indices = [max_z // 2, self.index, max_x // 2]
            else: 
                current_indices = [max_z // 2, max_y // 2, self.index]
        else:
            current_indices = None


        self.image_widget.set_image_data(img_data_255, self.ww, self.wl, 
                                         slice_info=slice_info_str,
                                         indices=current_indices,
                                         plane=self.current_plane,
                                         is_mpr=False)
        self.image_widget.update()
        
        if self.view_stack.currentIndex() == 1:
            self.mpr_view_widget.update_all_views()
        

    # --- UIとナビゲーション (その他) ---

    def set_window_title(self, mode: str):
        """現在のファイル情報とビューモードに基づいてウィンドウ名を更新する"""
        if self.ds is None:
            self.setWindowTitle("Advanced DICOM Viewer")
            return

        patient_name = str(getattr(self.ds, 'PatientName', 'N/A')).replace('^', ', ')
        patient_id = getattr(self.ds, 'PatientID', 'N/A')
        study_date = getattr(self.ds, 'StudyDate', 'N/A')
        modality = getattr(self.ds, 'Modality', 'N/A')

        title = (
            f"{patient_id}_{patient_name}_{study_date}_{modality}: {mode}"
        )
        self.setWindowTitle(title)


    def update_info_panel(self):
        if self.ds is None: return
        
        is_little_endian = self.ds.file_meta.TransferSyntaxUID.is_little_endian
        endian_info = "Little Endian" if is_little_endian else "Big Endian"
        
        info = {
            "ファイル名": os.path.basename(self.files[self.index]),
            "スライス": f"{self.index + 1}/{len(self.files)}",
            "患者名": getattr(self.ds, 'PatientName', 'N/A'),
            "患者ID": getattr(self.ds, 'PatientID', 'N/A'),
            "撮影日": getattr(self.ds, 'StudyDate', 'N/A'),
            "WW/WL": f"{int(self.ww)}/{int(self.wl)}",
            "ズーム": f"{self.image_widget.zoom_factor:.2f}",
            "エンディアン": endian_info
        }
        
        info_text = ""
        for key, value in info.items():
            info_text += f"**{key}**: {value}\n"
            
        self.info_text.setText(info_text)

    def show_full_dicom_header(self):
        if self.ds is None: 
            QMessageBox.information(self, "情報", "DICOMファイルが読み込まれていません。")
            return
            
        header_window = QWidget()
        header_window.setWindowTitle(f"DICOMヘッダ全体 - {os.path.basename(self.files[self.index])}")
        header_window.setGeometry(150, 150, 600, 800)
        
        text_widget = QTextEdit()
        text_widget.setReadOnly(True)
        text_widget.setText(str(self.ds))
        
        layout = QVBoxLayout(header_window)
        layout.addWidget(text_widget)
        header_window.show()
        self._header_window = header_window 

    def on_slider_change(self, value):
        new_index = int(value)
        if new_index != self.index:
            self.index = new_index
            self.load_image()

    def next_image(self):
        if self.index < self.slice_slider.maximum():
            self.index += 1
            self.load_image()

    def prev_image(self):
        if self.index > 0:
            self.index -= 1
            self.load_image()


if __name__ == "__main__":
    from PySide6.QtWidgets import QSizePolicy
    app = QApplication(sys.argv)
    viewer = PyQtDicomViewer()
    viewer.show()
    sys.exit(app.exec())