import pydicom
import numpy as np
from PySide6.QtWidgets import (
		QApplication, QMainWindow,QVBoxLayout, QWidget, QMenuBar, QFileDialog
)

filepath = 'sample/JPCLN001.dcm'


def load_dicom_data(filepath):
  """
  DICOMファイルの読み込み関数
  ピクセルデータをNumpy配列に変換し、メタデータを辞書で返す。
  
  Args:
		filepath (str): DICOMファイルのパス
	Returns:
		pixel_array (np.ndarray): ピクセルデータのNumpy配列
		meta_data (dict): メタデータの辞書
	"""
  try:
    ds = pydicom.dcmread(filepath)
  except Exception as e:
    print(f'DICOMファイルの読み込みに失敗しました: {e}')
    return None, None

  # ピクセルデータをNumpy配列に変換
  pixel_array = ds.pixel_array.astype(np.int16)

	# メタデータの取得
  rescale_slope = ds.get('RescaleSlope', 1)
  rescale_intercept = ds.get('RescaleIntercept', 0)
  window_center = ds.get('WindowCenter', None)
  window_width = ds.get('WindowWidth', None)
  bits_stored = ds.get('BitsStored', None)

  meta_data = {
    'RescaleSlope': rescale_slope,
    'RescaleIntercept': rescale_intercept,
    'WindowCenter': window_center,
    'WindowWidth': window_width,
    'BitsStored': bits_stored
  }
  return pixel_array, meta_data

def get_hu_array(pixel_array, meta):
	"""
	HU値のNumPy配列に
	"""
	if pixel_array is None or meta is None:
		return None

	slope = meta.get('RescaleSlope', 1)
	intercept = meta.get('RescaleIntercept', 0)

	hu_array = pixel_array * slope + intercept
	return hu_array




pixel_array, meta = load_dicom_data(filepath)
# print(pixel_array)
print(meta)

num_grayscale_levels = 2 ** meta['BitsStored']
print(f'グレースケールレベル数: {num_grayscale_levels}')


