# api.py

class PluginAPI:
    """这是内核暴露给插件的唯一操作接口中间层
    插件只能通过这个类与系统交互
    无法直接触碰Kernel实例
    """
    
    def __init__(self, kernel, plugin_name):
        """我们在内部持有kernel的引用
        但是在python的约定中.
        以下划线开头的变量不建议在外部被访问
        """
        self._kernel = kernel
        self._plugin_name = plugin_name
        
    def log(self, message):
        """插件专属的日志方法
        这样做能够自动带上插件的名字，方便调试
        """
        print(f"[{self._plugin_name}] {message}")
        
    def on(self, event_name, callback):
        """代理注册监听
        """
        # 实例还是调用内核的方式，但是对插件来说是透明的
        self._kernel.on(event_name, callback)
        
    def emit(self, event_name, **kwargs):
        """代理发送事件
        """
        self._kernel.emit(event_name, **kwargs)
        
    def get_config(self, key):
        """只允许读取配置，不允许修改
        """
        return self._kernel.context.get(key)
    
    
    # 如果你允许插件修改数据，可以单独提供方法，并在这里做校验
    # def set_data(self, key, value):
    #     if key == "admin": 
    #         raise PermissionError("你不允许修改管理员账号！")
    #     self._kernel.context[key] = value