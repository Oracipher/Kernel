# plugins/security_tools/__init__.py
from interface import IPlugin

class Plugin(IPlugin):
    def start(self) -> None:
        self.api.log("安全工具正在启动...")
        
        # 读取 global 数据
        status = self.api.get_data("core_status", scope="global")
        
        if status == "ONLINE":
            self.api.log("连接核心成功")
            # 存入 local 数据 (默认)
            self.api.set_data("firewall_rules", 50) 
        else:
            self.api.log("核心未就绪")
            # 可以在这里抛出异常，测试 Kernel 的容错回滚
            # raise Exception("依赖未满足，启动失败")

    def stop(self) -> None:
        self.api.log("安全工具卸载")