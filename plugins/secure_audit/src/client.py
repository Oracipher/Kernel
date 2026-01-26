# plugins/secure_audit/src/client.py
import os
from .database import AuditDB
from .utils import generate_hash, get_timestamp

class AuditClient:
    def __init__(self, config, env_secrets, base_dir):
        # 组装路径
        self.db_path = os.path.join(base_dir, config['db_name'])
        self.log_txt_path = os.path.join(base_dir, config['log_file'])
        
        # 注入依赖
        self.salt = env_secrets.get('DB_SALT', 'default_salt')
        self.console_out = config.get('console_output', False)
        
        # 初始化数据库
        self.db = AuditDB(self.db_path)

    def record(self, event_type, message):
        """核心业务：记录日志"""
        ts = get_timestamp()
        # 计算安全指纹
        fingerprint = generate_hash(message + ts, self.salt)
        
        # 1. 写入数据库
        self.db.insert_log(ts, event_type, message, fingerprint)
        
        # 2. 写入文本文件 (备份)
        with open(self.log_txt_path, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] [{event_type}] {message} | Hash:{fingerprint[:8]}...\n")
            
        return fingerprint

    def get_recent(self, limit=5):
        return self.db.query_logs(limit)