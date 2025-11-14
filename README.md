# Advanced DICOM Viewer

## 概要 (Overview)

本プロジェクトは、Python と PySide6 (Qt) をベースに開発された多機能な医用画像ビューワーです。CT や MR などの DICOM シリーズデータを読み込み、Hounsfield Unit (HU) 変換、Window/Level (W/L) 調整、ズーム/パン操作、および多断面再構成 (MPR) ビューによる相互参照を可能にします。

## 主な機能 (Features)

- **DICOM シリーズ読み込み**: フォルダ内の DICOM ファイル (dcm) を自動的に検出し、3D データとしてスタックします。
- **動的 W/L 調整**: スライダー操作、またはマウスドラッグ操作により、リアルタイムでコントラスト (WW) と輝度 (WL) を調整できます。
- **多断面再構成 (MPR)**:
  - **ビュー統合**: メインウィンドウ内で単断面表示と MPR 比較ビューを切り替え可能です。
  - **相互参照**: Axial, Coronal, Sagittal の 3 断面を同時に表示し、スクロールバー操作でインデックスをリンクさせます。
- **動的な情報表示**: 患者 ID、撮影情報、現在の W/L 値、およびエンディアン情報などをリアルタイムで表示します。

## ユーザーマニュアル

ユーザーマニュアルは別紙に記載されています。

## 開発環境 (Development Environment)

### 1. 動作環境

- Python 3.11
- Windows

### 2. ライブラリのインストール

以下のコマンドを実行して、必要な依存関係をインストールしてください。

```
pip install -r requirements.txt
```

### 3. 実行方法

```
python viewer_release.py
```

# ライセンス

このアプリケーションは GNU Lesser General Public License v3.0 のもとで公開されています。詳細は `LICENSE.txt` ファイルを参照してください。

このアプリケーションは PySide6 を利用しています。PySide6 は LGPL v3 ライセンスの下で公開されています。詳細は [こちら](https://www.qt.io/licensing/) を参照してください。