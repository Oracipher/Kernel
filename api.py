# api.py

import copy

class Omni:
    """
    源自拉丁语，意为“全”
    内核暴露给插件的唯一操作接口(沙箱层/Facade模式)
    """
    
    def __init__(self, kernel, plugin_name):
        # [Mentor Note] 使用单下划线表示受保护成员，虽不能完全防止恶意访问，
        # 但符合 Python 约定。不要使用双下划线，那只是混淆名称，不是真正的私有。
        self._kernel = kernel
        self._plugin_name = plugin_name
        
        # [Mentor Note] 定义受保护的键值集合，查找速度 O(1)
        self._protected_keys = {"version", "admin", "config"}
        
    def log(self, message):
        """带插件名的日志"""
        print(f"[{self._plugin_name}] {message}")
        
    def monitor(self, event_name, callback):
        """注册事件监听,代理给内核"""
        if not callable(callback):
            self.log(f"Error: event {event_name} callback is not callable")
            return
        self._kernel.monitor(event_name, callback)

    def on(self, event_name, callback):
        """提供别名以符合常见习惯"""
        return self.monitor(event_name, callback)
        
    def emit(self, event_name, **kwargs):
        """发送事件"""
        self._kernel.emit(event_name, **kwargs)
        
    # --- 新增的数据操作接口 (已加固) ---
    
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
        
        # [Mentor Note] 这是一个关键的安全修复！
        # 必须确保返回的是深拷贝。如果拷贝失败（例如对象包含锁或文件句柄），
        # 绝对不能返回 raw_data，否则恶意插件会获得内核数据的直接引用（指针）。
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
        # [Mentor Note] 修复漏洞：之前 append 没有检查 protected_keys，
        # 导致黑客可以通过追加数据破坏配置。
        if not self._check_permission(key):
            return

        target = self._kernel.context.get(key)
        
        if target is None:
            self._kernel.context[key] = [value]
        elif isinstance(target, list):
            target.append(value)
        else:
            self.log(f"Error: Key '{key}' 存在但不是列表，无法追加数据。")