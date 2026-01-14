# api.py
import os
import json
from typing import Any, Callable, Dict, Optional, List, Union

# 为了类型提示，引用 Kernel 但不直接实例化
if False:
    from kernel import PluginKernel

class PluginAPI:
    """
    内核暴露给插件的唯一操作接口（沙箱层）
    """
    
    def __init__(self, kernel: 'PluginKernel', plugin_name: str, plugin_dir: str) -> None:
        self._kernel = kernel
        self._plugin_name = plugin_name
        self._plugin_dir = plugin_dir
        
    @property
    def plugin_dir(self) -> str:
        """获取当前插件的目录路径"""
        return self._plugin_dir

    def log(self, message: str) -> None:
        print(f"[{self._plugin_name}] {message}")
        
    def get_plugin_config(self) -> Dict[str, Any]:
        """读取插件目录下 config.json 的内容"""
        config_path = os.path.join(self._plugin_dir, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.log(f"读取配置文件失败: {e}")
                return {}
        return {}

    # --- 事件系统代理 ---
    def on(self, event_name: str, callback: Callable[..., Any]) -> None:
        self._kernel.on(event_name, callback)
        
    def emit(self, event_name: str, **kwargs: Any) -> None:
        self._kernel.emit(event_name, **kwargs)
        
    # --- 数据中心代理 ---
    def get_data(self, key: str, default: Any = None) -> Any:
        return self._kernel.context.get(key, default)
    
    def set_data(self, key: str, value: Any) -> None:
        if key == "admin":
            self.log("权限不足：无法修改 admin")
            return
        self._kernel.context[key] = value