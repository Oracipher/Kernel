# api.py
import copy

class Omni:
    """
    源自拉丁语，意为“全”
    内核暴露给插件的唯一操作接口(沙箱层/Facade模式)
    """
    
    def __init__(self, kernel, plugin_name):
        self._kernel = kernel
        self._plugin_name = plugin_name
        
    def log(self, message):
        """带插件名的日志"""
        print(f"[{self._plugin_name}] {message}")
        
    def monitor(self, event_name, callback):
        """注册事件监听,代理给内核"""
        if not callable(callback):
            self.log(f"Error: event {event_name} callback is not callable")
            return
        self._kernel.monitor(event_name, callback)
        
    def emit(self, event_name, **kwargs):
        """发送事件"""
        self._kernel.emit(event_name, **kwargs)
        
    # --- 新增的数据操作接口 ---
    
    def get_data(self, key, default=None):
        """安全读取全局上下文数据"""
        # 返回数据的深拷贝，防止插件直接修改全局数据
        raw_data = self
        try:
            return copy.deepcopy(raw_data)
        except Exception:
            return copy.copy(raw_data)

    def set_data(self, key, value):
        """设置全局上下文数据"""
        # 在这里可以加权限控制，比如禁止修改 "admin"
        if key == "admin":
            self.log("Error: 权限不足，尝试修改管理员账号被拒绝")
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