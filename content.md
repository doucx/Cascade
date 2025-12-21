抱歉，船长。这是我在使用 `uv` 工具链时的疏忽。

`uv` 在处理 Monorepo 工作区时非常严格：任何在依赖列表（即使是 `dev` 依赖）中引用的本地包，都必须在 `[tool.uv.sources]` 部分显式注册为 `{ workspace = true }`，否则它会试图去 PyPI 寻找它们（或者像现在这样直接报错）。

我们之前添加了依赖，却忘了给它们发“工作区通行证”。

## [WIP] fix(build): 在 uv 配置中注册缺失的工作区成员

### 用户需求
`uv pip install` 失败，提示 `cascade-cli-controller` 等包缺少 `tool.uv.sources` 入口。需要修正 `pyproject.toml` 配置，以便 `uv` 能正确识别并链接这些本地工作区成员。

### 评论
这是使用现代 Python 构建工具（如 `uv`, `hatch`）管理 Monorepo 时的常见配置要求。`dependencies` 声明了“我需要什么”，而 `tool.uv.sources` 声明了“去哪里找”。只有两者匹配，本地开发环境才能闭环。

### 目标
1.  在根 `pyproject.toml` 的 `[tool.uv.sources]` 部分，为 `cascade-cli-controller`、`cascade-cli-observer` 和 `cascade-connector-mqtt` 添加 `{ workspace = true }` 映射。

### 基本原理
显式声明工作区源是 `uv` 解析本地依赖图的前提。这告诉构建工具这些包不是来自 PyPI，而是直接位于当前的 `packages/` 目录下，应该以可编辑模式链接。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/tooling #task/object/config-uv #task/action/config-update #task/state/continue

---

### Script

#### Acts 1: 注册工作区源

我们将缺失的包映射添加到 `[tool.uv.sources]` 部分。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-interfaces = { workspace = true }
cascade-runtime = { workspace = true }
cascade-py = { workspace = true }
cascade-provider-ipfs = { workspace = true }

[tool.hatch.workspaces]
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-interfaces = { workspace = true }
cascade-runtime = { workspace = true }
cascade-py = { workspace = true }
cascade-provider-ipfs = { workspace = true }
cascade-cli-controller = { workspace = true }
cascade-cli-observer = { workspace = true }
cascade-connector-mqtt = { workspace = true }

[tool.hatch.workspaces]
~~~~~

### 下一步建议
这是最后一块拼图。

请再次执行：
1.  **安装**: `uv pip install -e .[dev]`
2.  **测试**: `pytest`

现在配置已经完整且闭环，环境搭建应该能顺利完成。
