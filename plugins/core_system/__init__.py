from interface import IPlugin

class Plugin(IPlugin):
    def start(self) -> None:
        config = self.api.get_plugin_config()
        version = config.get("version", "0.0")
        
        self.api.log(f"核心系统 (v{version}) 正在启动...")
        
        # 初始化核心数据
        self.api.set_data("core_status", "ONLINE")
        self.api.set_data("max_connections", 100)
        self.api.log("核心数据已初始化")

    def stop(self) -> None:
        self.api.log("核心系统停止")