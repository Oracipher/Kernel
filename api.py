# api.py

import copy

class Omni:
    """
    内核暴露给插件的唯一操作接口(沙箱层/Facade模式)
    """
    
    def __init__(self, kernel, plugin_name):
        # 使用单下划线表示受保护成员，虽不能完全防止恶意访问，
        # 但符合 Python 约定。不要使用双下划线，那只是混淆名称，不是真正的私有。
        self._kernel = kernel
        self._plugin_name = plugin_name
        
        # 定义受保护的键值集合，查找速度 O(1)
        self._protected_keys = {"version", "admin", "config"}
        
    def log(self, message):
        """带插件名的日志"""
        print(f"[{self._plugin_name}] {message}")
        
    def synapse(self, event_name, callback):
        """注册事件监听,代理给内核"""
        if not callable(callback):
            self.log(f"Error: event {event_name} callback is not callable")
            return
        self._kernel.synapse(event_name, callback)

    def on(self, event_name, callback):
        """提供别名以符合常见习惯"""
        return self.synapse(event_name, callback)
        
    def impulse(self, event_name, **kwargs):
        """发送事件"""
        self._kernel.impulse(event_name, **kwargs)
        
    def emit(self, event_name, **kwargs):
        """提供别名以符合常见习惯"""
        return self.impulse(event_name, **kwargs)
        
    # --- 新增的数据操作接口  ---
    
    def _check_permission(self, key):
        """内部权限检查方法"""
        if key in self._protected_keys:
            self.log(f"Security Alert: 拒绝访问/修改受保护的键 '{key}'")
            return False
        return True

    def get_data(self, key, default=None):
        """安全读取全局上下文数据"""
        if key not in self._kernel.context:
            return default
        
        raw_data = self._kernel.context[key]
        """
        返回数据的深拷贝，防止插件直接修改全局数据
        注意：深拷贝可能失败（例如包含无法复制的对象），
        此时返回默认值并记录安全警告日志。
        """
        try:
            return copy.deepcopy(raw_data)
        except Exception:
            self.log(f"Security Warning: Data '{key}' is unsafe to copy. Access denied.")
            return default # 安全失败 (Fail Safe)

    def set_data(self, key, value):
        """设置全局上下文数据"""
        if not self._check_permission(key):
            return
        self._kernel.context[key] = value
        
    def append_data(self, key, value):
        """向列表类型的数据追加内容"""
        # 追加数据前必须检查权限，防止恶意插件绕过 set_data 直接修改受保护数据
        if not self._check_permission(key):
            return

        target = self._kernel.context.get(key)
        
        if target is None:
            self._kernel.context[key] = [value]
        elif isinstance(target, list):
            target.append(value)
        else:
            self.log(f"Error: Key '{key}' 存在但不是列表，无法追加数据。")