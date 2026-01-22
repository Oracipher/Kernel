from interface import IPlugin

class Plugin(IPlugin):
    def start(self):
        self.api.log("插件启动成功！")
        
        # 读取数据
        ver = self.api.get_data("version", "Unknown")
        self.api.log(f"读取系统版本: {ver}")
        
        # 写入数据
        self.api.set_data("last_login_plugin", "HelloPlugin")

    def stop(self):
        self.api.log("再见！")