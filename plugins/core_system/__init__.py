# plugins/core_system/__init__.py
from interface import IPlugin
import time

class Plugin(IPlugin):
    def start(self) -> None:
        self.api.log("核心系统正在启动...")
        
        # 使用 global scope 供他人读取
        self.api.set_data("core_status", "ONLINE", scope="global")
        
        # 注册一个测试事件
        self.api.on("test_event", self.handle_test)

    def handle_test(self, **kwargs):
        self.api.log(f"收到事件，正在处理(模拟耗时)... 参数: {kwargs}")
        time.sleep(2) # 模拟耗时，因为是线程池执行，不会卡住 Kernel 命令行
        self.api.log("事件处理完毕")

    def stop(self) -> None:
        self.api.log("核心系统停止")