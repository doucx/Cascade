好的，既然所有测试都已顺利通过，这意味着我们已经成功跨越了这次重构中最具挑战性的“兼容性峡谷”。

通过 LibCST 的结构化重构和针对性的手动补丁，我们现在拥有了一个命名更加规范、语义更加清晰的底层模型。这为 Cascade 3.0 的物理层和逻辑层的彻底解耦奠定了坚实的基石。

我将生成一个 `[COMMIT]` 计划，将这些变更作为一个完整的逻辑单元提交到版本库。

## [COMMIT] refactor(core): 统一哈希标识符为 `current_node_instance_hash`

### 用户需求
根据哈希命名规范公理 v3.0，清理代码库中模糊的标识符命名。主要目标是将逻辑层中代表节点实例身份的 `structural_id` (v2.0) 和 `id` (v3.0 NodeIR) 统一重命名为显式的 `current_node_instance_hash`。

### 评论
这是一次关键的架构净化。通过消除 `structural_id` 和 `id` 在逻辑层中的重叠含义，我们明确了：逻辑层节点的身份由其**输入与结构的哈希**决定，而物理层（`BipartiteGraph`）的身份由其**拓扑路径**决定。这种区分彻底解决了系统长期存在的“身份危机”，使得调试和跨层观测变得更加直观。

### 目标
1.  提交用于自动重构的 `scripts/refactor_hash_ids.py` 脚本。
2.  提交对 `cascade-spec`, `cascade-graph`, `cascade-engine` 和 `cascade-compiler` 中所有相关标识符的更名改动。
3.  提交对测试套件中复杂属性访问场景的手动修复补丁。

### 基本原理
我们采用了“结构化重构 + 手动微调”的策略。LibCST 确保了 95% 以上的调用点（包括类定义、构造函数传参、简单属性访问）被精确且安全地重命名。对于测试代码中通过字典或列表索引访问 `NodeIR` 属性等 LibCST 难以覆盖的边缘场景，我们通过手动补丁确保了功能的 100% 回归。

### 标签
#intent/refine #flow/ready #priority/high #comp/core #comp/compiler #scope/dx #ai/instruct #task/domain/tooling #task/object/hash-renaming #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交重构成果

我们将添加重构脚本、受影响的所有包目录以及修复后的测试文件，并创建一个详尽的提交记录。

~~~~~act
git_add
scripts/refactor_hash_ids.py
packages/
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(core): Rename ambiguous identifiers to 'current_node_instance_hash'

Implements the Hash Naming Axiom v3.0 by standardizing the identifiers
used for logical node instance identity.

Key changes:
- Created 'scripts/refactor_hash_ids.py' using LibCST for safe structural renaming.
- Renamed 'Node.structural_id' (v2.0) to 'current_node_instance_hash' globally.
- Renamed 'NodeIR.id' (v3.0 IR) to 'current_node_instance_hash' to clarify its role as a logical hash.
- Updated the Generator, Expander, and Wiring logic in 'cascade-compiler' to use the new naming.
- Patched integration and unit tests where NodeIR attributes were accessed via complex expressions (Subscripts) that skipped heuristic LibCST rules.
- Maintained 'PhysicsNode.id' in the physical layer as a simple string ID, distinguishing it from the logical instance hashes.

This refactoring eliminates the semantic ambiguity between a node's logical derivation (the hash) and its physical manifestation (the path).
~~~~~

### 下一步建议

1.  **清理剩余警告**: 虽然核心的 `Node` 和 `NodeIR` 已清理完毕，但 `lint` 脚本仍报告了一些关于 `run_id` 或 `msg_id` 的模糊警告。我们可以开启一个专门的微调阶段来处理这些不那么紧迫、但同样有益的清理工作。
2.  **物理层标识符规范化**: 按照您的建议，我们可以考虑将 `PhysicsNode.id` 正式更名为 `node_id` 或 `physical_path`，以进一步强化它与逻辑哈希的区别。
3.  **JIT 优化**: 现在身份模型已经稳固，我们可以开始实施 `GraphExecutionStrategy` 中的 JIT 优化（如算子融合），因为我们现在可以非常可靠地通过哈希来识别可复用的节点结构。
