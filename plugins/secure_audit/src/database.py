# plugins/secure_audit/src/database.py
import sqlite3
# import os

class AuditDB:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_table()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_table(self):
        """初始化表结构"""
        create_sql = """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            event_type TEXT,
            message TEXT,
            hash_fingerprint TEXT
        );
        """
        with self._get_conn() as conn:
            conn.execute(create_sql)

    def insert_log(self, timestamp, event, msg, fingerprint):
        sql = "INSERT INTO audit_logs (timestamp, event_type, message, hash_fingerprint) VALUES (?, ?, ?, ?)"
        with self._get_conn() as conn:
            conn.execute(sql, (timestamp, event, msg, fingerprint))

    def query_logs(self, limit=5):
        sql = "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?"
        with self._get_conn() as conn:
            cursor = conn.execute(sql, (limit,))
            return cursor.fetchall()