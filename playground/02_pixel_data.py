import pydicom
import numpy as np

filepath = 'sample/JPCLN001.dcm'


def load_dicom_data(filepath):
  # DICOMファイルの読み込み
  try:
    ds = pydicom.dcmread(filepath)
  except Exception as e:
    print(f'DICOMファイルの読み込みに失敗しました: {e}')
    return None, None

  # ピクセルデータをNumpy配列に変換
  pixel_array = ds.pixel_array.astype(np.int16)

  rescale_slope = ds.get('RescaleSlope', 1)
  rescale_intercept = ds.get('RescaleIntercept', 0)
  window_center = ds.get('WindowCenter', None)
  window_width = ds.get('WindowWidth', None)

  meta_data = {
    'RescaleSlope': rescale_slope,
    'RescaleIntercept': rescale_intercept,
    'WindowCenter': window_center,
    'WindowWidth': window_width
  }
  return pixel_array, meta_data

pixel_array, meta = load_dicom_data(filepath)
# print(pixel_array)
print(meta)