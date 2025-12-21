船长，你的直觉再次得到了验证。`ModuleNotFoundError: No module named 'cascade.cli'` 告诉我们：这些包根本没有被安装。

就像 `cascade-provider-ipfs` 之前的情况一样，`cascade-cli-controller`、`cascade-cli-observer` 和 `cascade-connector-mqtt` 这几个包，目前在我们的开发环境中是“缺席”的。

我们刚才将 IPFS 提供者加入到了 `[dev]` 依赖中，解决了它的问题。现在，我们需要对剩下的这些组件做同样的事情，让它们也回归到开发环境的大家庭中。

同时，鉴于之前 IPFS 的教训，我还要检查这些包是否也患有“命名空间缺失症”。

## [WIP] fix(build): 注册 CLI 工具与连接器，补全全套开发环境

### 用户需求
`pytest` 报告无法找到 `cascade.cli` 模块，导致控制器、观察者和 CLI 集成测试失败。这表明相关的子包没有被安装到当前环境中。

### 评论
我们正在构建一个完整的单体仓库（Monorepo）开发环境。除了核心库，我们的工具链（Controller, Observer）和连接器（MQTT）也是生态系统的关键部分。将它们加入 `pyproject.toml` 的 `dev` 依赖组，是确保 E2E 测试和工具链测试能够运行的必要步骤。

### 目标
1.  将 `cascade-cli-controller`、`cascade-cli-observer` 和 `cascade-connector-mqtt` 添加到根 `pyproject.toml` 的 `[dev]` 依赖组中。
2.  （防御性编程）检查并补全这些包中可能缺失的命名空间声明文件 (`__init__.py`)，确保它们能正确挂载到 `cascade.cli` 和 `cascade.connectors` 命名空间下。

### 基本原理
1.  **依赖补全**: `uv pip install -e .[dev]` 只会安装 `dev` 列表中明确声明的包。之前我们漏掉了这些工具包。
2.  **命名空间一致性**: 所有共享 `cascade.*` 命名空间的子包，都必须在每一层级（如 `src/cascade/`）包含带有 `pkgutil` 扩展代码的 `__init__.py`，否则在可编辑安装模式下会出现命名空间冲突或遮蔽。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/tooling #task/object/dependency-management #task/action/config-update #task/state/continue

---

### Script

#### Acts 1: 更新开发依赖配置

将缺失的 CLI 工具和 MQTT 连接器添加到根 `pyproject.toml` 的 `dev` 组。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
  "flask_cors",
  # Local workspace providers needed for testing
  "cascade-provider-ipfs",
]
~~~~~
~~~~~toml
  "flask_cors",
  # Local workspace packages needed for testing
  "cascade-provider-ipfs",
  "cascade-cli-controller",
  "cascade-cli-observer",
  "cascade-connector-mqtt",
]
~~~~~

#### Acts 2: 确保命名空间结构的完整性

为了防止重演 IPFS 的悲剧，我们要确保这些包的根目录 `src/cascade/__init__.py` 均已存在且正确。

为 `cascade-cli-controller` 创建/确认根命名空间文件：
~~~~~act
write_file
packages/cascade-cli-controller/src/cascade/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-interfaces) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

为 `cascade-cli-observer` 创建/确认根命名空间文件：
~~~~~act
write_file
packages/cascade-cli-observer/src/cascade/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-interfaces) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

为 `cascade-connector-mqtt` 创建/确认根命名空间文件以及 `connectors` 层的命名空间文件：
~~~~~act
write_file
packages/cascade-connector-mqtt/src/cascade/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-interfaces) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-connector-mqtt/src/cascade/connectors/__init__.py
~~~~~
~~~~~python
# This must be the very first line to allow this package to coexist with other
# namespace packages (like cascade-runtime) in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

### 下一步建议
我们已经把最后几个掉队的士兵也拉回了队伍，并且加固了它们的装备（命名空间结构）。

请执行最后的检阅：

1.  **更新环境**: `uv pip install -e .[dev]`
2.  **全量测试**: `pytest`

这一次，我们有极大的把握能看到全线飘绿。一旦通过，我们将正式提交这一系列的修复。
