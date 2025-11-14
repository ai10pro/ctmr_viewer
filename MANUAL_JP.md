# Advanced DICOM Viewer
# ユーザーマニュアル（JP）

## ダウンロード・実行
### GitHubからコードをダウンロードし実行
[GitHub-ai10pro/ctmr_viewer](https://github.com/ai10pro/ctmr_viewer)からGitクローンを行う。

```bash
git clone https://github.com/ai10pro/ctmr_viewer.git
cd ctmr_viewer
```

クローン後、Pythonの仮想環境を構築し、```requirements.txt```から必要なパッケージをインストールする。

```bash
python -m venv .venv
.venv/Scripts/activate/Activate.psl
pip install -r requirements.txt
```
ルードディレクトリにいることを確認し、```viewer_release.py```を実行する。

```bash
python viewer_release.py
```


## 操作方法