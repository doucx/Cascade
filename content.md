## [WIP] fix(config): 移除子包中的 `__init__.py` 以修复 Pyright 命名空间合并

### 错误分析
Pyright 和其他静态分析工具在处理 Monorepo 源码视图（Source View）时，遵循严格的包发现规则：
1.  如果在 `extraPaths` 中发现了多个包含 `cascade/__init__.py` 的目录，它会将它们视为**多个冲突的常规包 (Regular Packages)**，通常只选取第一个加载，而忽略其他的。这导致了“找不到模块”的错误，因为 Pyright 认为它已经找到了 `cascade` 包的全部内容。
2.  Python 3.3+ 支持**隐式命名空间包 (Implicit Namespace Packages)**，即没有 `__init__.py` 的目录。Pyright 能够完美地自动合并多个隐式命名空间包。
3.  之前为了“运行时统一性”添加的 `__init__.py` 文件，无意中破坏了 Pyright 的合并逻辑。

虽然 `pkgutil` 可以在**运行时**通过 `sys.path` 扫描修复这个问题，但静态分析器不执行代码，因此无法利用 `extend_path` 的动态特性（除非使用 Editable Install，这在当前环境中不适用）。

### 用户需求
修复 48 个 Pyright 导入错误，使开发环境能正确识别跨包引用。

### 评论
我们必须回滚之前的操作。对于 Monorepo 源码开发，**除了**定义了顶层 API 的 `cascade-python` 外，其他所有包的 `cascade/` 根目录都必须保持为“隐式命名空间”（即不包含 `__init__.py`）。

### 目标
1.  删除除 `cascade-python` 外所有子包中 `src/cascade/__init__.py` 文件。
2.  保留 `cascade-python` 中的 `__init__.py`，因为它包含核心 API 逻辑和 `extend_path`（这足以保证运行时兼容性）。

### 基本原理
通过移除 `__init__.py`，我们告诉 Pyright：“这些目录只是 `cascade` 命名空间的一部分片段，请将它们合并。”

### 标签
#intent/fix #flow/ready #priority/high #comp/build #concept/config #scope/dx #ai/instruct #task/domain/build-system #task/object/namespace-packages #task/action/revert #task/state/continue

---

### Script

#### Acts 1: 移除阻碍 Pyright 合并的 `__init__.py` 文件

注意：我们保留 `packages/cascade-python/src/cascade/__init__.py`，因为那是唯一的 Facade 包。

~~~~~act
delete_file
packages/cascade-application/src/cascade/__init__.py
~~~~~

~~~~~act
delete_file
packages/cascade-cli-controller/src/cascade/__init__.py
~~~~~

~~~~~act
delete_file
packages/cascade-cli-observer/src/cascade/__init__.py
~~~~~

~~~~~act
delete_file
packages/cascade-common/src/cascade/__init__.py
~~~~~

~~~~~act
delete_file
packages/cascade-connector-local/src/cascade/__init__.py
~~~~~

~~~~~act
delete_file
packages/cascade-connector-mqtt/src/cascade/__init__.py
~~~~~

~~~~~act
delete_file
packages/cascade-engine/src/cascade/__init__.py
~~~~~

~~~~~act
delete_file
packages/cascade-graph/src/cascade/__init__.py
~~~~~

~~~~~act
delete_file
packages/cascade-library/src/cascade/__init__.py
~~~~~

~~~~~act
delete_file
packages/cascade-provider-ipfs/src/cascade/__init__.py
~~~~~

~~~~~act
delete_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~

~~~~~act
delete_file
packages/cascade-spec/src/cascade/__init__.py
~~~~~

### 下一步建议
操作完成后，Pyright 应该能够通过 `pyrightconfig.json` 中的 `extraPaths` 自动将这些目录下的 `cascade` 文件夹合并为一个逻辑命名空间。请再次运行 `pyright **/src/**.py` 进行验证。

此时剩下的错误应该只与 `cascade-python` 相关（因为它有一个显式的 `__init__.py`，可能会与合并后的隐式命名空间产生一点摩擦，但在 Pyright 的最新版本中通常能处理），或者是一些真实的类型错误。
