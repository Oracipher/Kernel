# api.py
import copy
# import logging

class Omni:
    """
    源自拉丁语，意为“全”
    内核暴露给插件的唯一操作接口(沙箱层/Facade模式)
    """
    
    def __init__(self, kernel, plugin_name):
        self.__kernel = kernel
        self._plugin_name = plugin_name
        
    def log(self, message):
        """带插件名的日志"""
        print(f"[{self._plugin_name}] {message}")
        
    def monitor(self, event_name, callback):
        """注册事件监听,代理给内核"""
        if not callable(callback):
            self.log(f"Error: event {event_name} callback is not callable")
            return
        self.__kernel.monitor(event_name, callback)
        
    def emit(self, event_name, **kwargs):
        """发送事件"""
        self.__kernel.emit(event_name, **kwargs)
        
    # --- 新增的数据操作接口 ---
    
    def get_data(self, key, default=None):
        """安全读取全局上下文数据"""
        # 返回数据的深拷贝，防止插件直接修改全局数据
        # 修正为从内核中context读取
        
        # 1. 从内核获取原始数据
        if key not in self.__kernel.context:
            return default
        raw_data = self.__kernel.context[key]
        
        # 2. 返回数据深拷贝，防止插件污染全局环境
        try:
            return copy.deepcopy(raw_data)
        except Exception:
            # self.log(f"Warning: Data '{key}' copy failed ({e}), returning shallow copy")
            return raw_data

    def set_data(self, key, value):
        """设置全局上下文数据"""
        # 在这里可以加权限控制，比如禁止修改 "admin"
        # 安全控制： 禁止覆盖上下文数据
        protected_keys = ["admin", "version", "config"]
        if key in protected_keys:
            self.log(f"Security Alert: 尝试修改受保护的键 '{key}' 被拒绝")
            return
        self.__kernel.context[key] = value
        
    def append_data(self, key, value):
        """向列表类型的数据追加内容"""
        target = self.__kernel.context.get(key)
        if target is None:
            self.__kernel.context[key] = [value]
        elif isinstance(target, list):
            target.append(value)
        else:
            self.log(f"Error: Key '{key}' 存在但不是列表，无法追加数据。")