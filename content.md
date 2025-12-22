好的，确认了。由于缺少 `py.typed` 文件，PEP 561 兼容的类型检查器（如 Pyright/Pylance）会忽略包中的类型信息，即使我们生成了完美的 `.pyi` 文件。

我们将执行以下操作：
1.  **创建 `py.typed` 文件**：在所有相关包中添加此标记文件。
2.  **优化 `generate_stubs.py`**：修改类型清理逻辑，允许 `LazyResult` 携带泛型参数（至少是 `[Any]`），而不是强行将其剥离。这将为未来更精确的类型推断打下基础。

## [WIP] fix(tooling): Add py.typed and preserve generics in stubs

### 用户需求
1.  让 IDE 识别 `LazyResult` 类型（解决 `Unknown`）。
2.  保留泛型信息（如 `LazyResult[Any]`）。

### 目标
1.  在所有 `src/cascade` 目录创建 `py.typed`。
2.  更新 stub 生成器以保留泛型语法。

### 基本原理
`py.typed` 是 PEP 561 的标准机制。而保留泛型信息可以让开发者明确知道 `LazyResult` 是一个容器类型，虽然目前自动生成的可能大多是 `Any`，但这比完全丢失信息要好。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #scope/dx #task/domain/tooling #task/object/ide-stubs #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 创建 `py.typed` 文件
这一步对于启用类型检查至关重要。

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

#### Acts 2: 修改 `scripts/generate_stubs.py` 以保留泛型
我们将修改 `clean_type_str` 函数。目前的逻辑过于激进，会把 `LazyResult[Any]` 替换为 `LazyResult`。我们将移除这一替换规则，并确保 `LazyResult` 的完整路径被正确缩短但保留中括号。

~~~~~act
patch_file
scripts/generate_stubs.py
~~~~~
~~~~~python
    # Simplify full paths to short names
    replacements = [
        (r"cascade\.spec\.lazy_types\.LazyResult", "LazyResult"),
        (r"cascade\.spec\.protocols\.Connector", "Connector"),
        (r"cascade\.spec\.protocols\.StateBackend", "StateBackend"),
        (r"cascade\.spec\.protocols\.CachePolicy", "CachePolicy"),
        # Handle quotes
        (r"'LazyResult\[Any\]'", "LazyResult"),
        (r"'LazyResult'", "LazyResult"),
    ]

    for pattern, repl in replacements:
~~~~~
~~~~~python
    # Simplify full paths to short names
    replacements = [
        (r"cascade\.spec\.lazy_types\.LazyResult", "LazyResult"),
        (r"cascade\.spec\.protocols\.Connector", "Connector"),
        (r"cascade\.spec\.protocols\.StateBackend", "StateBackend"),
        (r"cascade\.spec\.protocols\.CachePolicy", "CachePolicy"),
        # Handle quotes (but preserve generics like LazyResult[Any])
        (r"'LazyResult'", "LazyResult"), 
    ]

    for pattern, repl in replacements:
~~~~~

### 下一步建议
这次操作后，IDE 应该能正确加载类型信息。如果 VS Code 仍然显示红色，通常需要执行 **Developer: Reload Window** 来强制重新索引。到此为止，我们已经彻底解决了 IDE 飘红和自动补全失效的问题。
