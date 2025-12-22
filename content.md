分析结果非常有趣。

1.  **Namespace Package 结构**:
    *   `cascade-spec` 和 `cascade-engine` 等确实是隐式 Namespace Package（`src/cascade/` 下**没有** `__init__.py`）。
    *   `cascade-sdk` 是一个显式的 Namespace Package，它使用了 `pkgutil.extend_path`。
    *   `cascade-common` 也有一个 `__init__.py`。

2.  **`pkgutil` 声明**:
    `packages/cascade-sdk/src/cascade/__init__.py` 已经包含了：
    ```python
    __path__ = __import__("pkgutil").extend_path(__path__, __name__)
    ```
    这在理论上是正确的，它允许 `cascade` 包跨越多个位置。

3.  **问题核心**：
    问题在于 `cascade-spec` 和 `cascade-engine` 是**隐式 (Implicit)** Namespace Package (PEP 420)，而 `cascade-sdk` 是**显式 (Legacy/pkgutil)** Namespace Package。
    虽然这在 Python 3.3+ 运行时是可以混合工作的，但静态分析工具（尤其是 Pyright/Pylance）对混合使用这两种模式的支持往往很脆弱。
    **当存在一个包含 `__init__.py` 的目录时，LSP 往往会优先将其视为该包的唯一源，从而忽略其他隐式分布的包。**

    为了解决这个问题，我们需要确保**所有**参与 `cascade` 命名空间的包都采用相同的模式。由于 `cascade-sdk` 必须有 `__init__.py`（为了暴露 API），我们应该将所有其他包也升级为**显式 Namespace Package**。这意味着我们需要在所有包的 `src/cascade/` 目录下添加一个仅包含 `pkgutil` 样板代码的 `__init__.py`。

    这不仅能修复 LSP 问题，还能提高对旧版工具的兼容性，是一种更稳健的工程实践。

## [WIP] fix(build): Standardize namespace packages to explicit pkgutil style

### 错误分析
LSP 无法解析 `LazyResult` 的原因确认为 Namespace Package 模式不一致。`cascade-sdk` 使用显式 `__init__.py`，遮蔽了 `cascade-spec` 的隐式命名空间。

### 用户需求
让 LSP 正确解析跨包导入。

### 目标
在所有子包（spec, engine, graph 等）的 `src/cascade/` 目录下创建 `__init__.py`，并填入 `pkgutil` 扩展代码。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #scope/dx #task/domain/tooling #task/object/ide-stubs #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 为 `cascade-spec` 创建显式 `__init__.py`

~~~~~act
write_file
packages/cascade-spec/src/cascade/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

#### Acts 2: 为 `cascade-engine` 创建显式 `__init__.py`

~~~~~act
write_file
packages/cascade-engine/src/cascade/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

#### Acts 3: 为 `cascade-graph` 创建显式 `__init__.py`

~~~~~act
write_file
packages/cascade-graph/src/cascade/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

#### Acts 4: 为 `cascade-library` 创建显式 `__init__.py`

~~~~~act
write_file
packages/cascade-library/src/cascade/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

#### Acts 5: 检查 `cascade-common` 的 `__init__.py`
之前 `ls` 显示它有文件，我们需要确认它是否已经包含了 `pkgutil` 声明。

~~~~~act
read_file
packages/cascade-common/src/cascade/__init__.py
~~~~~

### 下一步建议
一旦所有包都统一为显式命名空间，LSP 应该就能正确地将它们“缝合”在一起。我们将再次检查 `cascade-common`，如果需要修改，将在下一个步骤中进行。之后，我们将创建一个包含 `py.typed` 和这些 `__init__.py` 的提交。
