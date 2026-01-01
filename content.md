好的，所有测试都通过，这表明我们已经成功地在编译器和运行时层面强化了哈希身份传递的契约。现在，我将为你生成一个 `[COMMIT]` 计划来提交这些变更。

## [COMMIT] fix(core): Enforce canonical_hash linkage from compiler backend to VM runtime

### 评论
这次修复解决了由于架构公理“哈希强制长命名规范”的实施过程中，`canonical_code_structure_hash` 在不同组件（编译器前端、后端、运行时）之间丢失或未被正确使用的问题。特别是，通过强制 `PhysicsFuncNode` 在构造时就要求 `canonical_code_structure_hash`，并在所有模拟和实际的节点创建中显式提供此哈希，我们建立了一条从定义到执行的不可断裂的身份链。

### 目标
提交所有修复，使系统哈希身份传递的一致性得到保证。

### 基本原理
通过以下措施，我们确保了 `canonical_code_structure_hash` 在整个编译和运行时生命周期中得到尊重与传递：
1.  **契约强化**: `cascade-spec/physics.py` 中的 `PhysicsFuncNode` 构造函数现在强制要求 `canonical_code_structure_hash` 参数。
2.  **后端实现**: `cascade-compiler/backend.py` 在创建所有 `PhysicsFuncNode` (包括合成的生命周期节点) 时，都正确地传递了 `canonical_code_structure_hash`。
3.  **测试一致性**: `cascade-vm` 和 `cascade-spec` 下的多个测试用例已同步更新，以匹配新的 `PhysicsFuncNode` 签名，并在测试场景中模拟正确的 `canonical_code_structure_hash` 传递，从而修复了链接失败相关的 `RuntimeError` 和 `TypeError`。
4.  **前端防御性修复**: 修复了 `cascade-compiler/frontend.py` 中 `_visit_mapped_result` 方法内的一个 `NameError`。

这些修改共同确立了系统中计算节点身份的稳定性和可追踪性。

### 标签
#intent/fix #flow/ready #priority/high
#comp/compiler #comp/runtime #comp/tests #concept/state #concept/executor
#task/domain/architecture #task/object/identity-hash #task/action/enforce
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 添加所有更改的文件到 Git 暂存区

我们将把在 `cascade-spec/src/cascade/spec/physics.py`、`cascade-compiler/src/cascade/compiler/backend.py`、`cascade-compiler/src/cascade/compiler/frontend.py` 以及多个测试文件中的所有修改添加到 Git 暂存区。

~~~~~act
git_add .
~~~~~

#### Acts 2: 提交代码到 Git 仓库

将暂存区的更改以一条有意义的提交信息提交。

~~~~~act
git_commit
~~~~~
~~~~~text
fix(core): Enforce canonical_hash linkage from compiler backend to VM runtime

This commit enforces the consistent propagation and usage of `canonical_code_structure_hash` across the compiler's intermediate representation (IR) and the VM's physical topology, resolving several linking and type-related errors.

Key changes include:
- **Spec Enforcement**: The `PhysicsFuncNode` constructor in `cascade-spec/src/cascade/spec/physics.py` was updated to explicitly require `canonical_code_structure_hash`, removing its default empty value.
- **Backend Fixes**: `cascade-compiler/src/cascade/compiler/backend.py` now correctly passes the `canonical_code_structure_hash` when instantiating all `PhysicsFuncNode`s, including the synthetic `result_emitter` and `term_emitter`.
- **Frontend Fix**: Resolved a `NameError` in `cascade-compiler/src/cascade/compiler/frontend.py` within the `_visit_mapped_result` method, ensuring proper variable usage during symbol table population.
- **Test Suite Alignment**: Numerous unit tests across `cascade-vm` (e.g., `test_physics.py`, reactor tests) and `cascade-spec/tests/physics/test_funcnode.py` were updated to comply with the new `PhysicsFuncNode` signature, providing valid `canonical_code_structure_hash` values, thus fixing `RuntimeError: Linking failed` and `TypeError` issues.

These changes ensure the integrity of the compute graph's identity chain, from task definition to runtime execution.
~~~~~
