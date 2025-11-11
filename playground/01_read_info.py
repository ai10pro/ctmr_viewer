import pydicom

file = pydicom.dcmread('sample/JPCLN001.dcm')

print(file)

print()
print(file.Rows)
print(file[(0x7Fe0, 0x0010)])
print(file[(0x0002, 0x0010)])
# print(file.PixelData)

NON_COMPRESSED_UIDS = {
    '1.2.840.10008.1.2',    # Implicit VR Little Endian
    '1.2.840.10008.1.2.1'   # Explicit VR Little Endian
    # '1.2.840.10008.1.2.2' # Explicit VR Big Endian (これも非圧縮だが稀)
}

def check_compression_status(filepath):
    """
    DICOMファイルを読み込み、Transfer Syntax UIDに基づいて圧縮方式をチェックする関数
    """
    try:
        ds = pydicom.dcmread(filepath)
    except Exception as e:
        print(f"ファイル読み込みエラー: {e}")
        return False, "読み込み失敗"

    # 1. Transfer Syntax UID (UIDオブジェクト) を取得
    transfer_syntax_uid = ds.file_meta.TransferSyntaxUID
    
    # 2. UIDの文字列値を取得
    uid_string = str(transfer_syntax_uid)
    
    # 3. pydicomの便利な属性名 (可読性のため) を取得
    syntax_name = transfer_syntax_uid.name 

    # 4. UIDの文字列値が非圧縮のセットに含まれているかで判定
    is_compressed = uid_string not in NON_COMPRESSED_UIDS

    return is_compressed, syntax_name
compressed, syntax = check_compression_status('sample/JPCLN001.dcm')
# print(f"圧縮されているか: {compressed}, 転送構文: {syntax}")