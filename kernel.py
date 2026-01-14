import os
import sys
import re
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

# --- 安全审计器 (静态代码检查) ---
class SecurityAuditor(ast.NodeVisitor):
    """
    [安全模块] 代码静态审计
    注意：Python 的动态特性意味着无法通过静态分析完全阻止恶意行为。
    此模块主要作为"代码规范检查"使用，防止无意的危险操作。
    """
    def __init__(self):
        self.errors = []
        # 禁止导入的系统级模块
        self.banned_imports = {'os', 'subprocess', 'shutil', 'sys', 'socket'}
        # 禁止调用的高危函数
        self.banned_calls = {'eval', 'exec', 'system', 'popen', 'spawn'}

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name.split('.')[0] in self.banned_imports:
                self.errors.append(f"Line {node.lineno}: 禁止直接导入系统模块 '{alias.name}'")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module and node.module.split('.')[0] in self.banned_imports:
            self.errors.append(f"Line {node.lineno}: 禁止从系统模块 '{node.module}' 导入")
        self.generic_visit(node)

    def visit_Call(self, node):
        # 检查函数调用，如 eval()
        if isinstance(node.func, ast.Name):
            if node.func.id in self.banned_calls:
                self.errors.append(f"Line {node.lineno}: 禁止调用高危函数 '{node.func.id}'")
        # 检查属性调用，如 os.system()
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
        return [f"语法解析失败: {str(e)}"]

@dataclass
class PluginMeta:
    name: str
    path: str
    version: str = "0.0.0"
    dependencies: List[str] = field(default_factory=list)
    module: Any = None
    instance: Optional[IPlugin] = None
    api_instance: Optional[PluginAPI] = None
    active: bool = False

class PluginKernel:
    def __init__(self) -> None:
        self.PLUGIN_DIR = "plugins"
        # 内核级锁，保护元数据和 Context 读写
        self._lock = threading.RLock()
        
        self.context_global: Dict[str, Any] = {
            "kernel_version": "3.5.0",
            "environment": "production"
        }
        self.context_local: Dict[str, Dict[str, Any]] = {}
        self.plugins_meta: Dict[str, PluginMeta] = {}
        
        # 事件总线: {event_name: [(callback, owner_name), ...]}
        self._events: Dict[str, List[tuple]] = {}
        
        # 异步任务线程池 (仅用于 emit 异步分发)
        self._executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="KernelWorker")
        
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
                if key.startswith("kernel_"):
                    return # 保护内核保留字段
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
                # 过滤掉属于该 owner 的回调
                self._events[name] = [
                    (cb, o) for cb, o in self._events[name] if o != owner
                ]
                # 清理空列表
                if not self._events[name]:
                    del self._events[name]

    # --- 事件系统 ---

    def emit(self, event_name: str, **kwargs: Any) -> List[Future]:
        """
        异步分发：将任务提交到线程池。
        """
        callbacks_snapshot = []
        with self._lock:
            if event_name in self._events:
                callbacks_snapshot = self._events[event_name][:]
        
        futures = []
        for func, owner in callbacks_snapshot:
            # 捕获异常的包装器
            f = self._executor.submit(self._safe_exec, func, event_name, owner, **kwargs)
            futures.append(f)
        return futures

    def sync_call_event(self, event_name: str, timeout: float = 5.0, **kwargs) -> List[Any]:
        """
        同步调用：在当前线程顺序执行。
        优势：避免线程池死锁。
        缺点：如果插件回调阻塞，会卡住调用者。
        """
        callbacks_snapshot = []
        with self._lock:
            if event_name in self._events:
                callbacks_snapshot = self._events[event_name][:]
        
        results = []
        if not callbacks_snapshot:
            return results

        for func, owner in callbacks_snapshot:
            try:
                # 注意：此处未实现严格的函数级超时中断，依赖插件自觉性
                res = func(**kwargs)
                results.append(res)
            except Exception as e:
                print(f"[Kernel Warning] 同步调用异常 [{owner}] -> {event_name}: {e}")
                results.append(e) # 将异常作为结果返回，不中断流程
                
        return results

    def _safe_exec(self, func: Callable, event_name: str, owner: str, **kwargs) -> Any:
        try:
            return func(**kwargs)
        except Exception as e:
            print(f"[Kernel Error] 异步执行异常 [{owner}] -> {event_name}: {e}")
            raise e

    # --- 依赖与版本控制 (修复版) ---

    def _parse_version(self, v_str: str) -> Tuple[int, ...]:
        """1.2.0 -> (1, 2, 0)"""
        try:
            return tuple(map(int, v_str.split('.')))
        except Exception:
            return (0, 0, 0)

    def _check_dep_version(self, req_str: str) -> bool:
        """
        健壮的依赖解析
        支持格式: "pluginA", "pluginA>=1.0.0", "pluginA==2.0", "pluginA<3.0"
        """
        # 正则匹配：名称 + (可选的操作符和版本号)
        # Group 1: Name, Group 2: Op, Group 3: Version
        pattern = r"^([a-zA-Z0-9_\-]+)(?:([<>=!]+)([\d\.]+))?$"
        match = re.match(pattern, req_str.strip())
        
        if not match:
            print(f"[Dep Error] 依赖格式无法解析: {req_str}")
            return False

        name, op, ver_req = match.groups()
        
        if name not in self.plugins_meta:
            return False # 依赖插件完全未加载
        
        meta = self.plugins_meta[name]
        
        # 如果没有指定版本操作符，只要存在即可
        if not op:
            return True

        curr_ver = self._parse_version(meta.version)
        req_ver = self._parse_version(ver_req)

        if op == ">=":
            return curr_ver >= req_ver
        elif op == ">":
            return curr_ver > req_ver
        elif op == "==":
            return curr_ver == req_ver
        elif op == "<=":
            return curr_ver <= req_ver
        elif op == "<":
            return curr_ver < req_ver
        
        return False

    def _resolve_dependencies(self) -> List[str]:
        """拓扑排序解析加载顺序"""
        ordered = []
        visited = set()
        visiting = set()

        def visit(name: str):
            if name in visited:
                return
            if name in visiting:
                raise Exception(f"检测到循环依赖: {name}")
            if name not in self.plugins_meta:
                return

            visiting.add(name)
            meta = self.plugins_meta[name]
            
            for dep_str in meta.dependencies:
                # 提取纯名称用于递归
                dep_match = re.match(r"^([a-zA-Z0-9_\-]+)", dep_str.strip())
                if not dep_match:
                    continue
                dep_name = dep_match.group(1)
                
                # 版本检查
                if not self._check_dep_version(dep_str):
                    raise Exception(f"插件 {name} 的依赖未满足: {dep_str}")
                
                # 递归处理依赖
                visit(dep_name)
                
            visiting.remove(name)
            visited.add(name)
            ordered.append(name)

        # 扫描所有已知插件
        for name in self.plugins_meta:
            # 只有未激活的才需要排队，但为了计算依赖树，通常重新计算
            try: 
                visit(name)
            except Exception as e: 
                print(f"[Dep Error] 忽略插件 {name}: {e}")
        
        return ordered

    def _scan_plugins(self) -> None:
        """扫描目录并刷新元数据"""
        if not os.path.exists(self.PLUGIN_DIR):
            return
        
        for entry in os.listdir(self.PLUGIN_DIR):
            plugin_path = os.path.join(self.PLUGIN_DIR, entry)
            if os.path.isdir(plugin_path):
                config_file = os.path.join(plugin_path, "config.json")
                if os.path.exists(config_file):
                    try:
                        with open(config_file, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                        
                        name = config.get("name", entry)
                        # 保持现有状态 (如果已加载)
                        existing = self.plugins_meta.get(name)
                        
                        self.plugins_meta[name] = PluginMeta(
                            name=name, 
                            path=plugin_path, 
                            version=config.get("version", "0.0.0"),
                            dependencies=config.get("dependencies", []),
                            # 继承之前的运行状态
                            active=existing.active if existing else False,
                            instance=existing.instance if existing else None,
                            api_instance=existing.api_instance if existing else None,
                            module=existing.module if existing else None
                        )
                    except Exception as e:
                        print(f"[Scan Error] 读取配置 {entry} 失败: {e}")

    # --- 插件加载核心 (包含超时控制) ---

    def load_plugin(self, name: str) -> bool:
        meta = self.plugins_meta.get(name)
        if not meta:
            return False
        if meta.active:
            return True

        # 1. 安全审计
        init_path = os.path.join(meta.path, "__init__.py")
        if os.path.exists(init_path):
            issues = scan_code_security(init_path)
            if issues:
                print(f"[Security Block] 插件 {name} 包含可疑代码，已拦截:")
                for i in issues:
                    print(f"  - {i}")
                return False

        try:
            # 2. 动态导入
            unique_mod_name = f"mk_plugin_{name}_{int(time.time())}" # 添加时间戳防止缓存污染
            spec = importlib.util.spec_from_file_location(unique_mod_name, init_path)
            
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[unique_mod_name] = mod
                spec.loader.exec_module(mod)
                
                if hasattr(mod, "Plugin"):
                    # 3. 注入 API
                    api = PluginAPI(self, name, meta.path)
                    meta.api_instance = api
                    meta.module = mod # 保存引用防止被GC
                    
                    inst = mod.Plugin(api)
                    if not isinstance(inst, IPlugin):
                        print(f"[Load Error] {name} 未继承 IPlugin")
                        return False

                    # 4. 超时启动保护
                    # 使用闭包变量来捕获结果
                    result_container = {"success": False, "error": None}
                    
                    def _runner():
                        try:
                            inst.start()
                            result_container["success"] = True
                        except Exception as e:
                            result_container["error"] = e

                    t = threading.Thread(target=_runner, name=f"Loader-{name}", daemon=True)
                    t.start()
                    t.join(timeout=3.0) # 设置3秒硬超时

                    if t.is_alive():
                        print(f"[Timeout] 插件 {name} 启动超时 (>3s)！")
                        print(" -> 正在切断该插件的 API 连接...")
                        # 强制清理 API，使插件内部后续调用失效
                        api._cleanup() 
                        return False
                    
                    if not result_container["success"]:
                        raise result_container["error"] or Exception("启动未返回成功状态")

                    meta.instance = inst
                    meta.active = True
                    print(f"[System] 插件已加载: {name} (v{meta.version})")
                    return True
            
            print(f"[Load Error] {name} 模块格式无效")
            return False
            
        except Exception as e:
            print(f"[FATAL] 加载崩溃 {name}: {e}")
            traceback.print_exc()
            return False

    def unload_plugin(self, name: str) -> None:
        meta = self.plugins_meta.get(name)
        if not meta or not meta.active:
            return

        print(f"[System] 正在卸载: {name}...")
        
        # 1. 调用 stop (带超时保护)
        if meta.instance:
            try:
                def _stopper():
                    meta.instance.stop()
                
                t = threading.Thread(target=_stopper, name=f"Unloader-{name}", daemon=True)
                t.start()
                t.join(timeout=2.0)
                
                if t.is_alive():
                    print(f"[Warn] 插件 {name} 停止方法超时，强制清理资源")
            except Exception as e:
                print(f"[Error] 插件停止时异常: {e}")

        # 2. 清理 API 资源 (关闭后台线程，注销事件)
        if meta.api_instance:
            meta.api_instance._cleanup()

        # 3. 内核层清理
        self.unregister_events_by_owner(name)
        
        with self._lock:
            if name in self.context_local:
                del self.context_local[name]

        # 4. 清理 Python 模块缓存
        # 尝试查找并删除 sys.modules 中的相关项
        keys_to_del = [k for k in sys.modules if f"mk_plugin_{name}" in k]
        for k in keys_to_del:
            del sys.modules[k]

        # 5. 重置元数据
        meta.instance = None
        meta.module = None
        meta.api_instance = None
        meta.active = False
        
        gc.collect() # 强制垃圾回收
        print(f"[System] 卸载完成: {name}")

    def init_system(self) -> None:
        print("[System] 初始化微内核...")
        self._scan_plugins()
        try:
            load_order = self._resolve_dependencies()
            print(f"[System] 解析加载顺序: {load_order}")
            for name in load_order:
                self.load_plugin(name)
        except Exception as e:
            print(f"[System Error] 初始化失败: {e}")

    def shutdown(self):
        print("\n[System] 系统正在关闭...")
        # 逆序卸载，保证依赖者先退出
        active_plugins = [p for p, m in self.plugins_meta.items() if m.active]
        # 简单逆序，更严格的做法是重新计算反向依赖图
        for name in reversed(active_plugins):
            self.unload_plugin(name)
        
        self._executor.shutdown(wait=False)
        print("[System] Bye.")

if __name__ == "__main__":
    k = PluginKernel()
    k.init_system()
    
    # CLI 交互
    while True:
        try:
            raw = input("\nKernel> ").strip()
            if not raw:
                continue
            parts = raw.split()
            cmd = parts[0].lower()
            
            if cmd == "exit":
                k.shutdown()
                break
            elif cmd == "list":
                print(f"{'Name':<20} {'Version':<10} {'Status':<10}")
                print("-" * 45)
                for n, m in k.plugins_meta.items():
                    status = "ACTIVE" if m.active else "STOPPED"
                    print(f"{n:<20} {m.version:<10} {status:<10}")
            elif cmd == "reload":
                if len(parts) > 1:
                    target = parts[1]
                    k.unload_plugin(target)
                    k._scan_plugins()
                    k.load_plugin(target)
            elif cmd == "emit":
                # 测试命令: emit test_event key=val
                if len(parts) > 1:
                    evt = parts[1]
                    kwargs = {}
                    for pair in parts[2:]:
                        if '=' in pair:
                            k, v = pair.split('=', 1)
                            kwargs[k] = v
                    print(f"Calling sync event: {evt}")
                    res = k.sync_call_event(evt, **kwargs)
                    print(f"Result: {res}")
            else:
                print("Unknown command. Try: list, reload <name>, emit <event>, exit")
                
        except KeyboardInterrupt:
            k.shutdown()
            break
        except Exception as e:
            print(f"CLI Error: {e}")