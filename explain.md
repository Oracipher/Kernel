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
from typing import Any, TYPE_CHECKING

# 使用 TYPE_CHECKING 避免循环导入，只用于类型提示
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
from typing import Dict, List, Any, Callable, Set
from dataclasses import dataclass

from interface import IPlugin
from api import PluginAPI

# 定义一个数据类来保存插件元数据
@dataclass
class PluginMeta:
    name: str
    path: str
    dependencies: List[str]
    module: Any = None
    instance: Any = None

class PluginKernel:
    def __init__(self) -> None:
        self.PLUGIN_DIR = "plugins"
        self.context: Dict[str, Any] = {
            "version": "2.0 Pro",
            "admin": "Administrator",
            "data": []
        }
        # 存储插件元数据：name -> PluginMeta
        self.plugins_meta: Dict[str, PluginMeta] = {}
        self._events: Dict[str, List[Callable]] = {}
        
        if not os.path.exists(self.PLUGIN_DIR):
            os.makedirs(self.PLUGIN_DIR)
    
    # --- 事件系统 ---
    def on(self, event_name: str, callback_func: Callable[..., Any]) -> None:
        if event_name not in self._events:
            self._events[event_name] = []
        self._events[event_name].append(callback_func)
        
    def emit(self, event_name: str, **kwargs: Any) -> None:
        if event_name in self._events:
            for func in self._events[event_name]:
                try:
                    func(**kwargs)
                except Exception as e:
                    print(f"[!] 事件异常 ({event_name}): {e}")
                    traceback.print_exc()

    # --- 核心依赖与加载逻辑 ---

    def _scan_plugins(self) -> None:
        """第一步：扫描目录，读取 config.json，构建元数据"""
        print("[*] 正在扫描插件目录...")
        self.plugins_meta.clear()
        
        for entry in os.listdir(self.PLUGIN_DIR):
            plugin_path = os.path.join(self.PLUGIN_DIR, entry)
            # 只处理文件夹
            if os.path.isdir(plugin_path):
                config_file = os.path.join(plugin_path, "config.json")
                init_file = os.path.join(plugin_path, "__init__.py")
                
                if os.path.exists(config_file) and os.path.exists(init_file):
                    try:
                        with open(config_file, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                            
                        name = config.get("name", entry)
                        deps = config.get("dependencies", [])
                        
                        meta = PluginMeta(name=name, path=plugin_path, dependencies=deps)
                        self.plugins_meta[name] = meta
                        print(f"    - 发现插件: {name} (依赖: {deps})")
                    except Exception as e:
                        print(f"[!] 无法读取插件配置 {entry}: {e}")

    def _resolve_dependencies(self) -> List[str]:
        """第二步：计算拓扑排序，返回正确的加载顺序列表"""
        # 结果列表
        ordered: List[str] = []
        # 访问状态：set 用于记录已处理的节点
        visited: Set[str] = set()
        # 正在访问：用于检测循环依赖
        visiting: Set[str] = set()

        def visit(name: str):
            if name in visited:
                return
            if name in visiting:
                raise Exception(f"检测到循环依赖: {name}")
            
            if name not in self.plugins_meta:
                raise Exception(f"缺失依赖插件: {name}")

            visiting.add(name)
            
            # 先递归加载依赖项
            for dep in self.plugins_meta[name].dependencies:
                visit(dep)
            
            visiting.remove(name)
            visited.add(name)
            ordered.append(name)

        # 遍历所有发现的插件
        for name in self.plugins_meta:
            try:
                visit(name)
            except Exception as e:
                print(f"[!] 依赖解析错误: {e}")
                # 可以在这里决定是否跳过该插件，或者直接终止
                
        return ordered

    def _load_and_start_plugin(self, name: str) -> None:
        """第三步：实际加载并启动单个插件"""
        meta = self.plugins_meta.get(name)
        if not meta:
            return

        try:
            # 1. 动态加载包 (Package)
            spec = importlib.util.spec_from_file_location(name, os.path.join(meta.path, "__init__.py"))
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[name] = mod # 注册到 sys.modules
                spec.loader.exec_module(mod)
                meta.module = mod
                
                # 2. 检查是否有 Plugin 类
                if hasattr(mod, "Plugin"):
                    # 注入 API，注意现在传入了 plugin_dir
                    api = PluginAPI(self, name, meta.path)
                    plugin_inst = mod.Plugin(api)
                    
                    if isinstance(plugin_inst, IPlugin):
                        meta.instance = plugin_inst
                        plugin_inst.start()
                        print(f"[+] 插件启动成功: {name}")
                    else:
                        print(f"[!] 错误: {name} 未继承 IPlugin")
                else:
                    print(f"[!] 错误: {name} 中未找到 Plugin 类")
            else:
                print(f"[!] 无法加载模块 spec: {name}")

        except Exception as e:
            print(f"[!] 加载插件 {name} 失败: {e}")
            traceback.print_exc()

    def init_plugins(self) -> None:
        """系统初始化流程"""
        # 1. 扫描
        self._scan_plugins()
        
        # 2. 排序
        try:
            load_order = self._resolve_dependencies()
            print(f"[*] 计算出的加载顺序: {load_order}\n")
            
            # 3. 按顺序加载
            for name in load_order:
                self._load_and_start_plugin(name)
                
        except Exception as e:
            print(f"[FATAL] 初始化插件系统失败: {e}")

    def list_plugins(self) -> List[str]:
        return [name for name, meta in self.plugins_meta.items() if meta.instance is not None]

# --- 主程序 ---
if __name__ == "__main__":
    kernel = PluginKernel()
    kernel.init_plugins()
    
    # 简单的交互循环
    while True:
        try:
            cmd = input("\nKernel> ").strip().lower()
            if cmd == "exit":
                break
            elif cmd == "list":
                print(f"已运行插件: {kernel.list_plugins()}")
            elif cmd == "data":
                print(json.dumps(kernel.context, indent=2, ensure_ascii=False))
        except KeyboardInterrupt:
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
    from interface import IPlugin

    class Plugin(IPlugin):
        def start(self) -> None:
            config = self.api.get_plugin_config()
            version = config.get("version", "0.0")
            
            self.api.log(f"核心系统 (v{version}) 正在启动...")
            
            # 初始化核心数据
            self.api.set_data("core_status", "ONLINE")
            self.api.set_data("max_connections", 100)
            self.api.log("核心数据已初始化")

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
    from interface import IPlugin

    class Plugin(IPlugin):
        def start(self) -> None:
            self.api.log("安全工具正在启动...")
            
            # 检查依赖插件是否已经准备好了数据
            # 如果没有依赖管理，这里可能会读取到 None，导致报错
            core_status = self.api.get_data("core_status")
            
            if core_status == "ONLINE":
                self.api.log("检测到核心系统在线，安全模块挂载成功！")
            else:
                self.api.log("警告：核心系统未就绪！")

        def stop(self) -> None:
            self.api.log("安全工具卸载")
    ```
