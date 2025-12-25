我们已成功进入 RED 状态：测试用例确认了当前系统无法区分两个相同的 Impure 任务实例。

现在我们将修改哈希逻辑，引入“任务纯度”检查。

## [WIP] feat(graph): 在哈希计算中实现纯度检查

### 用户需求
使 `HashingService` 能够识别任务的 `pure` 属性。
- 对于 `pure=False`（默认，Impure）的任务，在哈希计算中注入实例 UUID 作为 Salt，确保每次调用生成唯一的节点 ID。
- 对于 `pure=True`（Pure）的任务，保持原有的基于内容的哈希逻辑，确保相同的输入生成相同的节点 ID（去重）。

### 评论
这是 CP-006 的核心实现。通过简单的 UUID 注入，我们从根本上改变了引擎对“节点身份”的判定方式，解决了副作用任务被意外去重的问题，同时保留了纯函数任务的优化能力。

### 目标
1.  修改 `cascade-graph` 中的 `HashingService`。
2.  在 `_compute_lazy_result_hash` 和 `_compute_mapped_result_hash` 中添加对 `pure` 属性的检查。
3.  通过现有的测试用例。

### 基本原理
利用 `LazyResult` 和 `MappedLazyResult` 自身已有的 `_uuid` 字段作为天然的 Instance Salt。对于 Impure 任务，将其加入哈希计算流程即可破坏结构哈希的碰撞，从而强制生成新的节点。

### 标签
#intent/build #flow/ready #priority/high #comp/graph #concept/state #scope/core #ai/instruct #task/domain/core #task/object/task-purity #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 修改 HashingService 以支持 Purity

我们将修改 `packages/cascade-graph/src/cascade/graph/hashing.py`，在计算哈希时检查任务的 `pure` 属性。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python
    def _compute_lazy_result_hash(
        self, result: LazyResult, dep_nodes: Dict[str, Node]
    ) -> str:
        # 1. Base Components (Task identity and Policies)
        base_comps = [f"Task({getattr(result.task, 'name', 'unknown')})"]
        if result._retry_policy:
            rp = result._retry_policy
            base_comps.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
~~~~~
~~~~~python
    def _compute_lazy_result_hash(
        self, result: LazyResult, dep_nodes: Dict[str, Node]
    ) -> str:
        # 1. Base Components (Task identity and Policies)
        base_comps = [f"Task({getattr(result.task, 'name', 'unknown')})"]

        # [CP-006] Purity Check
        # Default is Impure (pure=False). Impure tasks get a unique salt (UUID)
        # to ensure every instance is a unique node in the graph.
        is_pure = getattr(result.task, "pure", False)
        if not is_pure:
            base_comps.append(f"Salt({result._uuid})")

        if result._retry_policy:
            rp = result._retry_policy
            base_comps.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python
    def _compute_mapped_result_hash(
        self, result: MappedLazyResult, dep_nodes: Dict[str, Node]
    ) -> str:
        base_comps = [f"Map({getattr(result.factory, 'name', 'factory')})"]

        meta_comps = []
        if result._condition:
            meta_comps.append("Condition:PRESENT")
~~~~~
~~~~~python
    def _compute_mapped_result_hash(
        self, result: MappedLazyResult, dep_nodes: Dict[str, Node]
    ) -> str:
        base_comps = [f"Map({getattr(result.factory, 'name', 'factory')})"]

        # [CP-006] Purity Check for Map
        is_pure = getattr(result.factory, "pure", False)
        if not is_pure:
            base_comps.append(f"Salt({result._uuid})")

        meta_comps = []
        if result._condition:
            meta_comps.append("Condition:PRESENT")
~~~~~

### 下一步建议
运行测试 `pytest tests/core/test_purity_model.py`。
预期结果：测试应该通过 (GREEN)。
如果测试通过，我们将提交这些更改。
