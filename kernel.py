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