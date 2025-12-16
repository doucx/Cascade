这是因为动态约束 (`.with_constraints(cpu=LazyResult)`) 在图构建时将 `LazyResult` 对象存储在了 `Node.constraints.requirements` 中，而 `json.dumps` 在序列化 `LazyResult` 时失败了。`LazyResult` 是一个内存中的指针，不是可序列化的数据类型。

我们将通过以下步骤修复此问题：在序列化包含动态约束的 `Node` 时，将 `LazyResult` 实例替换为其唯一的 `_uuid` 引用。

## [WIP] fix(graph): 修复动态约束中的 LazyResult JSON 序列化错误

### 错误分析
测试 `test_serialize_edge_types` 失败，因为 `Node.constraints.requirements` 中包含了不可序列化的 `LazyResult` 对象。序列化模块（`graph_to_dict`）在遇到这些对象时崩溃。

### 用户需求
修复 `TypeError: Object of type LazyResult is not JSON serializable` 错误，确保包含动态资源约束的工作流可以成功序列化和反序列化。

### 评论
这个修复是必需的，它清除了 `CSPSolver` 和 `EdgeType` 实现后产生的副作用。我们必须确保图的序列化模块能够安全地处理所有核心 `spec` 对象作为元数据或引用。

### 目标
1.  在 `src/cascade/graph/serialize.py` 中，修改 `_node_to_dict` 逻辑。
2.  在序列化 `ResourceConstraint.requirements` 时，将所有 `LazyResult` 或 `MappedLazyResult` 对象替换为一个包含其 `_uuid` 的字典引用 (`{"__lazy_ref": uuid}`)。
3.  确保 `RetryPolicy` 的 `backoff` 参数能够往返（已在上一个计划中处理，此处不再重复）。

### 基本原理
动态约束本质上是依赖图中的边（`EdgeType.CONSTRAINT`），因此在序列化 `Node` 自身时，我们只需要存储指向这些依赖的 UUID 引用，而不需要完整的对象，以避免序列化崩溃。反序列化后，图结构仍然完整，尽管需要更高级的逻辑才能使这种图具有运行时执行能力。

### 标签
#intent/fix #flow/ready #priority/high #comp/graph #concept/serialization #scope/core #ai/delegate #task/domain/graph #task/object/serialization #task/action/refinement #task/state/continue

---

### Script

#### Acts 1: 更新 `serialize.py` 的导入

确保 `LazyResult` 和 `MappedLazyResult` 被正确导入，以便在 `_node_to_dict` 中进行类型检查。

~~~~~act
patch_file
src/cascade/graph/serialize.py
~~~~~
~~~~~python
from ..spec.constraint import ResourceConstraint
from ..spec.lazy_types import RetryPolicy
from ..spec.task import Task
~~~~~
~~~~~python
from ..spec.constraint import ResourceConstraint
from ..spec.lazy_types import RetryPolicy, LazyResult, MappedLazyResult
from ..spec.task import Task
~~~~~

#### Acts 2: 修复 `_node_to_dict` 中的约束序列化逻辑

将 `LazyResult` 替换为其 UUID 引用，以防止 JSON 序列化器崩溃。

~~~~~act
patch_file
src/cascade/graph/serialize.py
~~~~~
~~~~~python
    if node.constraints:
        data["constraints"] = node.constraints.requirements

    return data
~~~~~
~~~~~python
    if node.constraints:
        # Dynamic constraints contain LazyResult/MappedLazyResult which are not JSON serializable.
        # We must replace them with their UUID reference.
        serialized_reqs = {}
        for res, amount in node.constraints.requirements.items():
            if isinstance(amount, (LazyResult, MappedLazyResult)):
                # Store the UUID reference as a JSON serializable dict.
                serialized_reqs[res] = {"__lazy_ref": amount._uuid}
            else:
                serialized_reqs[res] = amount
        data["constraints"] = serialized_reqs

    return data
~~~~~
