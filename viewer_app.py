import sys
import os
import numpy as np
import pydicom
from PIL import Image

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QSlider, QLineEdit, QFileDialog, QTextEdit,
    QMenuBar, QMenu, QMessageBox, QSizePolicy # QSizePolicyをインポートに追加
)
from PySide6.QtCore import Qt, Signal, QSize, QRectF # QRectFは描画時の座標計算に役立つ
from PySide6.QtGui import QPixmap, QImage, QPainter, QMouseEvent, QWheelEvent, QFont, QColor # QColorを追加

# --- 1. 定数・ヘルパー関数 ---
NON_COMPRESSED_UIDS = {'1.2.840.10008.1.2', '1.2.840.10008.1.2.1'}

def numpy_to_qimage(array_255: np.ndarray) -> QImage:
    if array_255.dtype != np.uint8:
        array_255 = array_255.astype(np.uint8)
        
    height, width = array_255.shape
    qimage = QImage(array_255.data, width, height, width, QImage.Format_Grayscale8)
    return qimage


# --- 2. カスタム画像表示ウィジェット（W/Lとズーム/パン対応） ---
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
        self.slice_info = "" # ★ スライス情報保持用
        
        self.ww, self.wl = 400.0, 40.0
        self._last_mouse_pos = None

        self.zoom_factor = 1.0
        self.pan_x, self.pan_y = 0, 0
        
        self.setMouseTracking(True)
        
    def set_image_data(self, data_255: np.ndarray, ww, wl, slice_info=""):
        self.img_data_255 = data_255
        self.ww, self.wl = ww, wl
        self.slice_info = slice_info # ★ スライス情報を受け取る
        self.image_size = data_255.shape[::-1]
        self.update()

    def paintEvent(self, event):
        if self.img_data_255 is None:
            super().paintEvent(event)
            return

        painter = QPainter(self)
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
        
        # 2. ★★★ スライス情報の描画 (左下) ★★★
        if self.slice_info:
            painter.setPen(QColor(255, 255, 0)) # 文字色を黄色に設定
            
            # フォントを大きくして視認性を高める
            font = QFont("Arial", 16, QFont.Bold)
            painter.setFont(font)
            
            # 画像の左下隅の位置を計算
            # マージンを考慮して、paste_x と paste_y + new_h に描画
            text_x = paste_x + 10  # 左からのマージン
            text_y = paste_y + new_h - 10 # 下からのマージン
            
            # テキストを左下座標から描画
            painter.drawText(text_x, text_y, self.slice_info)

        painter.end()


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


# --- 3. メインビューワーウィンドウ ---
class PyQtDicomViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced DICOM Viewer v1.2 (PyQt/PySide)")
        self.setGeometry(100, 100, 1200, 800)
        
        self.files, self.ds = [], None
        self.index = 0
        self.pixel_min, self.pixel_max = 0, 4095
        self.hu_data = None
        
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
        title_label = QLabel("DICOM Viewer")
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
        
        left_layout.addWidget(control_frame)
        left_layout.addStretch(1)
        splitter.addWidget(left_pane)

        # --- 右パネル (Right Pane) ---
        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)

        # 画像表示ラベル (カスタムクラス)
        self.image_widget = ImageDisplayWidget()
        self.image_widget.wwl_changed.connect(self.update_wwl_from_mouse)
        
        # 画像エリアを優先的に拡張 (ストレッチ係数を大きく設定)
        right_layout.addWidget(self.image_widget, 8) 
        
        # --- スライダーとボタンエリア ---
        
        # ★★★ スライダーの説明ラベルを削除 ★★★

        # スライススライダー
        self.slice_slider = QSlider(Qt.Horizontal)
        self.slice_slider.setRange(0, 0)
        self.slice_slider.valueChanged.connect(self.on_slider_change)
        right_layout.addWidget(self.slice_slider)
        
        # ボタンフレーム
        button_frame = QWidget()
        button_layout = QHBoxLayout(button_frame)
        
        # 次へ・前へボタンのサイズを大きくする
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


    # --- データの読み込みと更新 ---

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

        self.index = 0
        self.slice_slider.setRange(0, len(self.files) - 1)
        self.load_image(is_new_series=True)
        
    def load_image(self, is_new_series=False):
        if not self.files: return
        
        try:
            filepath = self.files[self.index]
            self.ds = pydicom.dcmread(filepath)
            
            # 1. HU変換 (生のピクセルデータから)
            raw_array = self.ds.pixel_array
            
            is_big_endian = not self.ds.file_meta.TransferSyntaxUID.is_little_endian
            
            if is_big_endian:
                # Big Endianの場合、強制的にバイトスワップを行う
                raw_array = raw_array.byteswap().newbyteorder('S')
            
            # 2. Rescale処理
            pixel_array = raw_array.astype(np.float32)
            slope = getattr(self.ds, 'RescaleSlope', 1.0)
            intercept = getattr(self.ds, 'RescaleIntercept', 0.0)
            self.hu_data = pixel_array * slope + intercept
            
            if is_new_series:
                self.pixel_min = int(self.hu_data.min())
                self.pixel_max = int(self.hu_data.max())
                
                self.wl_slider.setRange(self.pixel_min, self.pixel_max)
                self.ww_slider.setRange(1, self.pixel_max - self.pixel_min)
                self.auto_adjust_wwl()
            else:
                self.update_image()
            
            self.slice_slider.setValue(self.index)
            self.image_widget.zoom_factor, self.image_widget.pan_x, self.image_widget.pan_y = 1.0, 0, 0

        except Exception as e:
            QMessageBox.critical(self, "読み込みエラー", f"ファイル '{os.path.basename(self.files[self.index])}' の読み込みエラー: {e}")

    def auto_adjust_wwl(self):
        if self.hu_data is None: return
        
        p1 = np.percentile(self.hu_data, 1)
        p99 = np.percentile(self.hu_data, 99)
        
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
        
        # 1. W/L適用ロジック
        lower, upper = self.wl - self.ww / 2, self.wl + self.ww / 2
        
        display_array = self.hu_data.copy()
        np.clip(display_array, lower, upper, out=display_array)
        
        if self.ww > 0:
            display_array = (display_array - lower) / self.ww * 255
        else:
            display_array.fill(0)
            
        img_data_255 = display_array.astype(np.uint8)

        # 2. スライス情報文字列を生成
        slice_info_str = f"{self.index + 1}/{len(self.files)}"
        
        # 3. カスタムウィジェットにデータを渡し、再描画を要求
        # ★ スライス情報文字列も渡す
        self.image_widget.set_image_data(img_data_255, self.ww, self.wl, slice_info=slice_info_str)
        self.image_widget.update()
        

    # --- UIとナビゲーション ---

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
            info_text += f"{key}: {value}\n"
            
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
        if self.index < len(self.files) - 1:
            self.index += 1
            self.load_image()

    def prev_image(self):
        if self.index > 0:
            self.index -= 1
            self.load_image()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = PyQtDicomViewer()
    viewer.show()
    sys.exit(app.exec())