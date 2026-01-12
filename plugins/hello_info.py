# plugins/hello_info.py
from interface import IPlugin

class Plugin(IPlugin):
    # 不需要写 __init__，父类 IPlugin 已经帮你把 self.api 设置好了

    def start(self):
        self.api.log("插件启动成功！")

        # 1. 通过 API 安全读取数据
        app_version = self.api.get_data("version", "Unknown")
        admin_name = self.api.get_data("admin", "Nobody")
        
        self.api.log(f"当前系统版本: {app_version}")
        self.api.log(f"管理员是: {admin_name}")
        
        # 2. 通过 API 安全写入数据
        # 原代码: self.context["last_login_plugin"] = "HelloPlugin"
        self.api.set_data("last_login_plugin", "HelloPlugin")

    def stop(self):
        self.api.log("我要下线了，白白！")