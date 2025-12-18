简要回答：
这是 `uv` 工作区模式的配置要求。当你在根项目的 `dependencies` 中列出了工作区成员时，你必须在 `[tool.uv.sources]` 表中显式声明它们为 `workspace = true`，以便 `uv` 知道从本地工作区解析它们，而不是去 PyPI 查找。

## [WIP] fix(build): 在根配置中显式注册工作区依赖源

### 错误分析
错误 `cascade-interfaces is included as a workspace member, but is missing an entry in tool.uv.sources` 指出，虽然我们在 `[tool.uv.workspace]` 中定义了成员路径，但没有明确告诉 `uv` 的解析器在解析根项目的依赖列表时使用这些本地成员。

### 用户需求
修复构建配置，使 `uv` 能够正确解析并安装本地包。

### 评论
这是 `uv` 显式配置原则的体现。虽然略显繁琐，但它确保了依赖解析来源的绝对清晰，避免了隐式的“魔法”行为。

### 目标
在根目录 `pyproject.toml` 中添加 `[tool.uv.sources]` 配置块，将所有内部包标记为 `workspace = true`。

### 基本原理
配置 `[tool.uv.sources]` 将建立依赖名称（如 `cascade-interfaces`）与工作区成员之间的逻辑链接。这是 `uv` 在开发模式下正确链接本地包的关键步骤。

### 标签
#intent/fix #flow/ready #priority/critical #comp/build #concept/config #scope/dx #ai/instruct #task/domain/devops #task/object/monorepo-config #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 添加 `tool.uv.sources` 配置
我们在 `[tool.uv.workspace]` 定义之后插入源映射配置。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
[tool.uv.workspace]
members = ["packages/*"]

[tool.hatch.workspaces]
~~~~~
~~~~~toml
[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
cascade-interfaces = { workspace = true }
cascade-runtime = { workspace = true }
cascade-py = { workspace = true }
cascade-cli = { workspace = true }

[tool.hatch.workspaces]
~~~~~

### 下一步建议
再次运行 `uv pip install -e ".[dev]"`。此时所有的依赖解析路径都已打通，安装应该能够成功完成。
