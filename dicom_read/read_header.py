# dicom_read/read_header.py

import pydicom
from typing import Dict, Any, Tuple

NON_COMPRESSED_UIDS = {
    '1.2.840.10008.1.2',    # Implicit VR Little Endian
    '1.2.840.10008.1.2.1'   # Explicit VR Little Endian
}

def get_transfer_syntax_uid(filepath: str) -> bool:
    """
    ファイルパスからDICOMファイルを読み込み、Transfer Syntax UIDを取得し、
    エンディアン情報を返す関数
    """
    try:
        ds = pydicom.dcmread(filepath)
    except Exception as e:
        print(f"DICOMファイル読み込みエラー: {e}")
        return False

    transfer_syntax = ds.file_meta.TransferSyntaxUID
    print(transfer_syntax)

    if transfer_syntax.is_little_endian:
        return "Little Endian"
    else:
        return "Big Endian"


def get_all_header_info(filepath: str) -> Dict[str, Any] | None:
    """
    指定されたDICOMファイルから、要求されたすべての主要なヘッダ情報とエンディアン情報を取得する。
    """
    try:
        # ファイルを読み込む
        ds = pydicom.dcmread(filepath)
    except Exception as e:
        print(f"DICOMファイル読み込みエラー: {e}")
        return None
    
    # 1. エンディアン情報の取得
    transfer_syntax = ds.file_meta.TransferSyntaxUID
    # 'is_little_endian'属性を利用して、Little EndianかBig Endianかを判定
    endian_info = "Little Endian" if transfer_syntax.is_little_endian else "Big Endian"
    
# --- 2. WC/WWの取得 ---
    # MultiValueの場合の処理と、タグが存在しない場合のデフォルト値設定
    try:
        wc_raw = getattr(ds, 'WindowCenter', 40)
        ww_raw = getattr(ds, 'WindowWidth', 400)
        wc = float(wc_raw[0] if isinstance(wc_raw, MultiValue) else wc_raw)
        ww = float(ww_raw[0] if isinstance(ww_raw, MultiValue) else ww_raw)
    except Exception:
        wc, ww = 40.0, 400.0

    # --- 3. 圧縮方式の取得と判定 ---
    uid_string = str(transfer_syntax)
    is_compressed = uid_string not in NON_COMPRESSED_UIDS

    # --- 4. 最低/最高画素値の取得 (NEW) ---
    # Smallest/Largest Image Pixel Value タグを取得。存在しない場合はNoneや0に設定。
    # 存在しない場合や、実際のピクセルデータから取得したい場合は、
    # ds.pixel_array.min() / max() を使うが、ここではヘッダ情報のみを対象とする。
    pixel_min = getattr(ds, 'SmallestImagePixelValue', None)
    pixel_max = getattr(ds, 'LargestImagePixelValue', None)

    # --- 5. 患者情報の取得 ---
    patient_info = {
        'PatientName': str(getattr(ds, 'PatientName', 'N/A')),
        'PatientID': getattr(ds, 'PatientID', 'N/A'),
        'StudyDate': getattr(ds, 'StudyDate', 'N/A'),
        'Modality': getattr(ds, 'Modality', 'N/A'),
    }
    
    # --- 6. すべての情報を統合して返す ---
    all_info = {
        'endian': endian_info,
        'wc': wc,
        'ww': ww,
        'transfer_syntax_name': transfer_syntax.name,
        'is_compressed': is_compressed,
        'patient_info': patient_info,
        'pixel_min': pixel_min, # 新規追加
        'pixel_max': pixel_max, # 新規追加
        'file_path': filepath
    }
    
    return all_info