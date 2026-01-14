import os
import json
import threading
import weakref
import concurrent.futures
from typing import Any, Callable, Dict, List, TYPE_CHECKING

# 使用 TYPE_CHECKING 避免循环导入，仅用于静态分析
if TYPE_CHECKING:
    from kernel import PluginKernel

class PluginAPI:
    """
    改进后的插件沙箱 API (Thread-Safe Version)
    
    特性：
    1. 线程安全：对资源列表的操作加锁，防止竞态条件。
    2. 信号机制：提供 is_active 属性供插件轮询。
    3. 资源追踪：记录托管线程，卸载时尝试优雅关闭。
    """
    
    def __init__(self, kernel: 'PluginKernel', plugin_name: str, plugin_dir: str) -> None:
        # 使用弱引用防止循环引用 (PluginAPI <-> PluginKernel)
        self.__kernel_ref = weakref.ref(kernel)
        self._plugin_name = plugin_name
        self._plugin_dir = plugin_dir
        
        # --- 资源管理 ---
        # 引入重入锁，保护资源列表的并发读写
        self._resource_lock = threading.RLock()
        
        self._registered_events: List[str] = []
        self._managed_threads: List[threading.Thread] = []
        
        # 全局停止信号
        self._stop_event = threading.Event()

    @property
    def is_active(self) -> bool:
        """
        插件生命周期状态检查。
        所有耗时循环（如 while True）必须在每次迭代中检查此属性。
        如果为 False，应立即 break 退出。
        """
        return not self._stop_event.is_set()

    @property
    def _kernel(self) -> 'PluginKernel':
        """安全地获取内核实例"""
        k = self.__kernel_ref()
        if k is None:
            # 这种情况通常发生在系统关闭时
            raise RuntimeError(f"内核已销毁，插件 {self._plugin_name} API 调用失败")
        return k

    def log(self, message: str) -> None:
        """格式化日志输出"""
        t_name = threading.current_thread().name
        print(f"[{self._plugin_name}][{t_name}] {message}")

    def get_plugin_config(self) -> Dict[str, Any]:
        """读取插件目录下的 config.json"""
        config_path = os.path.join(self._plugin_dir, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.log(f"读取配置失败: {e}")
        return {}

    # --- 资源托管 (修复: 竞态条件) ---

    def spawn_task(self, target: Callable, args: tuple = (), daemon: bool = True) -> None:
        """
        启动托管线程。
        
        注意：Python 无法强制杀死线程。
        Target 函数必须在逻辑中检查 `if not api.is_active: break`。
        """
        if self._stop_event.is_set():
            self.log("错误: 插件已停止，拒绝启动新任务")
            return

        # 封装一下 target，以便未来可以在线程结束时自动从列表中移除自己（可选优化）
        # 这里保持简单，主要关注启动时的线程安全
        t = threading.Thread(target=target, args=args, name=f"{self._plugin_name}-Worker")
        t.daemon = daemon
        
        # 加锁写入列表，防止和 _cleanup 冲突
        with self._resource_lock:
            self._managed_threads.append(t)
            
        t.start()
    
    def _cleanup(self) -> None:
        """[内核内部调用] 卸载时清理资源"""
        self.log("正在清理资源...")
        
        # 1. 发出全局停止信号
        self._stop_event.set()
        
        # 2. 安全获取线程快照
        # 在锁内复制列表并清空原列表，防止遍历时列表被修改
        threads_snapshot = []
        with self._resource_lock:
            threads_snapshot = self._managed_threads[:]
            self._managed_threads.clear()
        
        # 3. 在锁外等待线程结束 (避免死锁)
        active_threads = [t for t in threads_snapshot if t.is_alive()]
        
        if active_threads:
            self.log(f"正在等待 {len(active_threads)} 个后台线程退出...")
            for t in active_threads:
                # 给予每个线程 1秒 的宽限期进行收尾
                t.join(timeout=1.0)
                
                if t.is_alive():
                    # 这里是 Python 线程机制的局限：我们无法物理杀死它
                    self.log(f"⚠️ 警告: 线程 '{t.name}' 未响应停止信号，将成为僵尸线程。")
                    self.log("   (请检查插件代码是否存在死循环或阻塞IO)")
        
        self.log("资源清理完毕")

    # --- 事件系统 ---
    
    def on(self, event_name: str, callback: Callable[..., Any]) -> None:
        """注册事件监听"""
        self._kernel.thread_safe_register_event(event_name, callback, owner=self._plugin_name)
        with self._resource_lock:
            self._registered_events.append(event_name)
        
    def emit(self, event_name: str, **kwargs: Any) -> List[concurrent.futures.Future]:
        """
        异步分发事件 (Fire-and-Forget)。
        返回 Future 列表，可用于查询执行结果或异常。
        """
        return self._kernel.emit(event_name, **kwargs)

    def call(self, event_name: str, timeout: float = 5.0, **kwargs: Any) -> List[Any]:
        """
        同步调用事件 (Blocking)。
        阻塞当前线程，直到所有监听者执行完毕。
        返回结果列表。
        """
        return self._kernel.sync_call_event(event_name, timeout=timeout, **kwargs)

    # --- 数据共享中心 ---

    def get_data(self, key: str, scope: str = 'global', default: Any = None) -> Any:
        """获取共享数据"""
        return self._kernel.thread_safe_get_data(self._plugin_name, key, scope, default)
    
    def set_data(self, key: str, value: Any, scope: str = 'local') -> None:
        """设置共享数据"""
        self._kernel.thread_safe_set_data(self._plugin_name, key, value, scope)