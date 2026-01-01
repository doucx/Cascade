太棒了。忽略 dunder 属性有效地切断了由于 Python 内部元数据访问触发的过早 Provider 发现循环。

## [COMMIT] fix(sdk): prevent circular import by ignoring dunder attributes in __getattr__

### 用户需求
修复由于 `cascade.sdk` 中的 `__getattr__` 误捕获 Python 内部属性（如 `__spec__`）而导致的 `import cascade` 循环引用错误。

### 评论
这是一个关键的基础设施修复。动态属性查找是一个强大的工具，但如果不小心区分内部机制和业务逻辑，很容易引发微妙的启动期故障。

### 目标
1. 提交 `packages/cascade-sdk/src/cascade/sdk.py` 的修改。
2. 清理临时诊断脚本 `diagnose_providers.py`。

### 基本原理
通过在 `__getattr__` 中首先检查并排除以 `__` 开头的属性，我们确保了只有常规的业务逻辑访问（或 Provider 请求）才会触发 Registry 的发现流程。这保证了在 `import cascade` 期间，模块可以安全地完成初始化，而不会被 Provider 的提前加载所中断。

### 标签
#intent/fix #flow/done #priority/high #comp/sdk #scope/core #ai/delegate #task/domain/testing #task/object/circular-import #task/action/fix #task/state/end #task/status/completed

---

### Script

#### Acts 1: 清理临时诊断工具

由于问题已经定位并修复，我们删除诊断脚本。

~~~~~act
delete_file
diagnose_providers.py
~~~~~

#### Acts 2: 提交代码修复

我们将修复后的 SDK 文件添加到暂存区并进行提交。

~~~~~act
git_add
packages/cascade-sdk/src/cascade/sdk.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(sdk): prevent circular import in dynamic attribute lookup

Modified `cascade.sdk.__getattr__` to explicitly ignore dunder attributes (starting with '__'). 

Previously, the attribute lookup was too broad, capturing internal Python metadata requests (like `__spec__` or `__path__`) during the initial `import cascade` sequence. This triggered the full `ProviderRegistry` discovery process before the top-level `cascade` module had finished its own initialization (specifically `from cascade.sdk import *`). 

When a discovered provider (like IPFS) then attempted to import from `cascade`, it encountered a partially initialized module without the required attributes, leading to an `AttributeError`. 

By ignoring dunder attributes, we ensure that the registry is only touched by legitimate business-level access, allowing a safe and clean module initialization.
~~~~~

### 下一步建议
- **回归测试**：确保所有其他 providers（如 http, s3）在新的 SDK 逻辑下依然能够被正确加载。
- **Linting**：考虑到 `cascade` 是一个高度动态的 SDK，建议在 CI 中增加对导入循环的静态检测工具。
