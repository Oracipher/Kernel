# plugins/crypto_guard/engine.py

import hmac
import hashlib
import os
from .utils import to_bytes, to_hex

class CryptoEngine:
    def __init__(self):
        # 初始化时生成一个内存中的随机密钥
        # 这个密钥只要插件不重启，就一直存在，但无法被外部直接读取
        self._master_key = os.urandom(32)

    def sign_data(self, message):
        """
        对消息进行签名
        返回: (signature_hex, status)
        """
        try:
            msg_bytes = to_bytes(message)
            # 使用 HMAC-SHA256 进行签名
            signature = hmac.new(self._master_key, msg_bytes, hashlib.sha256).digest()
            return to_hex(signature), True
        except Exception as e:
            return str(e), False

    def verify_data(self, message, signature_hex):
        """
        验证签名是否由本系统签发
        """
        try:
            expected_sig, _ = self.sign_data(message)
            # 防止时序攻击的字符串比较
            return hmac.compare_digest(expected_sig, signature_hex)
        except Exception:
            return False