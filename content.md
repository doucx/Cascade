这是一个专注于架构合规性的提交。

## [COMMIT] fix(naming): Adhere to Hash Naming Axiom v3.0 in compiler utils

### 用户需求
修正 `hashing.py` 和 `reflection.py` 中违反《架构公理：哈希强制长命名规范 v3.0》的变量命名。

### 评论
这次修正确保了所有哈希变量都遵循 `[State]_[Source]_[Object]_hash` 的格式，消除了关键抽象（如代码结构哈希）在语义上的模糊性，是保障系统身份完整性的一步。

### 目标
1.  在 `hashing.py` 中，将 `code_hash` 替换为 `canonical_code_structure_hash`。
2.  在 `reflection.py` 中，将 `structure_hash` 替换为 `current_code_structure_hash`。

### 基本原理
根据哈希命名公理，用于在运行时建立持久链接的 ID 必须使用 `canonical` 状态，而用于表示当前代码文件快照的哈希必须使用 `current` 状态。这次重命名严格遵守了这一语义分离原则。

### 标签
#intent/fix #flow/ready #priority/critical #comp/compiler #scope/core #concept/identity #ai/instruct #task/domain/compliance #task/object/hash-naming #task/action/fix #task/state/end

---

### Script

#### Acts 1: 提交哈希命名规范修复

~~~~~act
git_add
packages/cascade-compiler/src/cascade/compiler/utils/hashing.py
packages/cascade-compiler/src/cascade/compiler/utils/reflection.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(naming): Adhere to Hash Naming Axiom v3.0 in compiler utils

Ensures full compliance with the mandatory hash naming convention: `[State]_[Source]_[Object]_hash`.

Non-compliant short names were causing semantic ambiguity:

- In `hashing.py`, `code_hash` (representing the stable identity used for instance hashing) was renamed to `canonical_code_structure_hash`.
- In `reflection.py`, `structure_hash` (representing the snapshot taken from source code) was renamed to `current_code_structure_hash`.

This rectifies a critical architectural violation and improves code self-documentation.
~~~~~

### 下一步建议
哈希命名合规性问题已解决。现在我们回归到通用布线算法的演进路径。

下一步建议：
1.  **完善异常路由**: 修改 `standard_stainer`，使其捕获 `worker_result` 中的异常对象，并将其路由到新的 `output_error` 端口。这完成了主权端口体系的闭环。
2.  **通用性验证**: 引入一个连续资源（如 `Memory`），编写 `ContinuousResourcePrism`，以验证 Prism 架构的通用性。

你希望先完善异常路由的闭环，还是进入通用性验证？
