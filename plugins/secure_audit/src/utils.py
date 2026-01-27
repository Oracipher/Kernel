
# plugins/secure_audit/src/utils.py
import os
import hashlib
import hmac
import datetime

class EnvLoader:
    @staticmethod
    def load(path):
        env_vars = {}
        if not os.path.exists(path):
            return env_vars
        
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    # [Fix] 去除首尾空格和可能的引号
                    key = key.strip()
                    value = value.strip().strip("'").strip('"')
                    env_vars[key] = value
        return env_vars

def generate_hash(content, salt):
    """
    [Fix] 使用 HMAC-SHA256 生成防篡改指纹
    比简单的 sha256(content + salt) 更安全
    """
    if isinstance(salt, str):
        salt = salt.encode('utf-8')
    if isinstance(content, str):
        content = content.encode('utf-8')
        
    return hmac.new(salt, content, hashlib.sha256).hexdigest()

def get_timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")