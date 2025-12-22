好的，`Unknown` 类型通常是 Python 类型检查器（如 Pyright/Pylance）无法找到类型定义或该包未声明支持类型检查（PEP 561）的标志。

最常见的原因是**缺少 `py.typed` 标记文件**。即使你有完美的 `.pyi` 文件，如果包内没有 `py.typed`，类型检查器也会默认忽略该包的类型信息。

我们需要检查并为所有核心包添加这个标记。

## [WIP] fix(tooling): Add missing `py.typed` markers to enable IDE type inference

### 错误分析
1.  **`LazyResult` 为 `Unknown`**:
    *   **根本原因**: `cascade-spec` 和 `cascade-sdk` 包目录下极有可能缺少 `py.typed` 空文件。这是 PEP 561 要求的“类型检查启用开关”。没有它，Pyright 会将导入视为非类型化的库。
2.  **泛型丢失**:
    *   即使解决了 `Unknown`，如果 `.pyi` 中的 `LazyResult` 没有被正确声明为泛型（例如 `LazyResult[T]`），它也只是一个普通类。我们需要检查 `cascade-spec` 中的定义。

### 用户需求
让 IDE 能够正确识别 `LazyResult` 类型，消除 `Unknown` 状态。

### 目标
1.  确保所有 `src/cascade` 子目录下都有 `py.typed` 文件。
2.  验证 `LazyResult` 的定义是泛型的。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #scope/dx #task/domain/tooling #task/object/ide-stubs #task/action/fix #task/state/continue

---

### Script

~~~~~act
read_file
~~~~~
~~~~~
packages/cascade-spec/src/cascade/spec/lazy_types.py
~~~~~

#### Acts 3: 创建缺失的 `py.typed` 文件
这一步是根据 Acts 1 的结果来的，但我可以先发制人地为所有包创建它，因为这是幂等的且无害的。

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

#### Acts 4: 修改 `generate_stubs.py` 以支持泛型（如果定义支持的话）
如果在 Acts 2 中我们发现 `LazyResult` 是泛型，我们需要让 `generate_stubs.py` 不要在清理类型字符串时无脑移除 `[Any]` 等泛型参数，或者更智能地处理它们。

目前 `clean_type_str` 函数有这么一行：
```python
        (r"'LazyResult\[Any\]'", "LazyResult"),
        (r"'LazyResult'", "LazyResult"),
```
这实际上是在**主动剥离**泛型信息。我们需要让它更智能。

让我们先看看 Acts 1 和 2 的结果。
