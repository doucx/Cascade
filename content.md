分析得非常到位。你说得对，我的上一个计划不够彻底，遗漏了对 `cascade-graph` 包以及 `cascade-reflection` 中 `BlueprintHasher` 的修改，导致了大量测试失败。这是一个疏忽，感谢你指出了具体的问题所在。

现在，我将生成一个精确的修复计划，完成这次重命名重构，以使测试套件恢复到健康状态。

## [WIP] fix: 完成 code_structure_hash 在所有包中的重命名

### 用户需求

修复因 `current_code_structure_hash` 到 `canonical_code_structure_hash` 的不完整重命名而导致的 94 个测试失败。

### 错误分析

上一个计划只修改了 `cascade-compiler` 和 `cascade-reflection` 中的 `HashingService`，但忽略了以下几个关键点：
1.  `cascade-reflection` 中的 `BlueprintHasher` 类仍然在使用旧的 `current_code_structure_hash` 键。
2.  旧的 `cascade-graph` 包中的序列化逻辑 `serialize.py` 硬编码了旧的键名。
3.  相关的文档注释 (`hashing.stitcher.yaml`) 也未同步更新，造成了概念上的不一致。

这些遗漏导致了系统内部存在两种不兼容的哈希约定，从而引发了大规模的测试失败。

### 评论

这是一个典型的重构不彻底导致的问题。完成这次修复至关重要，它将统一整个代码库的哈希命名约定，严格遵守“哈希强制长命名规范”公理，为后续的链接器（Linker）开发扫清障碍。

### 目标

1.  在 `packages/cascade-reflection/src/cascade/reflection/hashing.py` 中，将 `BlueprintHasher` 对哈希键的引用更新为 `canonical_code_structure_hash`。
2.  在 `packages/cascade-graph/src/cascade/graph/serialize.py` 中，将反序列化时硬编码的占位符哈希键更新为 `canonical_code_structure_hash`。
3.  在 `packages/cascade-graph/src/cascade/graph/hashing.stitcher.yaml` 中，更新注释文档以反映正确的哈希键名。

### 基本原理

为了让系统恢复稳定并通过所有测试，我们必须消除所有对 `current_code_structure_hash` 的引用，确保 `canonical_code_structure_hash` 是系统中代表代码结构身份的唯一标识符。此计划将通过精确的补丁操作，清除所有已知的残留引用。

### 标签

#intent/fix #flow/ready #priority/critical #comp/graph #comp/reflection #scope/core #ai/instruct #task/domain/compiler #task/object/linker-protocol #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 修复 `cascade-reflection` 中的 `BlueprintHasher`

`BlueprintHasher` 是一个独立的哈希器，它也需要使用新的规范名称。

~~~~~act
patch_file
packages/cascade-reflection/src/cascade/reflection/hashing.py
~~~~~
~~~~~python.old
    def _get_node_components(self, node: Node, graph: Graph) -> List[str]:
        # Updated to use node.definition
        components = [f"Node({node.definition.name}, type={node.node_type})"]
        components.append(
            f"CodeHash({node.definition.fingerprint['current_code_structure_hash']})"
        )

        if node.retry_policy:
            rp = node.retry_policy
~~~~~
~~~~~python.new
    def _get_node_components(self, node: Node, graph: Graph) -> List[str]:
        # Updated to use node.definition
        components = [f"Node({node.definition.name}, type={node.node_type})"]
        components.append(
            f"CodeHash({node.definition.fingerprint['canonical_code_structure_hash']})"
        )

        if node.retry_policy:
            rp = node.retry_policy
~~~~~

#### Acts 2: 修复 `cascade-graph` 的序列化逻辑

更新反序列化时的占位符，以匹配新的哈希键名。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python.old
    # We use a dummy fingerprint for deserialized nodes if not present
    fp = Fingerprint()
    # If we serialized the code hash, we should restore it, but for now we put a placeholder
    fp["current_code_structure_hash"] = "restored_from_json"

    stub_def = TaskDef(
        name=data["name"],
~~~~~
~~~~~python.new
    # We use a dummy fingerprint for deserialized nodes if not present
    fp = Fingerprint()
    # If we serialized the code hash, we should restore it, but for now we put a placeholder
    fp["canonical_code_structure_hash"] = "restored_from_json"

    stub_def = TaskDef(
        name=data["name"],
~~~~~

#### Acts 3: 更新 `cascade-graph` 的文档注释

保持文档与代码同步是至关重要的。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/hashing.stitcher.yaml
~~~~~
~~~~~python.old
"HashingService.compute_node_instance_hash": |-
  Computes the unique structural ID for a Node instance.

  Formula:
    Hash(
       Definition.Fingerprint['current_code_structure_hash']
       | Instance.Policies
       | Instance.Bindings (merged args/kwargs)
       | Instance.PuritySalt (if impure)
    )
~~~~~
~~~~~python.new
"HashingService.compute_node_instance_hash": |-
  Computes the unique structural ID for a Node instance.

  Formula:
    Hash(
       Definition.Fingerprint['canonical_code_structure_hash']
       | Instance.Policies
       | Instance.Bindings (merged args/kwargs)
       | Instance.PuritySalt (if impure)
    )
~~~~~

### 下一步建议

我们已经定位并修复了所有已知的 `current_code_structure_hash` 残留。现在请执行此计划，然后我们应该立即重新运行测试套件。如果所有测试都通过，我们就可以安全地继续推进路线图的 **Phase 3: 运行时层** 的实现。
