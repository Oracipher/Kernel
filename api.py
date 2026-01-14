# api.py
import os
import json
from typing import Any, Callable, Dict, List

if False:
    from kernel import PluginKernel

class PluginAPI:
    """
    插件沙箱 API
    """
    def __init__(self, kernel: 'PluginKernel', plugin_name: str, plugin_dir: str) -> None:
        self._kernel = kernel
        self._plugin_name = plugin_name
        self._plugin_dir = plugin_dir
        # 追踪当前插件注册的事件，用于卸载时自动清理
        self._registered_events: List[str] = []

    def log(self, message: str) -> None:
        # 简单加个线程ID打印，方便调试异步
        import threading
        t_name = threading.current_thread().name
        print(f"[{self._plugin_name}][{t_name}] {message}")

    def get_plugin_config(self) -> Dict[str, Any]:
        config_path = os.path.join(self._plugin_dir, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.log(f"读取配置失败: {e}")
        return {}

    # --- 改进后的事件系统 ---
    
    def on(self, event_name: str, callback: Callable[..., Any]) -> None:
        """注册事件监听"""
        # 将注册行为委托给内核，并记录所有者
        self._kernel.register_event(event_name, callback, owner=self._plugin_name)
        self._registered_events.append(event_name)
        
    def emit(self, event_name: str, **kwargs: Any) -> None:
        """触发事件（现在支持异步分发）"""
        self._kernel.emit(event_name, **kwargs)

    # --- 改进后的数据中心（上下文隔离） ---

    def get_data(self, key: str, scope: str = 'global', default: Any = None) -> Any:
        """
        获取数据
        :param scope: 'global' (全局共享) 或 'local' (插件私有)
        """
        if scope == 'global':
            return self._kernel.context_global.get(key, default)
        elif scope == 'local':
            return self._kernel.context_local.get(self._plugin_name, {}).get(key, default)
        return default
    
    def set_data(self, key: str, value: Any, scope: str = 'local') -> None:
        """
        设置数据
        :param scope: 默认 'local' 防止污染全局，需显式指定 'global' 才能共享
        """
        if scope == 'global':
            if key == "admin":
                self.log("权限不足：禁止修改 admin 字段")
                return
            self._kernel.context_global[key] = value
        else:
            # 写入私有命名空间
            if self._plugin_name not in self._kernel.context_local:
                self._kernel.context_local[self._plugin_name] = {}
            self._kernel.context_local[self._plugin_name][key] = value