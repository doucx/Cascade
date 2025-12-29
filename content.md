## [WIP] fix: Correct dataclass inheritance and revert premature build config

### 错误分析
1.  **`TypeError: non-default argument 'func' follows default argument 'metadata'`**:
    *   **根本原因**: `TaskDef` dataclass 继承自 `Definition` dataclass。`Definition` 包含带有默认值的字段 (`fingerprint`, `metadata`)。`TaskDef` 引入了没有默认值的字段 (`func`, `name`)。Python 在生成 `__init__` 方法时，将父类的字段放在前面，导致生成的签名无效，因为无默认值的参数出现在了有默认值的参数之后。
    *   **解决方案**: 在 `Definition` 的 `@dataclass` 装饰器中添加 `kw_only=True`。这将强制所有 `Definition` 的字段（以及继承它的子类的这些字段）在 `__init__` 中必须通过关键字指定，从而将它们从 `__init__` 的位置参数列表中移出，解决了顺序冲突。

### 用户需求

### 评论
这个 `TypeError` 是一个很好的例子，说明了即使使用高级工具（如 dataclasses），也必须遵守 Python 语言的基本规则。通过 `kw_only=True` 进行修复是处理 dataclass 继承中此类问题的标准模式。同时，撤销对构建文件的修改是回归正确协议轨道的重要一步。

### 目标
1.  将根 `pyproject.toml` 文件恢复到修改前的状态。
2.  将 `packages/cascade-compiler/pyproject.toml` 文件恢复到修改前的状态。
3.  通过在 `Definition` 基类中强制使用关键字参数来修复 `TypeError`。

### 基本原理
通过将 `Definition` 的字段设为 keyword-only，我们生成的 `TaskDef.__init__` 签名将变为 `(self, func: Callable, name: str, *, fingerprint: Optional[Fingerprint] = None, metadata: Dict = ...)`. 这是一个完全合法的 Python 签名，解决了 `TypeError` 的根源。撤销构建文件的修改是承认错误并严格遵守用户指令的必要操作。

### 标签
#intent/fix #flow/draft #priority/critical
#comp/foundation #comp/compiler #scope/dx
#ai/instruct
#task/domain/core #task/object/compiler #task/action/tdd
#task/state/continue #task/status/active

---

### Script

#### Acts 3: 修复 `TypeError`
在 `Definition` 基类中应用 `kw_only=True` 修复 dataclass 继承问题。

~~~~~act
patch_file
packages/cascade-foundation/src/cascade/foundation/definitions/base.py
~~~~~
~~~~~python.old
@dataclass
class Definition:
    """
    Base class for all IR Level 0 definitions.
~~~~~
~~~~~python.new
@dataclass(kw_only=True)
class Definition:
    """
    Base class for all IR Level 0 definitions.
~~~~~

### 下一步建议
现在，`TypeError` 应该已经解决，`pytest` 将能够成功收集测试。请运行测试。我们预期 `test_builder.py` 中的部分测试会失败（特别是 `test_compiler_stable_identity`），这完全符合 TDD 的 "Red" 阶段。

一旦确认测试环境正常，我将为下一个 TDD 循环生成计划：**实现基于内容的 Fingerprint 计算**，以通过 `test_compiler_stable_identity`。
