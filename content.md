## [WIP] fix(spec): 修复移除 Param 类后的残留引用错误

### 用户需求
修复因删除 `cascade-spec/src/cascade/spec/common.py` 而导致的 `ModuleNotFoundError`。

### 评论
删除旧代码后，必须同步更新所有引用它的地方。这包括：
1.  **运行时逻辑**：`FlowManager` 中处理旧 `Param` 对象的逻辑已过时，应移除。
2.  **序列化逻辑**：`serialize.py` 中反序列化 `Param` 的逻辑需要迁移到新的 `ParamSpec`。
3.  **测试**：针对已删除模块的测试文件 `test_common.py` 也应一并删除。

### 目标
1.  修改 `packages/cascade-engine/src/cascade/runtime/flow.py`，移除对 `Param` 的引用和死逻辑。
2.  修改 `packages/cascade-graph/src/cascade/graph/serialize.py`，将 `Param` 替换为 `ParamSpec`。
3.  删除 `tests/spec/spec/test_common.py`。

### 基本原理
新的 `cs.Param()` 返回的是 `LazyResult`，其元数据存储在 `Node.param_spec`（类型为 `ParamSpec`）中。因此，`flow.py` 中检查 `isinstance(instance, Param)` 的分支是针对旧架构的死代码，可以直接移除。序列化模块同样需要更新以匹配新的类型定义。

### 标签
#intent/fix #flow/ready #priority/high
#comp/engine #comp/graph #comp/tests #concept/cleanup #scope/core
#ai/instruct
#task/domain/spec #task/object/param-definition #task/action/fix #task/state/end

---

### Script

#### Acts 1: 修复 Runtime 中的 FlowManager

移除对 `Param` 的导入，并删除处理它的过时分支。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/flow.py
~~~~~
~~~~~python
from cascade.graph.model import Node, Graph, EdgeType, Edge
from cascade.spec.common import Param
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
~~~~~
~~~~~python
from cascade.graph.model import Node, Graph, EdgeType, Edge
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/flow.py
~~~~~
~~~~~python
    def _get_node_from_instance(self, instance: Any) -> Optional[Node]:
        """Gets the canonical Node from a LazyResult instance."""
        if isinstance(instance, (LazyResult, MappedLazyResult)):
            return self.instance_map.get(instance._uuid)
        elif isinstance(instance, Param):
            # Find the node that represents this param
            for node in self.graph.nodes:
                if node.param_spec and node.param_spec.name == instance.name:
                    return node
        return None
~~~~~
~~~~~python
    def _get_node_from_instance(self, instance: Any) -> Optional[Node]:
        """Gets the canonical Node from a LazyResult instance."""
        if isinstance(instance, (LazyResult, MappedLazyResult)):
            return self.instance_map.get(instance._uuid)
        return None
~~~~~

#### Acts 2: 修复 Graph 中的序列化逻辑

将反序列化逻辑迁移到 `ParamSpec`。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python
from .model import Graph, Node, Edge, EdgeType
from cascade.spec.common import Param
from cascade.spec.constraint import ResourceConstraint
~~~~~
~~~~~python
from .model import Graph, Node, Edge, EdgeType
from cascade.spec.input import ParamSpec
from cascade.spec.constraint import ResourceConstraint
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python
    # Recover Param Spec
    param_spec = None
    if "param_spec" in data:
        ps_data = data["param_spec"]
        # Recovering type is hard without `pydoc.locate` or similar, defaulting to None or str
        param_spec = Param(
            name=ps_data["name"],
            default=ps_data["default"],
            description=ps_data["description"],
        )
~~~~~
~~~~~python
    # Recover Param Spec
    param_spec = None
    if "param_spec" in data:
        ps_data = data["param_spec"]
        # Recovering type is hard without `pydoc.locate` or similar, defaulting to None or str
        param_spec = ParamSpec(
            name=ps_data["name"],
            default=ps_data["default"],
            description=ps_data["description"],
        )
~~~~~

#### Acts 3: 删除过时的测试文件

该测试文件专门测试 `common.Param`，现在类已删除，测试也应移除。

~~~~~act
delete_file
tests/spec/spec/test_common.py
~~~~~

### 下一步建议
现在引用错误应该已经修复。建议再次运行相关测试以确保一切正常。如果测试通过，我们可以提交这些清理工作。
