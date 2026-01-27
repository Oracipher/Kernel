# plugins/secure_audit/__init__.py
import os
import json
from interface import Proot
from .src.utils import EnvLoader
from .src.client import AuditClient

class Plugin(Proot):
    def start(self):
        self.api.log("正在挂载 Secure Audit 系统 (Fixed Version)...")
        
        base_dir = os.path.dirname(__file__)
        env_path = os.path.join(base_dir, '.env')
        env_secrets = EnvLoader.load(env_path)
        
        cfg_path = os.path.join(base_dir, 'config.json')
        config = {"db_name": "audit.db", "log_file": "audit.log"} # 默认值
        try:
            if os.path.exists(cfg_path):
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    config.update(file_config)
        except Exception:
            pass

        try:
            self.audit_service = AuditClient(config, env_secrets, base_dir)
            self.api.log(f"审计服务已就绪. DB: {config.get('db_name')}")
        except Exception as e:
            self.api.log(f"服务初始化失败: {e}")
            return

        self.api.on("audit:record", self._handle_record)
        self.api.on("audit:query", self._handle_query)
        self.api.set_data("service.audit", "ONLINE")

    def stop(self):
        # [Fix] 确保资源被正确释放
        if hasattr(self, 'audit_service'):
            self.audit_service.close()
            
        self.api.set_data("service.audit", "OFFLINE")
        self.api.log("Secure Audit 系统已安全卸载。")

    def _handle_record(self, event_type, message):
        try:
            fp = self.audit_service.record(event_type, message)
            self.api.log(f"已归档: {event_type} (Hash: {fp[:6]})")
        except Exception as e:
            self.api.log(f"写入失败: {e}")

    def _handle_query(self, limit=5, callback_event=None):
        """
        [Fix] 增加了 callback_event 支持，
        使得查询结果可以回传给调用者，而不是仅仅打印。
        """
        logs = self.audit_service.get_recent(limit)
        
        if callback_event:
            # 如果调用者提供了回调地址，将数据发送回去
            self.api.emit(callback_event, data=logs)
        else:
            # 兼容旧逻辑或命令行调试
            print("\n--- 最新审计日志 (Console Dump) ---")
            for log in logs:
                print(f"ID:{log[0]} | {log[1]} | [{log[2]}] {log[3]}")
            print("-----------------------------------\n")