import dicom_read.read_header as read_header
import dicom_read.read_date as read_data

# main.py の呼び出し (修正不要)
def main():
    # 適切なファイルパスを指定
    # file = 'sample/JPCLN001.dcm'
    file = 'sample/2.16.840.1.114362.1.6.0.2.13412.6509808579.332603477.517.284.dcm'
    transfer_syntax_uid = read_header.get_transfer_syntax_uid(file)
    print(transfer_syntax_uid)
    print('---------------------')

    all_header_info = read_header.get_all_header_info(file)
    if all_header_info:
        print(all_header_info)
    
    print('---------------------')
    # --- 実行例 ---
    raw_data, rescale_tags = read_data.get_raw_pixel_data(file)
    if raw_data is not None:
        print(f"生のデータ形状: {raw_data.shape}")
        print(f"Rescale Slope: {rescale_tags['slope']}, Intercept: {rescale_tags['intercept']}")



if __name__ == '__main__':
    main()