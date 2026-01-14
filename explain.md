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
import ast
import time
import importlib
import importlib.util
import traceback
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from typing import Dict, List, Any, Callable, Optional, Tuple

from interface import IPlugin
from api import PluginAPI

# --- [新增] 安全审计器 ---
class SecurityAuditor(ast.NodeVisitor):
    """
    [解决问题: 安全性]
    通过 AST 静态分析插件代码，禁止高危操作。
    """
    def __init__(self):
        self.errors = []
        # 禁止导入的模块
        self.banned_imports = {'os', 'subprocess', 'shutil', 'sys'}
        # 禁止调用的函数名 (简单匹配)
        self.banned_calls = {'eval', 'exec', 'system', 'popen'}

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name.split('.')[0] in self.banned_imports:
                self.errors.append(f"Line {node.lineno}: 禁止导入 '{alias.name}'")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module and node.module.split('.')[0] in self.banned_imports:
            self.errors.append(f"Line {node.lineno}: 禁止从 '{node.module}' 导入")
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            if node.func.id in self.banned_calls:
                self.errors.append(f"Line {node.lineno}: 禁止调用 '{node.func.id}'")
        # 检查属性调用如 os.system (简化版)
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in self.banned_calls:
                self.errors.append(f"Line {node.lineno}: 禁止调用属性方法 '{node.func.attr}'")
        self.generic_visit(node)

def scan_code_security(file_path: str) -> List[str]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source)
        auditor = SecurityAuditor()
        auditor.visit(tree)
        return auditor.errors
    except Exception as e:
        return [f"解析失败: {str(e)}"]

@dataclass
class PluginMeta:
    name: str
    path: str
    version: str = "0.0.0"  # [新增] 版本号
    dependencies: List[str] = field(default_factory=list)
    module: Any = None
    instance: Optional[IPlugin] = None
    api_instance: Optional[PluginAPI] = None
    active: bool = False

class PluginKernel:
    def __init__(self) -> None:
        self.PLUGIN_DIR = "plugins"
        self._lock = threading.RLock()
        
        self.context_global: Dict[str, Any] = {
            "version": "3.3 Secure-Core",
            "admin": "Administrator"
        }
        self.context_local: Dict[str, Dict[str, Any]] = {}
        self.plugins_meta: Dict[str, PluginMeta] = {}
        self._events: Dict[str, List[tuple]] = {}
        
        # 事件处理线程池
        self._executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="EventWorker")
        
        if not os.path.exists(self.PLUGIN_DIR):
            os.makedirs(self.PLUGIN_DIR)

    # --- 线程安全的数据访问接口 (保持不变) ---
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
                if key == "admin": return
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

    def unregister_events_by_owner(self, owner: str) -> None:
        with self._lock:
            for name in list(self._events.keys()):
                self._events[name] = [
                    (cb, o) for cb, o in self._events[name] if o != owner
                ]

    # --- [修改] 事件系统 (解决死锁) ---

    def emit(self, event_name: str, **kwargs: Any) -> List[Future]:
        """异步分发：投递到线程池，返回 Future"""
        callbacks_snapshot = []
        with self._lock:
            if event_name in self._events:
                callbacks_snapshot = self._events[event_name][:]
        
        futures = []
        for func, owner in callbacks_snapshot:
            f = self._executor.submit(self._safe_event_call, func, event_name, owner, **kwargs)
            futures.append(f)
        return futures

    def sync_call_event(self, event_name: str, timeout: float = 5.0, **kwargs) -> List[Any]:
        """
        [解决问题: 死锁]
        不再使用 ThreadPoolExecutor 进行同步等待。
        改为在当前线程直接顺序执行回调 (Inline Execution)。
        这避免了 "Worker 等待 Worker" 造成的资源饥饿死锁。
        """
        callbacks_snapshot = []
        with self._lock:
            if event_name in self._events:
                callbacks_snapshot = self._events[event_name][:]
        
        results = []
        if not callbacks_snapshot:
            return results

        # 顺序执行，捕获异常，确保不崩溃
        for func, owner in callbacks_snapshot:
            try:
                # 简单的超时控制较难在同步调用中实现，除非使用 signal 或额外线程
                # 这里假设同步调用必须是快速响应的
                res = func(**kwargs)
                results.append(res)
            except Exception as e:
                print(f"[Warn] 同步调用异常 [{owner}] -> {event_name}: {e}")
                results.append(e)
                
        return results

    def _safe_event_call(self, func: Callable, event_name: str, owner: str, **kwargs) -> Any:
        try:
            return func(**kwargs)
        except Exception as e:
            print(f"[!] 事件执行异常 [{owner}] -> {event_name}: {e}")
            raise e

    # --- [修改] 依赖与版本控制 ---

    def _parse_version(self, v_str: str) -> Tuple[int, ...]:
        """简单版本解析 1.2.0 -> (1, 2, 0)"""
        try:
            return tuple(map(int, v_str.split('.')))
        except:
            return (0, 0, 0)

    def _check_dep_version(self, req_str: str) -> bool:
        """
        [解决问题: 版本控制]
        解析格式: "core_system>=1.0.0" 或 "plugin_a"
        """
        if ">=" in req_str:
            name, ver_req = req_str.split(">=", 1)
            name = name.strip()
            ver_req = ver_req.strip()
            
            if name not in self.plugins_meta:
                return False # 依赖不存在
            
            current_ver = self.plugins_meta[name].version
            if self._parse_version(current_ver) < self._parse_version(ver_req):
                print(f"[Dep Error] {name} 版本 {current_ver} < 需要 {ver_req}")
                return False
            return True
        else:
            # 无版本要求，只检查存在性
            return req_str.strip() in self.plugins_meta

    def _resolve_dependencies(self) -> List[str]:
        ordered = []
        visited = set()
        visiting = set()

        def visit(name: str):
            if name in visited: return
            if name in visiting: raise Exception(f"循环依赖: {name}")
            if name not in self.plugins_meta: return

            visiting.add(name)
            meta = self.plugins_meta[name]
            
            for dep_str in meta.dependencies:
                # 提取纯名称用于递归 (去掉版本号)
                dep_name = dep_str.split(">=")[0].strip()
                
                # 在这里进行版本预检查
                if not self._check_dep_version(dep_str):
                    raise Exception(f"插件 {name} 的依赖 {dep_str} 未满足")
                
                visit(dep_name)
                
            visiting.remove(name)
            visited.add(name)
            ordered.append(name)

        for name in self.plugins_meta:
            if not self.plugins_meta[name].active:
                try: visit(name)
                except Exception as e: print(f"[!] 依赖解析错误: {e}")
        return ordered

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
                        version = config.get("version", "0.0.0")
                        deps = config.get("dependencies", [])
                        
                        # [解决问题: 动态更新] 无论是否存在都更新元数据
                        self.plugins_meta[name] = PluginMeta(
                            name=name, 
                            path=plugin_path, 
                            version=version,
                            dependencies=deps,
                            active=self.plugins_meta.get(name, PluginMeta("", "")).active,
                            instance=self.plugins_meta.get(name, PluginMeta("", "")).instance,
                            api_instance=self.plugins_meta.get(name, PluginMeta("", "")).api_instance
                        )
                    except Exception as e:
                        print(f"[Error] 读取配置 {entry} 失败: {e}")

    # --- [修改] 插件加载 (安全审计 + 超时) ---

    def load_plugin(self, name: str) -> bool:
        meta = self.plugins_meta.get(name)
        if not meta: return False
        if meta.active: return True

        # 1. [新增] 安全性静态审计
        init_path = os.path.join(meta.path, "__init__.py")
        if os.path.exists(init_path):
            security_issues = scan_code_security(init_path)
            if security_issues:
                print(f"[Security Block] 拒绝加载插件 {name}，发现高危代码:")
                for issue in security_issues:
                    print(f"  - {issue}")
                return False

        try:
            unique_module_name = f"mk_plugin_{name}"
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
                        # 2. [新增] 启动超时保护
                        # 防止插件 start() 里的 sleep 或死循环阻塞主线程
                        start_success = [False]
                        start_error = [None]
                        
                        def _safe_start():
                            try:
                                inst.start()
                                start_success[0] = True
                            except Exception as e:
                                start_error[0] = e

                        # 使用临时的 Daemon 线程加载
                        t = threading.Thread(target=_safe_start, name=f"Loader-{name}", daemon=True)
                        t.start()
                        t.join(timeout=3.0) # 3秒超时
                        
                        if t.is_alive():
                            print(f"[Timeout] 插件 {name} 启动超时 (>3s)，强制中止加载")
                            # 注意：Python无法强杀线程，这个线程会泄露，但主进程不会卡死
                            # 必须清理已创建的 API
                            api._cleanup()
                            return False
                        
                        if not start_success[0]:
                            raise start_error[0] if start_error[0] else Exception("未知启动错误")

                        meta.instance = inst
                        meta.active = True
                        print(f"[+] 启动成功: {name} (v{meta.version})")
                        return True
            return False
        except Exception as e:
            print(f"[FATAL] 加载崩溃 {name}: {e}")
            traceback.print_exc()
            return False

    def unload_plugin(self, name: str) -> None:
        """卸载逻辑保持类似，增加容错"""
        meta = self.plugins_meta.get(name)
        if not meta or not meta.active: return

        print(f"[*] 正在卸载: {name}...")
        
        # 停止也需要超时保护，防止 stop() 卡死
        if meta.instance:
            try:
                t = threading.Thread(target=meta.instance.stop, name=f"Unloader-{name}", daemon=True)
                t.start()
                t.join(timeout=2.0)
                if t.is_alive():
                    print(f"[Warn] 插件 {name} 停止超时，强制清理资源")
            except Exception as e:
                print(f"[!] Stop异常: {e}")

        if meta.api_instance:
            meta.api_instance._cleanup()

        self.unregister_events_by_owner(name)
        
        with self._lock:
            if name in self.context_local:
                del self.context_local[name]

        unique_module_name = f"mk_plugin_{name}"
        if unique_module_name in sys.modules:
            del sys.modules[unique_module_name]
        
        meta.instance = None
        meta.module = None
        meta.api_instance = None
        meta.active = False
        gc.collect()
        print(f"[-] 卸载完成: {name}")

    # --- 辅助方法 ---
    # reload_plugin, _get_dependent_tree 等逻辑复用旧代码...
    # 为节省篇幅，此处省略 reload_plugin/shutdown/init_system 的重复代码
    # 实际使用时请保留原有的这些方法

    def reload_plugin(self, name: str) -> None:
        # (保持原有逻辑，调用 unload 和 load)
        if name not in self.plugins_meta: return
        dependents = self._get_dependent_tree(name)
        for dep in reversed(dependents): self.unload_plugin(dep)
        self.unload_plugin(name)
        self._scan_plugins() # 重新扫描配置
        if self.load_plugin(name):
            for dep in dependents: self.load_plugin(dep)

    def _get_dependent_tree(self, target: str) -> List[str]:
        # (保持原有逻辑)
        # 注意 dependencies 列表现在包含版本号，需要清洗
        rev_graph = {}
        for name, meta in self.plugins_meta.items():
            for dep_str in meta.dependencies:
                dep_name = dep_str.split(">=")[0].strip()
                if dep_name not in rev_graph: rev_graph[dep_name] = []
                rev_graph[dep_name].append(name)
        
        queue = [target]
        visited = {target}
        dependents = []
        while queue:
            curr = queue.pop(0)
            if curr in rev_graph:
                for child in rev_graph[curr]:
                    if child not in visited:
                        visited.add(child)
                        queue.append(child)
                        dependents.append(child)
        
        # 简单拓扑排序，忽略版本校验，仅用于重载顺序
        # 实际生产中应复用 _resolve_dependencies
        return dependents

    def init_system(self) -> None:
        self._scan_plugins()
        order = self._resolve_dependencies()
        for name in order:
            self.load_plugin(name)

    def shutdown(self):
        print("\n[*] 系统正在关闭...")
        # 逆序停止
        active = [p for p, m in self.plugins_meta.items() if m.active]
        for name in reversed(active):
            self.unload_plugin(name)
        self._executor.shutdown(wait=False)

if __name__ == "__main__":
    k = PluginKernel()
    k.init_system()
    
    # 简单的命令行交互
    while True:
        try:
            raw = input("\nKernel> ").strip().split()
            if not raw: continue
            cmd = raw[0].lower()
            if cmd == "exit":
                k.shutdown()
                break
            elif cmd == "list":
                for n, m in k.plugins_meta.items():
                    print(f" - {n} (v{m.version}): {'RUNNING' if m.active else 'STOPPED'}")
            elif cmd == "emit":
                if len(raw) > 1:
                    print(k.sync_call_event(raw[1]))
        except KeyboardInterrupt:
            k.shutdown()
            break
```

---

### 4. 插件示例

#### 插件 A: `plugins/core_system/`

1.  **config.json**
    ```json
    {
        "name": "core_system",
        "version": "1.0.1",
        "dependencies": [],
        "description": "基础核心服务，提供版本号供检测"
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
        "version": "1.2.0",
        "dependencies": [
            "core_system>=1.0.0"
        ],
        "description": "依赖高版本核心系统的安全工具"
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
