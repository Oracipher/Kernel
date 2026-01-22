# api.py

class PluginAPI:
    """
    内核暴露给插件的唯一操作接口（沙箱层）
    """
    
    def __init__(self, kernel, plugin_name):
        self._kernel = kernel
        self._plugin_name = plugin_name
        
    def log(self, message):
        """带插件名的日志"""
        print(f"[{self._plugin_name}] {message}")
        
    def on(self, event_name, callback):
        """注册事件监听"""
        self._kernel.on(event_name, callback)
        
    def emit(self, event_name, **kwargs):
        """发送事件"""
        self._kernel.emit(event_name, **kwargs)
        
    # --- 新增的数据操作接口 ---
    
    def get_data(self, key, default=None):
        """安全读取全局上下文数据"""
        return self._kernel.context.get(key, default)
    
    def set_data(self, key, value):
        """设置全局上下文数据"""
        # 在这里可以加权限控制，比如禁止修改 "admin"
        if key == "admin":
            self.log("警告：尝试修改管理员账号被拒绝！")
            return
        self._kernel.context[key] = value
        
    def append_data(self, key, value):
        """向列表类型的数据追加内容"""
        target = self._kernel.context.get(key)
        if target is None:
            self._kernel.context[key] = [value]
        elif isinstance(target, list):
            target.append(value)
        else:
            self.log(f"错误：{key} 不是一个列表，无法追加数据")