## [WIP] fix(build): 修复 pyproject.toml 中的工作区源映射

### 用户需求
修复 `cascade-application` 构建失败的问题。

### 错误分析
`uv` 报错指出 `cascade-common` 在 `dependencies` 中被引用，但在 `[tool.uv.sources]` 中缺少相应的工作区映射。这是因为我在上一轮修改中将依赖从 `cascade-sdk` 切换到了 `cascade-common`，但忘记更新源映射配置。

### 目标
在 `packages/cascade-application/pyproject.toml` 的 `[tool.uv.sources]` 部分添加 `cascade-common = { workspace = true }`。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #scope/core

---

### Script

#### Acts 1: 修复 pyproject.toml

~~~~~act
patch_file
packages/cascade-application/pyproject.toml
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-graph = { workspace = true }
cascade-sdk = { workspace = true }
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-engine = { workspace = true }
cascade-graph = { workspace = true }
cascade-common = { workspace = true }
~~~~~

### 下一步建议
构建修复后，我们将继续执行 ADR-013 的**阶段三**：将 `visualize` 和 `dry_run` 的逻辑从 SDK 迁移到 `CascadeApp`。

为了做到这一点，我需要先读取 SDK 中相关工具的源代码，以便能够正确地将它们移植过来。

~~~~~act
read_file
packages/cascade-sdk/src/cascade/tools/visualize.py
~~~~~

~~~~~act
read_file
packages/cascade-sdk/src/cascade/tools/preview.py
~~~~~

~~~~~act
read_file
packages/cascade-sdk/src/cascade/tools/events.py
~~~~~
