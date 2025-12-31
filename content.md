简要回答
是的，由于 `cascade.providers` 是一个命名空间包（Namespace Package），它不应该包含具体的逻辑代码（如类定义或重导出）。当多个包（如 `cascade-sdk` 和 `cascade-provider-ipfs`）共享这个命名空间时，`__init__.py` 的加载顺序是不确定的，导致有时无法找到在其中定义的 `LazyFactory`。

最稳健的做法是直接从定义的源头 `cascade.spec.protocols` 导入这些协议。

我们将执行以下操作：
1.  批量将所有 Provider 实现文件中的导入路径从 `cascade.providers` 修改为 `cascade.spec.protocols`。
2.  清理 `packages/cascade-sdk/src/cascade/providers/__init__.py`，使其成为标准的、纯净的命名空间包。

## [WIP] refactor: 规范化 Provider 协议的导入路径

### 摘要头
## [WIP] refactor: 规范化 Provider 协议的导入路径

### 用户需求
修复由于命名空间包冲突导致的 `ImportError`，确保测试能够正确加载 `LazyFactory` 和 `Provider` 协议。

### 评论
这是一个架构层面的修正。命名空间包（PEP 420）的设计初衷是用于包的拆分，严禁在 `__init__.py` 中放置逻辑代码。之前的实现在 `cascade-sdk` 的该文件中进行了重导出，这在单包环境下没问题，但在多包环境下（引入 `cascade-provider-ipfs` 后）就暴露了脆弱性。

### 目标
1.  修正所有引用错误的 Python 文件。
2.  净化 `cascade-sdk` 中的 `cascade/providers/__init__.py`。

### 基本原理
直接依赖 `cascade.spec.protocols` 这一单一事实来源（Single Source of Truth），解除对 `cascade.providers` 命名空间包行为的隐式依赖。

### 标签
#intent/refine #flow/ready #priority/high #comp/build #scope/core #ai/instruct #task/domain/refactor #task/object/imports #task/action/fix-circular-dependency #task/state/continue

---

### Script

#### Acts 1: 批量修正导入路径

使用 `sed` 批量替换错误的导入语句。我们将处理几种常见的导入格式。

~~~~~act
run_command
~~~~~
~~~~~
grep -r "from cascade.providers import .*LazyFactory" packages | cut -d: -f1 | sort | uniq | xargs sed -i 's/from cascade.providers import/from cascade.spec.protocols import/g'
~~~~~

#### Acts 2: 净化命名空间包入口

将 `cascade-sdk` 中的 `cascade/providers/__init__.py` 还原为纯粹的命名空间包声明。

~~~~~act
write_file
packages/cascade-sdk/src/cascade/providers/__init__.py
~~~~~
~~~~~python
# This allows 'cascade.providers' to be a namespace package,
# extended by other installed packages (like cascade-provider-ipfs).
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

### 下一步建议
运行测试以验证修复。
`pytest packages/cascade-sdk/tests/examples/test_llm_pattern.py`
