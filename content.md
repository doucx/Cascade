好的，这又是一个关于类型检查器（Pyright/Pylance）如何判定“重新导出（Re-export）”的经典问题。

 深度分析

*   **现象**: `cs.visualize` 在运行时存在，但在 IDE 中提示 "not an attribute"。
*   **原因**: 在 `.pyi` 文件中，如果你只是写 `from module import symbol`，严格的类型检查器会认为这只是**当前文件内部使用**的依赖，而不是向外暴露的公共 API。
*   **解决方案**: 为了显式地声明“我要导出这个符号”，必须使用**冗余别名**语法：
    `from module import symbol as symbol`
    或者定义 `__all__`。

在你的 `.pyi` 文件中，`visualize` 目前是这样导入的：
```python
from cascade.tools.visualize import visualize
```
这被视为私有导入。我们需要让脚本生成：
```python
from cascade.tools.visualize import visualize as visualize
```

---

## [WIP] fix: 强制重新导出 SDK 成员

### 用户需求
修复 IDE 中 `cs.visualize` 等 SDK 核心成员显示为 "not an attribute" 的问题。

### 目标
修改 `generate_stubs.py`，使所有 `KNOWN_SDK_EXPORTS` 的导入语句都使用 `import X as X` 的格式，从而被类型检查器识别为公共导出。

### Script

#### Acts 1: 修正导入生成逻辑

~~~~~act
patch_file
scripts/generate_stubs.py
~~~~~
~~~~~python
        for module_path, names in sorted(imports_by_module.items()):
            content_lines.append(f"from {module_path} import {', '.join(sorted(names))}")
        
        if sdk_natives:
~~~~~
~~~~~python
        for module_path, names in sorted(imports_by_module.items()):
            # Use 'import X as X' to force re-export for type checkers
            imports = ", ".join(f"{name} as {name}" for name in sorted(names))
            content_lines.append(f"from {module_path} import {imports}")
        
        if sdk_natives:
~~~~~

### 下一步建议

1.  运行 `act` 应用补丁。
2.  运行 `python scripts/generate_stubs.py`。
3.  重启 IDE。

你会发现 `packages/cascade-sdk/src/cascade/__init__.pyi` 中的导入语句变了，例如 `from cascade.tools.visualize import visualize as visualize`。这将彻底解决 "not an attribute" 的问题。
