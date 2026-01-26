# plugins/crypto_guard/utils.py

import binascii

def to_bytes(data):
    """强制转换为 bytes"""
    if isinstance(data, str):
        return data.encode('utf-8')
    return data

def to_hex(raw_bytes):
    """将 bytes 转为可读的 hex 字符串"""
    return binascii.hexlify(raw_bytes).decode('utf-8')