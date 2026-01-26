# plugins/secure_audit/src/utils.py
import os
import hashlib
import datetime

class EnvLoader:
    """简易的 .env 解析器"""
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
                    env_vars[key.strip()] = value.strip()
        return env_vars

def generate_hash(content, salt):
    """生成防篡改指纹"""
    raw = f"{content}{salt}".encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

def get_timestamp():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")