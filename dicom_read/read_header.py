import pydicom

def load_dicom_header(filepath):
    file = pydicom.dcmread(filepath)

    print(file)
    return file