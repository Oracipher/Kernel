from interface import IPlugin

class Plugin(IPlugin):
    def start(self) -> None:
        self.api.log("安全工具正在启动...")
        
        # 检查依赖插件是否已经准备好了数据
        # 如果没有依赖管理，这里可能会读取到 None，导致报错
        core_status = self.api.get_data("core_status")
        
        if core_status == "ONLINE":
            self.api.log("检测到核心系统在线，安全模块挂载成功！")
        else:
            self.api.log("警告：核心系统未就绪！")

    def stop(self) -> None:
        self.api.log("安全工具卸载")