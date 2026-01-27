
# PyMicroKernel (PMK) 🔌

> 一个轻量级、零依赖的 Python 微内核架构（Microkernel Architecture）参考实现。

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Architecture](https://img.shields.io/badge/Architecture-MicroKernel-orange.svg)]()

## 📖 简介

**PyMicroKernel** 是一个展示如何构建**插件化系统**的教学级框架。它演示了现代软件架构中的核心概念：关注点分离、依赖注入、沙箱隔离以及热重载机制。

通过这个项目，你可以学习到：
- 如何利用 Python 的 `importlib` 实现**动态模块加载**。
- 如何设计**沙箱层 (Facade)** 来隔离核心数据与插件逻辑。
- 如何实现**热重载 (Hot Reload)**，在不重启内核的情况下更新代码。
- 如何使用**抽象基类 (ABC)** 强制执行接口契约。

## ✨ 核心特性

- **🛡️ 安全沙箱 (Omni API)**: 插件无法直接触碰内核。所有交互通过 `Omni` 代理进行，核心数据（如 admin/config）受读写保护。
- **🔄 热重载 (Hot Reloading)**: 支持在运行时重新加载修改后的插件代码，无需重启进程。
- **⚡ 事件总线 (Event Bus)**: 内置轻量级发布/订阅系统，实现插件间的解耦通信。
- **🔐 数据隔离**: 使用 `deepcopy` 防止插件对全局上下文（Context）进行脏写或引用污染。
- **📝 交互式 Shell**: 内置类似操作系统的命令行界面，用于管理插件生命周期。

## 🏗️ 系统架构

```mermaid
graph TD
    User[用户/Shell] --> Kernel[MicroKernel (核心)]
    Kernel -->|注入 API| PluginA[插件 A]
    Kernel -->|注入 API| PluginB[插件 B]
    
    subgraph Sandbox [沙箱层 / Omni]
        PluginA -.->|调用| OmniA[Omni 实例 A]
        PluginB -.->|调用| OmniB[Omni 实例 B]
    end
    
    OmniA -->|安全访问| Context[全局上下文]
    OmniB -->|安全访问| Context
```

## 🚀 快速开始

### 1. 启动内核
直接运行 `kernel.py` 进入交互式 Shell：

```bash
python kernel.py
```

### 2. Shell 命令指南
内核启动后，你可以输入以下命令进行管理：

| 命令 | 参数 | 描述 |
| :--- | :--- | :--- |
| `list` | 无 | 列出当前内存中已加载的所有插件。 |
| `load` | `<filename>` | 从 `plugins/` 目录加载新插件 (例如: `load hello`)。 |
| `reload`| `<name>` | **热重载**指定插件。修改代码后直接执行，立即生效。 |
| `stop` | `<name>` | 停止插件运行并将其从内存中卸载。 |
| `data` | 无 | 查看当前的全局上下文数据 (JSON 格式)。 |
| `exit` | 无 | 优雅停止所有插件并退出程序。 |

## 🔌 插件开发指南

在 `plugins/` 目录下创建一个 `.py` 文件（例如 `demo.py`）。一个标准的插件必须继承自 `Proot` 并实现 `start` 和 `stop` 方法。

```python
# plugins/demo.py
from interface import Proot

class Plugin(Proot):
    def start(self):
        # 使用 self.api (Omni) 与内核交互，而不是直接 print
        self.api.log("Demo 插件已启动！")
        
        # 读取全局数据 (安全拷贝)
        user = self.api.get_data("admin")
        self.api.log(f"当前管理员: {user}")
        
        # 注册事件监听
        self.api.on("user_login", self.handle_login)
        
        # 写入/追加数据
        self.api.append_data("data", "Demo Plugin Loaded")

    def stop(self):
        self.api.log("Demo 插件正在停止...")

    def handle_login(self, **kwargs):
        self.api.log(f"检测到登录事件: {kwargs}")
```

然后在内核 Shell 中输入 `load demo` 即可运行。

## 📂 项目结构

```text
.
├── kernel.py       # [核心] 类加载器、事件总线、主循环
├── api.py          # [接口] 暴露给插件的沙箱 API (Facade)
├── interface.py    # [契约] 定义插件必须实现的抽象基类 (Protocol)
└── plugins/        # [目录] 在此处存放你的插件文件 (.py)
    └── ...
```

## ⚠️ 设计哲学与限制

*   **数据安全**: `api.py` 中的 `get_data` 默认返回数据的**深拷贝**。这虽然增加了内存开销，但对于防止插件无意间修改内核状态至关重要。
*   **权限控制**: `version`, `admin`, `config` 等键被标记为 `protected`，插件无法通过 `set_data` 修改它们。
*   **同步模型**: 目前事件总线是同步调用的。如果某个插件的回调函数阻塞，将会阻塞整个内核 Shell。

## 🤝 贡献

欢迎提交 Pull Request！如果你对**异步事件驱动**或**更细粒度的权限控制**感兴趣，请直接 Fork 本项目。

## 📄 许可证

MIT License

