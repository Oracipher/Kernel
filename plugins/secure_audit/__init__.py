# plugins/secure_audit/__init__.py
import os
import json
from interface import IPlugin
# 注意这里的相对导入
from .src.utils import EnvLoader
from .src.client import AuditClient

class Plugin(IPlugin):
    def start(self):
        self.api.log("正在挂载 Secure Audit 系统...")
        
        # 1. 确定基准路径
        base_dir = os.path.dirname(__file__)
        
        # 2. 加载 .env
        env_path = os.path.join(base_dir, '.env')
        env_secrets = EnvLoader.load(env_path)
        if not env_secrets:
            self.api.log("警告: 未找到 .env 文件，使用不安全的默认设置")
            
        # 3. 加载 config.json
        cfg_path = os.path.join(base_dir, 'config.json')
        try:
            with open(cfg_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception:
            config = {"db_name": "audit.db", "log_file": "fallback.log"}

        # 4. 初始化内部客户端 (Service)
        try:
            self.audit_service = AuditClient(config, env_secrets, base_dir)
            self.api.log(f"审计服务已就绪. DB: {config.get('db_name')}")
        except Exception as e:
            self.api.log(f"服务初始化失败: {e}")
            return

        # 5. 注册事件监听
        self.api.on("audit:record", self._handle_record)
        self.api.on("audit:query", self._handle_query)
        
        # 广播服务上线
        self.api.set_data("service.audit", "ONLINE")

    def stop(self):
        self.api.set_data("service.audit", "OFFLINE")
        self.api.log("Secure Audit 系统已卸载，数据库连接关闭。")

    # --- 事件处理 ---

    def _handle_record(self, event_type, message):
        """处理记录请求"""
        try:
            fp = self.audit_service.record(event_type, message)
            self.api.log(f"已归档: {event_type} (Hash: {fp[:6]})")
        except Exception as e:
            self.api.log(f"写入失败: {e}")

    def _handle_query(self, limit=5):
        """处理查询请求"""
        logs = self.audit_service.get_recent(limit)
        # 这里的 print 只是为了演示，实际应该 emit 回去
        print("\n--- 最新审计日志 ---")
        for log in logs:
            print(f"ID:{log[0]} | {log[1]} | [{log[2]}] {log[3]}")
        print("--------------------\n")