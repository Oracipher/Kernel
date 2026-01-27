
# plugins/secure_audit/src/client.py
import os
from .database import AuditDB
from .utils import generate_hash, get_timestamp

class AuditClient:
    def __init__(self, config, env_secrets, base_dir):
        self.db_path = os.path.join(base_dir, config['db_name'])
        
        # [Fix] 预先打开日志文件，避免频繁 open/close
        log_txt_path = os.path.join(base_dir, config['log_file'])
        self.log_file = open(log_txt_path, 'a', encoding='utf-8', buffering=1) # buffering=1 行缓冲
        
        self.salt = env_secrets.get('DB_SALT', 'default_salt')
        self.db = AuditDB(self.db_path)

    def record(self, event_type, message):
        ts = get_timestamp()
        # HMAC 计算
        fingerprint = generate_hash(message + ts, self.salt)
        
        # 1. 写入数据库
        self.db.insert_log(ts, event_type, message, fingerprint)
        
        # 2. 写入文本文件 (使用已打开的句柄)
        try:
            self.log_file.write(f"[{ts}] [{event_type}] {message} | Hash:{fingerprint[:8]}...\n")
            # 如果非常重要，可以 self.log_file.flush()
        except Exception as e:
            print(f"[Audit Warning] File write failed: {e}")
            
        return fingerprint

    def get_recent(self, limit=5):
        return self.db.query_logs(limit)
        
    def close(self):
        """[Fix] 统一资源清理"""
        if self.db:
            self.db.close()
        if self.log_file:
            try:
                self.log_file.close()
            except:
                pass