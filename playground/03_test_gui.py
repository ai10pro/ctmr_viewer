import sys
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QMenuBar, QFileDialog
)

# === 読み込み関数のダミー実装 ===
# 実際にはここにpydicomを使った読み込みロジックが入ります。
def load_dicom_data(filepath):
    """
    DICOMファイルを読み込むダミー関数。
    実際にはpydicom.dcmreadとピクセル配列/メタデータ取得ロジックが入る。
    """
    if not filepath:
        return None, None
        
    print(f"ダミーでDICOMファイル: {filepath} を読み込み中...")
    
    # 256x256のランダムなHU値配列を生成 (CT値の範囲 -1000〜1000 程度を想定)
    dummy_data = np.random.randint(-1000, 1000, size=(256, 256), dtype=np.int16)
    
    # ダミーのメタデータ（Rescaleと標準的なWindow/Level）
    dummy_metadata = {
        'slope': 1.0, 
        'intercept': 0, 
        'center': 40, 
        'width': 400
    }
    
    return dummy_data, dummy_metadata

def get_hu_array(pixel_array, metadata):
    """
    ピクセル配列とメタデータからHU値を計算するダミー関数。
    (ここでは既にload_dicom_dataでHU値相当のダミーを返しているが、処理の流れを維持)
    """
    # 実際のHU変換: hu_array = pixel_array * metadata['slope'] + metadata['intercept']
    return pixel_array

class DicomViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DICOM Viewer Prototype")
        self.setGeometry(100, 100, 800, 600)
        
        # --- UI構築 ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        self.layout = QVBoxLayout(central_widget)
        
        # pyqtgraphの画像ビューワウィジェット
        self.image_view = pg.ImageView()
        self.layout.addWidget(self.image_view)
        
        # メニューバーを作成
        self.create_menu_bar()

    def create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("ファイル(&F)")
        
        # 「開く」アクションをメニューに追加し、open_fileメソッドに接続
        open_action = file_menu.addAction("開く(&O)")
        open_action.triggered.connect(self.open_file)

    def open_file(self):
        # ファイルダイアログを開く
        filepath, _ = QFileDialog.getOpenFileName(
            self, 
            "DICOMファイルを開く", 
            "", 
            "DICOM Files (*.dcm);;All Files (*)"
        )
        
        if filepath:
            self.load_and_display_dicom(filepath)

    def load_and_display_dicom(self, filepath):
        """
        ファイルパスを受け取り、画像を読み込み、表示する
        """
        # 1. データ読み込み (ダミー or 実際のpydicom関数)
        pixel_data, metadata = load_dicom_data(filepath)
        
        if pixel_data is None:
            return

        # 2. HU値配列の取得 (ダミーではそのまま)
        hu_array = get_hu_array(pixel_data, metadata)
        
        # 3. pyqtgraphによる表示
        # pyqtgraph.ImageView.setImage()にデータを渡す
        self.image_view.setImage(hu_array)

        # 4. 固定のW/L値を初期レベルとして設定 (WW=400, WC=40)
        wc = metadata.get('center', 40)
        ww = metadata.get('width', 400)
        
        min_level = wc - (ww / 2)
        max_level = wc + (ww / 2)
        
        # setLevels(最小値, 最大値) で初期のウィンドウを設定
        self.image_view.setLevels(min_level, max_level)
        
        print(f"画像がGUIに表示されました。初期W/L: {ww}/{wc}")

# === アプリケーションの実行 ===
if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = DicomViewer()
    viewer.show()
    sys.exit(app.exec())