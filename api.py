# api.py
import os
import json
import threading
import weakref
from typing import Any, Callable, Dict, List, Optional

if False:
    from kernel import PluginKernel

class PluginAPI:
    """
    改进后的插件沙箱 API
    特点：线程安全代理、生命周期资源托管、弱引用内核
    """
    def __init__(self, kernel: 'PluginKernel', plugin_name: str, plugin_dir: str) -> None:
        # [解决 C: 沙箱逃逸] 使用弱引用，防止强引用循环，并使用私有属性名增加访问难度
        self.__kernel_ref = weakref.ref(kernel)
        self._plugin_name = plugin_name
        self._plugin_dir = plugin_dir
        
        # [解决 D: 异常隔离] 追踪插件创建的资源
        self._registered_events: List[str] = []
        self._managed_threads: List[threading.Thread] = []

    @property
    def _kernel(self) -> 'PluginKernel':
        """内部辅助方法：安全获取内核实例"""
        k = self.__kernel_ref()
        if k is None:
            raise RuntimeError("内核实例已销毁，插件API失效")
        return k

    def log(self, message: str) -> None:
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

    # --- 资源托管 (解决 D) ---

    def spawn_task(self, target: Callable, args: tuple = (), daemon: bool = True) -> None:
        """
        [推荐] 使用此方法启动线程，而非 threading.Thread
        内核可在卸载插件时追踪并清理这些线程。
        """
        t = threading.Thread(target=target, args=args, name=f"{self._plugin_name}-Worker")
        t.daemon = daemon
        t.start()
        self._managed_threads.append(t)
    
    def _cleanup(self) -> None:
        """[内核调用] 卸载时清理资源"""
        # 1. 等待非守护线程结束（可选逻辑，这里简单演示）
        # 2. 清理内部状态
        active_threads = [t for t in self._managed_threads if t.is_alive()]
        if active_threads:
            self.log(f"警告: 卸载时仍有 {len(active_threads)} 个活跃线程")
            # 实际生产中可能需要设置 Event 标志位通知线程退出
        self._managed_threads.clear()

    # --- 事件系统 ---
    
    def on(self, event_name: str, callback: Callable[..., Any]) -> None:
        # 调用内核的线程安全方法
        self._kernel.thread_safe_register_event(event_name, callback, owner=self._plugin_name)
        self._registered_events.append(event_name)
        
    def emit(self, event_name: str, **kwargs: Any) -> None:
        self._kernel.emit(event_name, **kwargs)

    # --- 数据中心 (解决 A: 线程安全委托) ---

    def get_data(self, key: str, scope: str = 'global', default: Any = None) -> Any:
        return self._kernel.thread_safe_get_data(self._plugin_name, key, scope, default)
    
    def set_data(self, key: str, value: Any, scope: str = 'local') -> None:
        self._kernel.thread_safe_set_data(self._plugin_name, key, value, scope)