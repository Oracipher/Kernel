# api.py
import os
import json
import threading
import weakref
import concurrent.futures
from typing import Any, Callable, Dict, List, Optional, Union

if False:
    from kernel import PluginKernel

class PluginAPI:
    """
    改进后的插件沙箱 API
    解决问题：
    1. 僵尸线程：引入 StopEvent 信号机制
    2. 事件反馈：支持同步调用 (call) 和 异步Future (emit)
    """
    def __init__(self, kernel: 'PluginKernel', plugin_name: str, plugin_dir: str) -> None:
        self.__kernel_ref = weakref.ref(kernel)
        self._plugin_name = plugin_name
        self._plugin_dir = plugin_dir
        
        # [解决 D] 资源追踪
        self._registered_events: List[str] = []
        self._managed_threads: List[threading.Thread] = []
        
        # [解决: 僵尸线程] 全局停止信号
        # 插件内的循环线程应当在每次迭代检查 self.api.is_active
        self._stop_event = threading.Event()

    @property
    def is_active(self) -> bool:
        """[新增] 插件是否处于活跃状态，用于线程循环判断退出条件"""
        return not self._stop_event.is_set()

    @property
    def _kernel(self) -> 'PluginKernel':
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

    # --- 资源托管 (解决: 僵尸线程) ---

    def spawn_task(self, target: Callable, args: tuple = (), daemon: bool = True) -> None:
        """
        启动托管线程。
        注意：target 函数内部必须在循环中检查 `if not api.is_active: break`，
        否则无法在卸载时优雅退出。
        """
        if self._stop_event.is_set():
            self.log("错误: 插件已停止，无法启动新任务")
            return

        t = threading.Thread(target=target, args=args, name=f"{self._plugin_name}-Worker")
        t.daemon = daemon
        t.start()
        self._managed_threads.append(t)
    
    def _cleanup(self) -> None:
        """[内核调用] 卸载时清理资源"""
        self.log("正在清理资源...")
        
        # 1. 发出停止信号
        self._stop_event.set()
        
        # 2. 等待线程结束 (加入超时机制，防止死锁)
        active_threads = [t for t in self._managed_threads if t.is_alive()]
        if active_threads:
            self.log(f"等待 {len(active_threads)} 个线程退出...")
            for t in active_threads:
                # 给予每个线程 1秒 的宽限期进行收尾
                t.join(timeout=1.0)
                if t.is_alive():
                    self.log(f"警告: 线程 {t.name} 未能响应停止信号 (可能处于死循环或IO阻塞)")
        
        self._managed_threads.clear()

    # --- 事件系统 (解决: Fire-and-Forget) ---
    
    def on(self, event_name: str, callback: Callable[..., Any]) -> None:
        self._kernel.thread_safe_register_event(event_name, callback, owner=self._plugin_name)
        self._registered_events.append(event_name)
        
    def emit(self, event_name: str, **kwargs: Any) -> List[concurrent.futures.Future]:
        """
        [修改] 异步分发事件，返回 Future 列表。
        可以通过 futures[i].result() 获取返回值或捕获异常。
        """
        return self._kernel.emit(event_name, **kwargs)

    def call(self, event_name: str, timeout: float = 5.0, **kwargs: Any) -> List[Any]:
        """
        [新增] 同步调用事件。
        阻塞直到所有监听者执行完毕，并返回结果列表。
        """
        return self._kernel.sync_call_event(event_name, timeout=timeout, **kwargs)

    # --- 数据中心 ---

    def get_data(self, key: str, scope: str = 'global', default: Any = None) -> Any:
        return self._kernel.thread_safe_get_data(self._plugin_name, key, scope, default)
    
    def set_data(self, key: str, value: Any, scope: str = 'local') -> None:
        self._kernel.thread_safe_set_data(self._plugin_name, key, value, scope)