
# plugins/secure_audit/src/database.py
import sqlite3

class AuditDB:
    def __init__(self, db_path):
        self.db_path = db_path
        # [Fix] 建立持久连接，check_same_thread=False 允许在微内核的单线程模型中安全使用
        # 如果未来内核变成多线程，这里需要加锁
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._init_table()

    def _init_table(self):
        create_sql = """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            event_type TEXT,
            message TEXT,
            hash_fingerprint TEXT
        );
        """
        # 使用持久连接执行
        with self.conn:
            self.conn.execute(create_sql)

    def insert_log(self, timestamp, event, msg, fingerprint):
        sql = "INSERT INTO audit_logs (timestamp, event_type, message, hash_fingerprint) VALUES (?, ?, ?, ?)"
        try:
            # [Fix] 使用事务上下文，自动 commit/rollback
            with self.conn:
                self.conn.execute(sql, (timestamp, event, msg, fingerprint))
        except sqlite3.Error as e:
            print(f"[AuditDB Error] Insert failed: {e}")

    def query_logs(self, limit=5):
        sql = "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?"
        # 查询不需要 commit，直接用 cursor
        cursor = self.conn.execute(sql, (limit,))
        return cursor.fetchall()
        
    def close(self):
        """[Fix] 显式关闭连接"""
        if self.conn:
            self.conn.close()