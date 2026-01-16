# Python Micro Kernel

## 说明

explain - 解释
direct  - 说明

success - 成功执行

Notice  - 注意错误
warn    - 警告错误
Error   - 严重错误


## 想法

1. 使用类型提示信息type hints
   
```python
from types import ModuleType
from api import PluginAPI
from interface import IPlugin

    def _check_and_start(self, loaded_module: ModuleType, plugin_name: str):
        if hasattr(loaded_module, "Plugin"):
            try:
                plugin_api: PluginAPI = PluginAPI(self, plugin_name)

                plugin_instance = loaded_module.Plugin(plugin_api)

```

2. 或者注释多写一点，注释驱动
   
```python
def _check_and_start(self, mod, name):
        # mod (module): 就是那个 .py 文件
        # name: 就是那个文件的名字，比如 "hello"
        
        # 步骤 1: 看看文件里有没有写 class Plugin
        if hasattr(mod, "Plugin"):
            try:
                # 步骤 2: 准备 API (相当于给新员工配的工作手机)
                # 里面存了两个信息：1.我是谁(self/内核)，2.它是谁(name)
                plugin_api = PluginAPI(self, name)
                
                # 步骤 3: 实例化 (相当于正式招人入职)
                # mod.Plugin 是类(图纸)，加括号()变成实例(活人)
                # 把工作手机(api)塞给它
                plugin_instance = mod.Plugin(plugin_api)
                
                # 步骤 4: 身份检查 (防止有人混水摸鱼)
                # 必须是 IPlugin 的后代才能入职
                if not isinstance(plugin_instance, IPlugin):
                    print(f"警告: {name} 没按规矩写代码！")
                
                # 步骤 5: 存入花名册 (关键！否则以后找不到它了)
                self.loaded_plugins[name] = plugin_instance
                
                # 步骤 6: 按下启动按钮
                plugin_instance.start()
                
                print(f"[+] {name} 启动成功")

            except Exception as e:
                print(f"启动出错了: {e}")
```

3. 写一份中英文对照表

|英文代码|脑内中文翻译|形象理解|
|:---:|:---:|:---:|
|Kernel|核心 / 司令部|大脑，管所有事的。|
|Plugin|插件 / 小兵|干具体活的员工。|
|Context|环境 / 公告栏|大家都能看到的数据（字典）。|
|Emit|发射 / 广播|拿个大喇叭喊话：“出事啦！”|
|Handler|处理者|听到喇叭后，跑过来干活的那个函数。|
|Instance|实例 / 实体|活的东西。类(Class)是死图纸，Instance 是照着图纸造出来的活人。|


## 已实现

| 功能模块 | 具体特性 | 点评 (设计价值) |
| :--- | :--- | :--- |
| **插件加载机制** | **动态发现与导入** | 利用 `importlib` 和 `sys.modules` 实现了类似于 Python 标准库的动态加载，且支持自动扫描 `plugins` 目录。这是微内核的基石。 |
| **热重载 (Hot Reload)** | **代码热更新** | 实现了 `stop` -> `reload` -> `start` 的完整闭环。这在开发阶段非常有用，允许在不重启主程序的情况下更新插件逻辑。 |
| **安全隔离层** | **API 中间件 (Facade模式)** | **这是最大的亮点**。通过 `PluginAPI` 隔离了 `Kernel` 实例，插件无法直接修改内核数据（如删除 `loaded_plugins`），实现了“最小权限原则”。 |
| **通信机制** | **事件总线 (Event Bus)** | 实现了基础的发布/订阅模式 (`on` / `emit`)。插件之间不需要互相 import 就能通信，实现了**高度解耦**。 |
| **契约约束** | **接口类 (ABC Interface)** | 使用 `abc` 模块定义了 `IPlugin`，强制要求插件实现 `start` 和 `stop`。保证了内核调用插件时的稳定性。 |
| **生命周期管理** | **初始化与销毁** | 明确了插件的生与死。在 `stop` 中给予插件清理资源（虽然目前只是打印）的机会，防止内存泄漏或句柄残留。 |
| **交互界面** | **CLI 命令行** | 提供了一个简单的 REPL 环境，方便开发者实时调试、查看状态和手动控制插件。 |

## 未实现

Python 无法强制杀死线程：
在 api.py 中，尝试 t.join(timeout=1.0)。如果插件里写了一个 while True: pass 且不检查 api.is_active，内核是无法强制停止该线程的。这是 Python threading 模块的底层限制（没有 Thread.terminate()）。


模块卸载的“不干净”：
sys.modules 的清理极其复杂。虽然删除了引用，但如果其他地方（比如闭包、 traceback 对象）引用了插件里的对象，内存依然不会释放。Python 并不擅长“热卸载”代码。


1. 热重载的深坑 (sys.modules 清理)
你在 unload_plugin 中做了：
code
```Python
keys_to_del = [k for k in sys.modules if f"mk_plugin_{name}" in k]
for k in keys_to_del: del sys.modules[k]
```
风险：Python 的模块导入机制非常复杂。仅仅删除 sys.modules 是不够的。如果其他插件或内核 import 了该插件中的类（例如 from plugins.A import SomeClass），即使你删除了模块，内存中旧类的引用依然存在。
建议：在微内核架构中，尽量禁止插件之间的直接 import，强制通过 kernel.get_data 或 api.call (RPC风格) 通信，这样才能真正实现无痛热重载。
2. 同步事件的阻塞风险
code
```Python
def sync_call_event(self, ...):
    # ...
    res = func(**kwargs) # 直接在主线程执行
```
风险：如果插件 B 的回调函数里写了 time.sleep(100) 或者死循环，整个内核的主线程就会被卡死，CLI 也会无响应。
建议：即使是同步调用，也可以考虑设置超时机制（虽然在 Python 线程中强制 kill 很难，但可以在架构设计上引入 asyncio 协程来更好地处理超时）。
3. 安全沙箱的局限性
虽然你用了 ast 检查，但 Python 是一门动态语言。
code
```Python
# 绕过示例
op = getattr(importlib.import_module("o" + "s"), "sys" + "tem")
op("rm -rf /")
```
AST 很难检测动态生成的字符串调用。
建议：不要通过代码审计来保证 100% 安全。真正的沙箱需要操作系统级别的隔离（如 Docker 容器或 WebAssembly）。对于 Python 内部沙箱，你的做法作为“防君子不防小人”的规范检查是合格的

线程无法真正“杀死”：
在 _cleanup 中，代码尝试等待线程结束。如果插件写了 while True: pass 且不检查 api.is_active，内核是无法强制终止它的。
进阶思路：如果需要绝对的隔离和强杀能力，未来可以考虑使用 multiprocessing 替代 threading，但这会极大增加数据共享的复杂度（需要 IPC）。
沙箱逃逸：
SecurityAuditor 禁止了 import os，但如果用户使用 __import__("o"+"s") 或者通过 object.__subclasses__ 等黑魔法，依然可以绕过检查。这是 Python 做沙箱的天然劣势。
卸载的“不干净”：
虽然代码尝试了 del sys.modules[...] 和 gc.collect()，但在 Python 中，如果其他模块引用了被卸载插件的对象，内存是无法完全释放的（这个代码已经尽力做了最好）。