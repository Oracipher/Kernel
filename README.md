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

1. 依赖管理： 如果插件A依赖插件B的处理
2. 配置管理： 每个插件如何拥有自己独立的配置文件
3. 插件不应该只有一个文件，而允许为一个文件夹
4. **“并发模型”**
5. **“错误隔离”**

| 待升级模块 | 建议功能点 | 分析 (为什么要这么做？) |
| :--- | :--- | :--- |
| **并发模型** | **异步/线程支持** | **当前最致命的问题**。目前所有逻辑都在主线程。如果一个插件的 `start()` 里写了 `time.sleep(10)`，整个内核和 CLI 都会卡死。未来需要引入 `asyncio` 或 `threading` 来运行插件。 |
| **配置管理** | **外部配置文件** | 目前配置硬编码在 `kernel.context`。建议支持 `config.yaml` 或 `.env` 文件加载，并让插件拥有读取自己专属配置的能力（如 `api.get_config("plugin_name.key")`）。 |
| **元数据管理** | **Manifest (清单) 文件** | 目前插件名主要靠文件名推断。建议每个插件目录下有一个 `info.json`，定义插件名、版本、**依赖关系**（Dependency）和作者信息。 |
| **依赖注入与管理** | **加载顺序控制** | 如果插件 A 依赖 插件 B 的数据，目前主要靠文件名排序加载，不可靠。未来应实现“DAG（有向无环图）拓扑排序”来决定加载顺序。 |
| **异常隔离加强** | **沙箱化运行** | 目前虽然捕获了异常，但如果插件发生段错误（C扩展）或死循环，内核依然脆弱。虽然 Python 很难做完美沙箱，但可以考虑子进程（Subprocess）模式运行高危插件。 |
| **事件系统增强** | **优先级与返回值** | 目前 `emit` 只是广播。未来可以支持：1. 监听器优先级（谁先处理）；2. 事件拦截（阻断传播）；3. 获取监听器的返回值（用于插件间的数据请求）。 |
| **接口强校验** | **强制类型检查** | 目前 `_check_and_start` 中如果插件没继承接口只是打印警告。建议在检测到不合规插件时，**直接拒绝加载**，严格执行契约。 |
| **日志系统** | **结构化日志** | 目前使用 `print`。建议引入 Python 标准库 `logging`，支持日志分级（INFO/ERROR）、写入文件和日志轮转。 |


