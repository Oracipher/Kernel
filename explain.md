### 📂 目录结构预览

```text
/project_root
  ├── interface.py           # 接口定义（核心契约）
  ├── api.py                 # 插件 API（沙箱层）
  ├── kernel.py              # 内核（包含依赖解析算法）
  └── plugins/               # 插件目录
      ├── core_system/       # [插件1] 被依赖的基础插件
      │   ├── __init__.py    # 插件入口代码
      │   └── config.json    # 配置文件
      └── security_tools/    # [插件2] 依赖 core_system
          ├── __init__.py
          └── config.json
```

---

### 1. 接口层 (`interface.py`)

```python
# interface.py
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api import PluginAPI

class IPlugin(ABC):
    """
    插件接口基类
    """
    def __init__(self, api: 'PluginAPI') -> None:
        self.api = api
        
    @abstractmethod
    def start(self) -> None:
        """插件启动入口"""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """插件停止清理"""
        pass
```

### 2. 中间层 (`api.py`)

```python
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
```

### 3. 核心层 (`kernel.py`)

```python
# kernel.py
import os
import sys
import json
import gc
import importlib
import importlib.util
import traceback
import threading
from concurrent.futures import ThreadPoolExecutor, Future, wait, ALL_COMPLETED
from dataclasses import dataclass
from typing import Dict, List, Any, Callable, Optional, Set

from interface import IPlugin
from api import PluginAPI

@dataclass
class PluginMeta:
    name: str
    path: str
    dependencies: List[str]
    module: Any = None
    instance: Optional[IPlugin] = None
    api_instance: Optional[PluginAPI] = None
    active: bool = False

class PluginKernel:
    def __init__(self) -> None:
        self.PLUGIN_DIR = "plugins"
        
        self._lock = threading.RLock()
        
        self.context_global: Dict[str, Any] = {
            "version": "3.2 Enhanced",
            "admin": "Administrator"
        }
        self.context_local: Dict[str, Dict[str, Any]] = {}
        self.plugins_meta: Dict[str, PluginMeta] = {}
        self._events: Dict[str, List[tuple]] = {}
        
        self._executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="EventWorker")
        
        if not os.path.exists(self.PLUGIN_DIR):
            os.makedirs(self.PLUGIN_DIR)

    # --- 线程安全的数据访问接口 ---

    def thread_safe_get_data(self, caller: str, key: str, scope: str, default: Any) -> Any:
        with self._lock:
            if scope == 'global':
                return self.context_global.get(key, default)
            elif scope == 'local':
                return self.context_local.get(caller, {}).get(key, default)
            return default

    def thread_safe_set_data(self, caller: str, key: str, value: Any, scope: str) -> None:
        with self._lock:
            if scope == 'global':
                if key == "admin":
                    print(f"[Security] 插件 {caller} 尝试修改 admin 被拒绝")
                    return
                self.context_global[key] = value
            else:
                if caller not in self.context_local:
                    self.context_local[caller] = {}
                self.context_local[caller][key] = value

    def thread_safe_register_event(self, event_name: str, callback: Callable, owner: str) -> None:
        with self._lock:
            if event_name not in self._events:
                self._events[event_name] = []
            self._events[event_name].append((callback, owner))

    # --- [修改] 事件系统 (支持同步/异步反馈) ---

    def unregister_events_by_owner(self, owner: str) -> None:
        with self._lock:
            for name in list(self._events.keys()):
                self._events[name] = [
                    (cb, o) for cb, o in self._events[name] if o != owner
                ]
            
    def emit(self, event_name: str, **kwargs: Any) -> List[Future]:
        """
        [修改] 返回 Future 列表，允许调用者追踪执行状态
        """
        callbacks_snapshot = []
        with self._lock:
            if event_name in self._events:
                callbacks_snapshot = self._events[event_name][:]
        
        futures = []
        for func, owner in callbacks_snapshot:
            # 提交任务并保留 Future
            f = self._executor.submit(self._safe_event_call, func, event_name, owner, **kwargs)
            futures.append(f)
        return futures

    def sync_call_event(self, event_name: str, timeout: float = 5.0, **kwargs) -> List[Any]:
        """
        [新增] 同步等待所有事件处理器完成，并返回结果列表
        """
        futures = self.emit(event_name, **kwargs)
        if not futures:
            return []
            
        # 阻塞等待所有任务完成
        done, not_done = wait(futures, timeout=timeout, return_when=ALL_COMPLETED)
        
        results = []
        for f in done:
            try:
                results.append(f.result())
            except Exception as e:
                results.append(e) # 或者记录错误
        
        if not_done:
            print(f"[Warn] 事件 {event_name} 同步调用超时，{len(not_done)} 个任务未完成")
            
        return results

    def _safe_event_call(self, func: Callable, event_name: str, owner: str, **kwargs) -> Any:
        """执行实际回调并返回结果"""
        try:
            return func(**kwargs)
        except Exception as e:
            print(f"[!] 事件执行异常 [{owner}] -> {event_name}: {e}")
            raise e # 重新抛出，以便 Future 捕获

    # --- 依赖计算与拓扑 (保持原样) ---

    def _scan_plugins(self) -> None:
        if not os.path.exists(self.PLUGIN_DIR): return
        
        for entry in os.listdir(self.PLUGIN_DIR):
            plugin_path = os.path.join(self.PLUGIN_DIR, entry)
            if os.path.isdir(plugin_path):
                config_file = os.path.join(plugin_path, "config.json")
                if os.path.exists(config_file):
                    try:
                        with open(config_file, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                        name = config.get("name", entry)
                        
                        if name not in self.plugins_meta:
                            self.plugins_meta[name] = PluginMeta(
                                name=name, 
                                path=plugin_path, 
                                dependencies=config.get("dependencies", [])
                            )
                        else:
                            self.plugins_meta[name].dependencies = config.get("dependencies", [])
                            self.plugins_meta[name].path = plugin_path
                    except Exception:
                        pass

    def _resolve_dependencies(self) -> List[str]:
        ordered = []
        visited = set()
        visiting = set()

        def visit(name: str):
            if name in visited: return
            if name in visiting: raise Exception(f"循环依赖: {name}")
            if name not in self.plugins_meta: return

            visiting.add(name)
            for dep in self.plugins_meta[name].dependencies:
                visit(dep)
            visiting.remove(name)
            visited.add(name)
            ordered.append(name)

        for name in self.plugins_meta:
            if not self.plugins_meta[name].active:
                try: visit(name)
                except Exception as e: print(f"[!] 依赖错误 {name}: {e}")
        return ordered

    def _get_dependent_tree(self, target_plugin: str) -> List[str]:
        dependents = []
        rev_graph: Dict[str, List[str]] = {}
        for name, meta in self.plugins_meta.items():
            for dep in meta.dependencies:
                if dep not in rev_graph: rev_graph[dep] = []
                rev_graph[dep].append(name)
        
        queue = [target_plugin]
        visited = {target_plugin}
        while queue:
            current = queue.pop(0)
            if current in rev_graph:
                for child in rev_graph[current]:
                    if child not in visited:
                        visited.add(child)
                        queue.append(child)
                        dependents.append(child)
        
        full_order = self._resolve_dependencies()
        sorted_dependents = [p for p in full_order if p in dependents]
        return sorted_dependents

    # --- 插件生命周期 ---

    def load_plugin(self, name: str) -> bool:
        meta = self.plugins_meta.get(name)
        if not meta: return False
        if meta.active: return True

        try:
            # 保持使用 unique_module_name 进行隔离
            unique_module_name = f"mk_plugin_{name}"
            init_path = os.path.join(meta.path, "__init__.py")
            spec = importlib.util.spec_from_file_location(unique_module_name, init_path)
            
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[unique_module_name] = mod
                spec.loader.exec_module(mod)
                meta.module = mod
                
                if hasattr(mod, "Plugin"):
                    api = PluginAPI(self, name, meta.path)
                    meta.api_instance = api
                    
                    inst = mod.Plugin(api)
                    if isinstance(inst, IPlugin):
                        inst.start()
                        meta.instance = inst
                        meta.active = True
                        print(f"[+] 启动成功: {name}")
                        return True
            return False
        except Exception as e:
            print(f"[FATAL] 加载崩溃 {name}: {e}")
            traceback.print_exc()
            return False

    def unload_plugin(self, name: str) -> None:
        """
        [修改] 卸载流程增加了深度清理和 GC
        """
        meta = self.plugins_meta.get(name)
        if not meta or not meta.active: return

        print(f"[*] 正在卸载: {name}...")
        
        # 1. 逻辑停止
        try:
            if meta.instance:
                meta.instance.stop()
        except Exception as e:
            print(f"[!] Stop异常: {e}")

        # 2. 清理资源 (StopEvent 触发, 等待线程)
        if meta.api_instance:
            meta.api_instance._cleanup()

        # 3. 清理事件
        self.unregister_events_by_owner(name)
        
        # 4. 清理数据
        with self._lock:
            if name in self.context_local:
                del self.context_local[name]

        # 5. [解决 C: 深度清理] 移除模块引用
        unique_module_name = f"mk_plugin_{name}"
        if unique_module_name in sys.modules:
            del sys.modules[unique_module_name]
        
        # 解除所有引用
        meta.instance = None
        meta.module = None
        meta.api_instance = None # 这一步很关键，断开 API 对 Kernel 的弱引用持有者
        meta.active = False
        
        # 6. [新增] 强制垃圾回收
        # 这一步是为了解决 Python 的循环引用问题 (Plugin <-> API <-> Kernel)
        # 虽然使用了 weakref，但闭包、traceback 等仍可能造成循环引用
        gc.collect()
        
        print(f"[-] 卸载完成: {name} (GC Collected)")

    def reload_plugin(self, name: str) -> None:
        if name not in self.plugins_meta:
            print(f"[!] 未知插件: {name}")
            return

        print(f"\n[Refactor] 准备级联重载: {name}")
        
        dependents = self._get_dependent_tree(name)
        if dependents:
            print(f"[*] 检测到依赖链: {name} <- {', '.join(dependents)}")
        
        # 逆序卸载
        for dep_name in reversed(dependents):
            self.unload_plugin(dep_name)
            
        self.unload_plugin(name)
        
        # 刷新并重新加载
        self._scan_plugins()
        
        if self.load_plugin(name):
            # 正序恢复
            for dep_name in dependents:
                print(f"[*] 正在恢复依赖插件: {dep_name}")
                if not self.load_plugin(dep_name):
                    print(f"[!] 恢复失败: {dep_name}")
        else:
            print(f"[!] 核心插件 {name} 重载失败，依赖链恢复中止。")

    def init_system(self) -> None:
        self._scan_plugins()
        order = self._resolve_dependencies()
        for name in order:
            self.load_plugin(name)

    def shutdown(self):
        print("\n[*] 系统正在关闭...")
        active_plugins = [p for p, m in self.plugins_meta.items() if m.active]
        topo_order = self._resolve_dependencies()
        shutdown_order = [p for p in reversed(topo_order) if p in active_plugins]
        
        for name in shutdown_order:
            self.unload_plugin(name)
        self._executor.shutdown(wait=False)

if __name__ == "__main__":
    kernel = PluginKernel()
    kernel.init_system()
    
    while True:
        try:
            raw = input("\nKernel> ").strip().split()
            if not raw: continue
            cmd = raw[0].lower()
            
            if cmd == "exit":
                kernel.shutdown()
                break
            elif cmd == "list":
                for name, meta in kernel.plugins_meta.items():
                    status = "RUNNING" if meta.active else "STOPPED"
                    print(f" - {name}: {status}")
            elif cmd == "reload":
                if len(raw) > 1:
                    kernel.reload_plugin(raw[1])
                else:
                    print("Usage: reload <plugin_name>")
            elif cmd == "emit":
                # 测试同步调用
                if len(raw) > 1:
                    print("触发事件 (Wait)...")
                    # 使用新的 call 接口
                    results = kernel.sync_call_event(raw[1], msg="Manual trigger")
                    print(f"事件返回结果: {results}")
        except KeyboardInterrupt:
            kernel.shutdown()
            break

```

---

### 4. 插件示例

#### 插件 A: `plugins/core_system/`

1.  **config.json**
    ```json
    {
        "name": "core_system",
        "version": "1.0.0",
        "dependencies": []
    }
    ```

2.  **__init__.py**
    ```python
    # plugins/core_system/__init__.py
    from interface import IPlugin
    import time

    class Plugin(IPlugin):
        def start(self) -> None:
            self.api.log("核心系统正在启动...")
            
            # 使用 global scope 供他人读取
            self.api.set_data("core_status", "ONLINE", scope="global")
            
            # 注册一个测试事件
            self.api.on("test_event", self.handle_test)

        def handle_test(self, **kwargs):
            self.api.log(f"收到事件，正在处理(模拟耗时)... 参数: {kwargs}")
            time.sleep(2) # 模拟耗时，因为是线程池执行，不会卡住 Kernel 命令行
            self.api.log("事件处理完毕")

        def stop(self) -> None:
            self.api.log("核心系统停止")
    ```

#### 插件 B: `plugins/security_tools/` (依赖 core_system)

1.  **config.json**
    ```json
    {
        "name": "security_tools",
        "version": "1.2",
        "dependencies": ["core_system"]
    }
    ```

2.  **__init__.py**
    ```python
    # plugins/security_tools/__init__.py
    from interface import IPlugin

    class Plugin(IPlugin):
        def start(self) -> None:
            self.api.log("安全工具正在启动...")
            
            # 读取 global 数据
            status = self.api.get_data("core_status", scope="global")
            
            if status == "ONLINE":
                self.api.log("连接核心成功")
                # 存入 local 数据 (默认)
                self.api.set_data("firewall_rules", 50) 
            else:
                self.api.log("核心未就绪")
                # 可以在这里抛出异常，测试 Kernel 的容错回滚
                # raise Exception("依赖未满足，启动失败")

        def stop(self) -> None:
            self.api.log("安全工具卸载")
    ```
