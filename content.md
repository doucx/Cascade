好的，`cascade-common` 已经正确配置。这确认了我们的诊断：`cascade-sdk` 和 `cascade-common` 作为显式命名空间包，遮蔽了其他隐式命名空间包。

现在我们将执行一个完整的计划，将所有相关的包都转换为显式命名空间包，并同时添加 `py.typed` 标记。这将从根本上解决 LSP 的类型解析问题。

## [WIP] fix(build): Standardize on explicit namespace packages and add py.typed

### 错误分析
1.  **Namespace 模式不一致**: `cascade-sdk` 和 `cascade-common` 使用了带 `__init__.py` 的显式命名空间包，而 `cascade-spec`, `cascade-engine` 等则使用了无 `__init__.py` 的隐式命名空间包。这种混合模式导致 Pyright/Pylance 等静态分析器无法正确合并 `cascade` 命名空间，从而找不到 `cascade.spec` 等子模块。
2.  **缺少 `py.typed` 标记**: 所有包都缺少 PEP 561 规定的 `py.typed` 文件，这告诉类型检查器要忽略这些包的类型信息。

这两个问题共同导致了 LSP 将跨包导入的类型（如 `LazyResult`）解析为 `Unknown`。

### 用户需求
修复 LSP，使其能正确解析项目中的所有类型，消除 `Unknown` 状态。

### 评论
这是一个关键的开发者体验（DX）修复。通过将所有包统一为更稳健的显式（`pkgutil`）命名空间包，我们不仅解决了当前的 LSP 问题，还为项目的长期可维护性奠定了坚实的基础。

### 目标
1.  在所有 `cascade-*` 包的 `src/cascade` 目录下创建 `py.typed` 文件，以启用类型检查。
2.  在所有之前使用隐式命名空间的包（spec, engine, graph, library）的 `src/cascade` 目录下创建 `__init__.py`，并添加 `pkgutil` 扩展代码，将它们转换为显式命名空间包。

### 基本原理
通过强制所有参与 `cascade` 命名空间的包都遵循同一种显式声明模式，我们消除了静态分析工具的解析歧义。`pkgutil.extend_path` 是 Python 官方支持的、用于构建跨目录包的传统且可靠的机制。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #scope/dx #task/domain/tooling #task/object/ide-stubs #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: Create `py.typed` markers
在所有包中添加 PEP 561 标记文件，以启用类型检查。

~~~~~act
run_command
~~~~~
~~~~~
touch packages/cascade-spec/src/cascade/py.typed
touch packages/cascade-sdk/src/cascade/py.typed
touch packages/cascade-engine/src/cascade/py.typed
touch packages/cascade-common/src/cascade/py.typed
touch packages/cascade-graph/src/cascade/py.typed
touch packages/cascade-library/src/cascade/py.typed
~~~~~

#### Acts 2: Standardize on explicit namespace packages
为所有之前是隐式命名空间的包创建 `__init__.py`，使其与 `cascade-sdk` 和 `cascade-common` 保持一致。

~~~~~act
write_file
packages/cascade-spec/src/cascade/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-engine/src/cascade/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-graph/src/cascade/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/cascade-library/src/cascade/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

### 下一步建议
我们已经完成了所有必要的文件系统修改。现在最关键的一步是**重启你的 IDE 或语言服务器**（例如，在 VS Code 中使用 `Developer: Reload Window` 命令）。这将强制 Pyright/Pylance 重新扫描工作区，并根据新的 `__init__.py` 和 `py.typed` 文件重新构建其类型索引。

如果重启后问题解决，我们就可以创建一个 `[COMMIT]` 计划来最终提交这些更改。
