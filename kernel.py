# kernel.py
import os
import sys
import json
import importlib
import importlib.util
import traceback
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Dict, List, Any, Callable, Set, Optional

from interface import IPlugin
from api import PluginAPI

@dataclass
class PluginMeta:
    name: str
    path: str
    dependencies: List[str]
    module: Any = None
    instance: Optional[IPlugin] = None
    active: bool = False

class PluginKernel:
    def __init__(self) -> None:
        self.PLUGIN_DIR = "plugins"
        
        # 改进：分离全局上下文和局部上下文
        self.context_global: Dict[str, Any] = {
            "version": "3.0 Ultra",
            "admin": "Administrator"
        }
        self.context_local: Dict[str, Dict[str, Any]] = {}
        
        self.plugins_meta: Dict[str, PluginMeta] = {}
        
        # 改进：事件字典结构 {event_name: [(callback, owner_plugin_name)]}
        self._events: Dict[str, List[tuple]] = {}
        
        # 改进：引入线程池处理事件
        self._executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="EventWorker")
        
        if not os.path.exists(self.PLUGIN_DIR):
            os.makedirs(self.PLUGIN_DIR)

    # --- 增强的事件系统 ---

    def register_event(self, event_name: str, callback: Callable, owner: str) -> None:
        if event_name not in self._events:
            self._events[event_name] = []
        self._events[event_name].append((callback, owner))

    def unregister_events_by_owner(self, owner: str) -> None:
        """卸载插件时，清理其注册的所有事件回调"""
        for name in list(self._events.keys()):
            # 过滤掉属于该 owner 的回调
            self._events[name] = [
                (cb, o) for cb, o in self._events[name] if o != owner
            ]
            
    def emit(self, event_name: str, **kwargs: Any) -> None:
        """非阻塞事件分发"""
        if event_name in self._events:
            for func, owner in self._events[event_name]:
                # 提交到线程池执行
                self._executor.submit(self._safe_event_call, func, event_name, owner, **kwargs)

    def _safe_event_call(self, func: Callable, event_name: str, owner: str, **kwargs) -> None:
        try:
            func(**kwargs)
        except Exception as e:
            print(f"[!] 事件执行异常 [{owner}] -> {event_name}: {e}")

    # --- 核心生命周期管理 ---

    def _scan_plugins(self) -> None:
        # (保持原逻辑，略作简化)
        # 实际生产中这里应该只扫描新发现的插件，避免覆盖已加载的元数据
        if not self.plugins_meta: 
            print("[*] 正在扫描插件目录...")
        
        for entry in os.listdir(self.PLUGIN_DIR):
            plugin_path = os.path.join(self.PLUGIN_DIR, entry)
            if os.path.isdir(plugin_path):
                config_file = os.path.join(plugin_path, "config.json")
                if os.path.exists(config_file):
                    try:
                        with open(config_file, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                        name = config.get("name", entry)
                        
                        # 只有未加载时才添加元数据
                        if name not in self.plugins_meta:
                            meta = PluginMeta(
                                name=name, 
                                path=plugin_path, 
                                dependencies=config.get("dependencies", [])
                            )
                            self.plugins_meta[name] = meta
                    except Exception:
                        pass

    def _resolve_dependencies(self) -> List[str]:
        # (保持原逻辑，拓扑排序)
        ordered = []
        visited = set()
        visiting = set()

        def visit(name: str):
            if name in visited: return
            if name in visiting: raise Exception(f"循环依赖: {name}")
            if name not in self.plugins_meta: raise Exception(f"缺失依赖: {name}")

            visiting.add(name)
            for dep in self.plugins_meta[name].dependencies:
                visit(dep)
            visiting.remove(name)
            visited.add(name)
            ordered.append(name)

        for name in self.plugins_meta:
            if not self.plugins_meta[name].active: # 只计算未激活的或重新计算
                try:
                    visit(name)
                except Exception as e:
                    print(f"[!] 依赖错误 {name}: {e}")
        return ordered

    def load_plugin(self, name: str) -> bool:
        """加载并启动插件（增强版）"""
        meta = self.plugins_meta.get(name)
        if not meta:
            print(f"[!] 插件元数据不存在: {name}")
            return False
        
        if meta.active:
            print(f"[-] 插件已运行: {name}")
            return True

        print(f"[*] 正在加载: {name}...")
        try:
            # 改进1: 防止污染 sys.modules，添加前缀
            unique_module_name = f"mk_plugin_{name}"
            
            init_path = os.path.join(meta.path, "__init__.py")
            spec = importlib.util.spec_from_file_location(unique_module_name, init_path)
            
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[unique_module_name] = mod # 注册唯一名称
                spec.loader.exec_module(mod)
                meta.module = mod
                
                if hasattr(mod, "Plugin"):
                    api = PluginAPI(self, name, meta.path)
                    inst = mod.Plugin(api)
                    
                    if isinstance(inst, IPlugin):
                        # 改进2: 容错启动
                        try:
                            inst.start()
                            meta.instance = inst
                            meta.active = True
                            print(f"[+] 启动成功: {name}")
                            return True
                        except Exception as e:
                            print(f"[!] {name}.start() 抛出异常: {e}")
                            print("    -> 正在回滚...")
                            try: inst.stop() 
                            except: pass
                            return False
                    else:
                        print(f"[!] 错误: Plugin 类未继承 IPlugin")
                else:
                    print(f"[!] 错误: 未找到 Plugin 类")
            return False
            
        except Exception as e:
            print(f"[FATAL] 加载过程崩溃 {name}: {e}")
            traceback.print_exc()
            return False

    def unload_plugin(self, name: str) -> None:
        """新增：卸载插件"""
        meta = self.plugins_meta.get(name)
        if not meta or not meta.active:
            print(f"[-] 插件未运行或不存在: {name}")
            return

        print(f"[*] 正在卸载: {name}...")
        
        # 1. 停止插件
        try:
            if meta.instance:
                meta.instance.stop()
        except Exception as e:
            print(f"[!] 停止插件出错: {e}")

        # 2. 清理事件监听
        self.unregister_events_by_owner(name)
        
        # 3. 清理上下文数据 (Local scope)
        if name in self.context_local:
            del self.context_local[name]

        # 4. 移除 sys.modules (允许文件修改后重载生效)
        unique_module_name = f"mk_plugin_{name}"
        if unique_module_name in sys.modules:
            del sys.modules[unique_module_name]
            
        # 5. 重置元数据
        meta.active = False
        meta.instance = None
        meta.module = None
        print(f"[-] 卸载完成: {name}")

    def reload_plugin(self, name: str) -> None:
        """新增：热重载"""
        self.unload_plugin(name)
        # 简单的重载逻辑：重新读取配置并加载
        # 注意：这里未处理反向依赖（如果 Core 重载，依赖它的 Security 也应该重启）
        # 生产环境需要递归卸载依赖树，这里演示单体重载
        self._scan_plugins() 
        self.load_plugin(name)

    def init_system(self) -> None:
        self._scan_plugins()
        order = self._resolve_dependencies()
        for name in order:
            self.load_plugin(name)

    def shutdown(self):
        print("\n[*] 系统正在关闭...")
        # 逆序停止
        active_plugins = [p for p, m in self.plugins_meta.items() if m.active]
        for name in reversed(active_plugins):
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
                print("Global:", json.dumps(kernel.context_global, indent=2))
                print("Local:", json.dumps(kernel.context_local, indent=2, default=str))
            elif cmd == "emit":
                # 测试异步事件
                if len(raw) > 1:
                    kernel.emit(raw[1], msg="Manual trigger")
                    print("事件已分发(异步)")
        except KeyboardInterrupt:
            kernel.shutdown()
            break