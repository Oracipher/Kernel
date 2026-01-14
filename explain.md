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
```

### 3. 核心层 (`kernel.py`)

```python
# kernel.py
import os
import sys
import json
import importlib
import importlib.util
import traceback
import threading
from concurrent.futures import ThreadPoolExecutor
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
    api_instance: Optional[PluginAPI] = None  # 新增：持有API实例以便清理
    active: bool = False

class PluginKernel:
    def __init__(self) -> None:
        self.PLUGIN_DIR = "plugins"
        
        # [解决 A: 线程安全] 引入可重入锁
        self._lock = threading.RLock()
        
        self.context_global: Dict[str, Any] = {
            "version": "3.1 Secure",
            "admin": "Administrator"
        }
        self.context_local: Dict[str, Dict[str, Any]] = {}
        self.plugins_meta: Dict[str, PluginMeta] = {}
        self._events: Dict[str, List[tuple]] = {}
        
        self._executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="EventWorker")
        
        if not os.path.exists(self.PLUGIN_DIR):
            os.makedirs(self.PLUGIN_DIR)

    # --- [解决 A] 线程安全的数据访问接口 ---

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

    # --- 事件系统 ---

    def unregister_events_by_owner(self, owner: str) -> None:
        with self._lock:
            for name in list(self._events.keys()):
                self._events[name] = [
                    (cb, o) for cb, o in self._events[name] if o != owner
                ]
            
    def emit(self, event_name: str, **kwargs: Any) -> None:
        # 获取回调列表快照，避免在迭代时被修改
        callbacks_snapshot = []
        with self._lock:
            if event_name in self._events:
                callbacks_snapshot = self._events[event_name][:] # Copy
        
        for func, owner in callbacks_snapshot:
            self._executor.submit(self._safe_event_call, func, event_name, owner, **kwargs)

    def _safe_event_call(self, func: Callable, event_name: str, owner: str, **kwargs) -> None:
        try:
            func(**kwargs)
        except Exception as e:
            print(f"[!] 事件执行异常 [{owner}] -> {event_name}: {e}")

    # --- 依赖计算与拓扑 ---

    def _scan_plugins(self) -> None:
        # 扫描逻辑保持不变，但为了演示完整性，确保每次重新扫描
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
                        
                        # 更新或新增元数据
                        if name not in self.plugins_meta:
                            self.plugins_meta[name] = PluginMeta(
                                name=name, 
                                path=plugin_path, 
                                dependencies=config.get("dependencies", [])
                            )
                        else:
                            # 重新扫描时更新依赖配置
                            self.plugins_meta[name].dependencies = config.get("dependencies", [])
                            self.plugins_meta[name].path = plugin_path
                    except Exception:
                        pass

    def _resolve_dependencies(self) -> List[str]:
        """计算完整的启动顺序（拓扑排序）"""
        ordered = []
        visited = set()
        visiting = set()

        def visit(name: str):
            if name in visited: return
            if name in visiting: raise Exception(f"循环依赖: {name}")
            if name not in self.plugins_meta: return # 容错：忽略不存在的依赖

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
        """
        [解决 B: 级联重载] 计算反向依赖树
        返回所有依赖于 target_plugin 的插件列表（按依赖层级排序）
        例如：A 被 B 依赖，B 被 C 依赖。输入 A，返回 [B, C]
        """
        dependents = []
        # 构建反向图： { "core": ["security"], ... }
        rev_graph: Dict[str, List[str]] = {}
        for name, meta in self.plugins_meta.items():
            for dep in meta.dependencies:
                if dep not in rev_graph: rev_graph[dep] = []
                rev_graph[dep].append(name)
        
        # BFS 查找所有受影响节点
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
        
        # 对受影响的节点进行拓扑排序，确保卸载顺序正确
        # 这里简化处理：只要按照依赖顺序的逆序即可
        # 使用现有的 _resolve_dependencies 逻辑对 dependents 重新排序
        full_order = self._resolve_dependencies() # 这是一个 [Base, ..., Leaf] 的列表
        
        # 过滤出 dependents 并保持 full_order 中的顺序
        sorted_dependents = [p for p in full_order if p in dependents]
        
        return sorted_dependents

    # --- 插件生命周期 ---

    def load_plugin(self, name: str) -> bool:
        meta = self.plugins_meta.get(name)
        if not meta: return False
        if meta.active: return True

        try:
            unique_module_name = f"mk_plugin_{name}"
            init_path = os.path.join(meta.path, "__init__.py")
            spec = importlib.util.spec_from_file_location(unique_module_name, init_path)
            
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[unique_module_name] = mod
                spec.loader.exec_module(mod)
                meta.module = mod
                
                if hasattr(mod, "Plugin"):
                    # 传入 Kernel 实例，API 内部会弱引用
                    api = PluginAPI(self, name, meta.path)
                    meta.api_instance = api # 保存 API 引用以便清理
                    
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
        meta = self.plugins_meta.get(name)
        if not meta or not meta.active: return

        print(f"[*] 正在卸载: {name}...")
        
        # 1. 停止插件
        try:
            if meta.instance:
                meta.instance.stop()
        except Exception as e:
            print(f"[!] Stop异常: {e}")

        # 2. [解决 D] 清理 API 托管的资源 (线程等)
        if meta.api_instance:
            meta.api_instance._cleanup()

        # 3. 清理事件监听 (加锁操作)
        self.unregister_events_by_owner(name)
        
        # 4. 清理 Local Storage (加锁操作)
        with self._lock:
            if name in self.context_local:
                del self.context_local[name]

        # 5. 移除 sys.modules
        unique_module_name = f"mk_plugin_{name}"
        if unique_module_name in sys.modules:
            del sys.modules[unique_module_name]
            
        # 6. 重置元数据
        meta.active = False
        meta.instance = None
        meta.module = None
        meta.api_instance = None
        print(f"[-] 卸载完成: {name}")

    def reload_plugin(self, name: str) -> None:
        """
        [解决 B: 级联重载] 智能重载
        流程：
        1. 找到所有依赖此插件的上层插件 (Dependents)
        2. 按依赖树逆序（先叶子节点）卸载所有受影响插件
        3. 卸载并重载目标插件
        4. 按依赖树正序（先基础节点）重新加载所有受影响插件
        """
        if name not in self.plugins_meta:
            print(f"[!] 未知插件: {name}")
            return

        print(f"\n[Refactor] 准备级联重载: {name}")
        
        # 1. 计算受影响的插件
        dependents = self._get_dependent_tree(name)
        if dependents:
            print(f"[*] 检测到依赖链: {name} <- {', '.join(dependents)}")
        
        # 2. 逆序卸载 (先卸载 Security, 再卸载 Core)
        # dependents 已经是按 [Base -> Leaf] 排序，所以卸载要反过来
        for dep_name in reversed(dependents):
            self.unload_plugin(dep_name)
            
        # 3. 卸载目标
        self.unload_plugin(name)
        
        # --- 刷新元数据 ---
        self._scan_plugins()
        
        # 4. 重载目标
        if self.load_plugin(name):
            # 5. 正序恢复依赖者
            for dep_name in dependents:
                print(f"[*] 正在恢复依赖插件: {dep_name}")
                if not self.load_plugin(dep_name):
                    print(f"[!] 恢复失败: {dep_name} (可能因 API 变更导致不兼容)")
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
        # 依赖树逆序关闭
        # 简单逆转 active_plugins 可能不准确，最好根据拓扑序逆转
        topo_order = self._resolve_dependencies()
        shutdown_order = [p for p in reversed(topo_order) if p in active_plugins]
        
        for name in shutdown_order:
            self.unload_plugin(name)
        self._executor.shutdown(wait=False)

# --- 主程序 ---
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
            elif cmd == "data":
                # 调试打印，不需要锁（只读 snapshot 即可，或者稍微不一致也没事）
                print("Global:", json.dumps(kernel.context_global, indent=2))
                print("Local:", json.dumps(kernel.context_local, indent=2, default=str))
            elif cmd == "emit":
                if len(raw) > 1:
                    kernel.emit(raw[1], msg="Manual trigger")
                    print("事件已分发")
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
