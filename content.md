简要回答

非常抱歉，我违反了系统的公理级约束。`code_hash` 和 `structure_hash` 确实不符合《哈希强制长命名规范 v3.0》。

这是一个严重的合规性问题。根据公理，变量名必须完整描述其**状态 (State)**、**来源 (Source)** 和 **对象 (Object)**。我将立即修正这些违规命名，确保代码库完全符合“统一身份”框架。

## [WIP] fix(compiler): 修正哈希变量命名以符合架构公理 v3.0

### 错误分析
在 `hashing.py` 和 `reflection.py` 中，我使用了简写变量名（`code_hash`, `structure_hash`）。
*   **违规原因**: 违反了 `[State]_[Source]_[Object]_hash` 的四段式强制构造法。
*   **潜在风险**: 简写掩盖了哈希的语义角色（是用于“链接”的 `canonical` 状态，还是用于“比较”的 `current` 状态？），这在复杂的变更检测逻辑中会导致致命的歧义。

### 用户需求
修正所有被 Lint 识别出的哈希命名违规项。

### 评论
“公理不可逾越”。这次修正将把模糊的“结构哈希”提升为明确的“当前代码结构哈希”和“规范代码结构哈希”，使身份追踪逻辑完全自文档化。

### 目标
1.  将 `hashing.py` 中的 `code_hash` 重命名为 `canonical_code_structure_hash`。
2.  将 `reflection.py` 中的 `structure_hash` 重命名为 `current_code_structure_hash`。

### 基本原理
根据《哈希强制长命名规范 v3.0》：
*   在 `hashing.py` 中，我们使用哈希来建立节点身份，这属于 **链接 (Linking)** 行为，因此状态应为 `canonical`。
*   在 `reflection.py` 中，我们正在从实时源码中计算快照，这属于 **快照 (Snapshot)** 行为，因此状态应为 `current`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/compiler #scope/core #concept/identity #task/domain/compiler #task/object/hash-naming #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 修正 `hashing.py` 中的命名违规

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/utils/hashing.py
~~~~~
~~~~~python.old
    ) -> str:
        # 1. Start with the Stable Code Fingerprint
        code_hash = definition.fingerprint["current_code_structure_hash"]
        components = [f"CodeHash:{code_hash}"]

        # 2. Purity Salt
~~~~~
~~~~~python.new
    ) -> str:
        # 1. Start with the Stable Code Fingerprint
        # According to Axiom: [State]_[Source]_[Object]_hash
        # Use 'canonical' state here because it represents the stable identity used for linking.
        canonical_code_structure_hash = definition.fingerprint["current_code_structure_hash"]
        components = [f"CodeHash:{canonical_code_structure_hash}"]

        # 2. Purity Salt
~~~~~

#### Acts 2: 修正 `reflection.py` 中的命名违规

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/utils/reflection.py
~~~~~
~~~~~python.old
        # 3. Compute Fingerprint
        # We compute a structural hash based on the definition's content.
        structure_hash = self._compute_structure_hash(
            name, args, return_annotation, docstring, is_async, mode
        )

        fingerprint = Fingerprint()
        fingerprint["current_code_structure_hash"] = structure_hash

        return TaskDef(
~~~~~
~~~~~python.new
        # 3. Compute Fingerprint
        # We compute a structural hash based on the definition's content.
        # According to Axiom: [State]_[Source]_[Object]_hash
        # Use 'current' state here because this is a snapshot freshly computed from source.
        current_code_structure_hash = self._compute_structure_hash(
            name, args, return_annotation, docstring, is_async, mode
        )

        fingerprint = Fingerprint()
        fingerprint["current_code_structure_hash"] = current_code_structure_hash

        return TaskDef(
~~~~~

### 下一步建议
修正完成后，请再次运行 `python scripts/lint_hash_names.py` 以确认违规项已全部消除。
我们将始终保持对架构公理的最高敬畏。
