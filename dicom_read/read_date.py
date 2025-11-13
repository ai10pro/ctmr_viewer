import pydicom
import numpy as np
from typing import Dict, Any, Tuple

# ... (get_all_header_infoなどの他の関数は既に存在しているものとする) ...

def get_raw_pixel_data(filepath: str) -> Tuple[np.ndarray | None, Dict[str, float] | None]:
    """
    DICOMファイルから生のピクセルデータ配列と、Rescaleに必要なメタデータを取得する。
    HU値への変換は行わない。
    
    Args:
        filepath (str): DICOMファイルのパス。
        
    Returns:
        Tuple[np.ndarray | None, Dict[str, float] | None]: 
        生のピクセル配列と、Rescale Slope/Interceptの辞書。
    """
    try:
        # pydicomが自動でデコード/エンディアン処理を行う
        ds = pydicom.dcmread(filepath)
    except Exception as e:
        print(f"DICOMファイル読み込みエラー: {e}")
        return None, None
    
    # 1. 生のピクセル配列を取得
    try:
        raw_array = ds.pixel_array
        
    except NotImplementedError as e:
        # 圧縮データでデコーダが不足している場合
        print(f"デコーダ不足エラー。圧縮形式: {ds.file_meta.TransferSyntaxUID.name}")
        return None, None
    except Exception as e:
        print(f"ピクセルデータ取得エラー: {e}")
        return None, None

    # 2. Rescale情報を取得 (float型で統一)
    rescale_info = {
        'slope': float(getattr(ds, 'RescaleSlope', 1.0)),
        'intercept': float(getattr(ds, 'RescaleIntercept', 0.0))
    }
    
    # 生の配列とRescale情報を返す
    return raw_array, rescale_info