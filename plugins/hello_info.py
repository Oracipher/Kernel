# plugins/hello_info.py

class Plugin:
    def __init__(self, context, kernel):
        self.context = context
        self.kernel = kernel

    def start(self):
        # 1. 读取共享上下文中的数据
        app_version = self.context.get("version", "Unknown")
        admin_name = self.context.get("admin", "Nobody")
        
        print("\n[HelloPlugin] 插件启动成功！")
        print(f"[HelloPlugin] 当前系统版本: {app_version}")
        print(f"[HelloPlugin] 管理员是: {admin_name}")
        
        # 2. 我们也可以往 context 里写点东西，留给别的插件看
        self.context["last_login_plugin"] = "HelloPlugin"

    def stop(self):
        print("[HelloPlugin] 我要下线了，白白！")