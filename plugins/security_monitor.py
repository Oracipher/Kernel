
# plugins/security_monitor.py
from interface import Proot

class Plugin(Proot):
    def start(self):
        self.api.log("安保系统启动")
        self.api.on("risk_alert", self.handle_alert)
        
        # [Fix] 预先确保数据容器存在
        existing = self.api.get_data("security_logs")
        if existing is None:
            self.api.set_data("security_logs", [])

    def stop(self):
        pass

    def handle_alert(self, level, message, **kwargs):
        print(f"\n>>> [警报] 级别: {level} | 内容: {message}")
        
        if level == "HIGH":
            # [Fix] 使用专用的 key，避免污染全局 data
            # 这里的 append_data 在 api.py 中已经有权限检查，
            # 但我们需要确保目标是一个 list
            target_key = "security_logs"
            
            # 双重保险：检查当前类型
            current_data = self.api.get_data(target_key)
            if isinstance(current_data, list):
                self.api.append_data(target_key, f"BREACH: {message}")
                self.api.log("已归档高危记录")
            else:
                self.api.log(f"错误: 无法写入日志，'{target_key}' 不是列表")