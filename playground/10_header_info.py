import pydicom
import os

file = 'sample/JPCLN001.dcm'

read_pydicom = pydicom.dcmread(file)
read_os = os.path.getsize(file)

print(read_pydicom.Rows)
print(read_pydicom[(0x7Fe0, 0x0010)])