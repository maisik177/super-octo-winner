import os, ctypes
from ctypes import wintypes
from pathlib import Path
from stock import ApiError, ROOT

def protect(value: bytes, decrypt=False):
    if os.name != 'nt':
        raise ApiError('Zapamiętywanie klucza wymaga Windows (DPAPI).')

    class Blob(ctypes.Structure):
        _fields_ = [('length', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(value)
    source = Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise ApiError('Nie można odczytać/zapisać klucza Windows. Skonfiguruj klucz na tym koncie użytkownika.')
    try:
        return ctypes.string_at(output.data, output.length)
    finally:
        kernel.LocalFree(output.data)


KEY = ROOT / 'data' / 'api-key.dpapi'
def load_key():
    source = KEY
    try: return protect(source.read_bytes(), decrypt=True).decode('utf-8')
    except OSError: raise ApiError('Zaimportuj klucz API z pliku.')
def save_key(key):
    key=key.strip()
    if not key or any(c.isspace() for c in key): raise ApiError('Niepoprawny klucz.')
    KEY.parent.mkdir(parents=True,exist_ok=True)
    KEY.write_bytes(protect(key.encode()))
