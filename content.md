你的分析完全正确。这是一个典型的循环导入（circular import）错误，它揭示了一个架构上的深层问题：

1.  **`cascade.graph.build`** (在 `cascade-graph` 包中) 依赖 `cascade.compiler.hashing`。
2.  **`cascade.compiler.hashing`** (在 `cascade-compiler` 包中) 又反过来依赖 `cascade.graph.model`。

这创建了一个不可解析的包间依赖环，导致 Python 解释器在加载模块时失败。`graph` 包作为更底层的模型定义，绝对不能依赖于更高层的 `compiler` 包。

**解决方案**：我们将通过修改 `cascade.compiler.hashing` 来打破这个循环。它对 `cascade.graph.model.Node` 的依赖仅仅是为了一个类型提示和访问 `.current_node_instance_hash` 属性。我们可以通过使用 `typing.Any` (鸭子类型) 来移除这个硬性的导入依赖，从而切断循环。

这是一个纠正性的修复步骤，然后我们就可以继续我们的 TDD 流程。

## [WIP] fix: 解除 graph 和 compiler 包之间的循环导入

### 错误分析
`pytest` 在收集测试时失败，报告了一个 `ImportError`，指出 `cascade.compiler.hashing` 和 `cascade.graph` 之间存在循环导入。`GraphBuilder` (在 `graph` 包中) 需要 `HashingService` (在 `compiler` 包中) 来计算哈希，而 `HashingService` 需要 `Node` 的类型定义 (在 `graph` 包中) 来进行类型提示，从而形成了依赖环。

### 评论
这是一个重要的架构健康度修复。包之间必须保持单向依赖的层次结构。这个修复通过在编译器层使用“鸭子类型”来解耦对具体图模型的依赖，从而恢复了正确的依赖方向。

### 目标
1.  修改 `packages/cascade-compiler/src/cascade/compiler/hashing.py`。
2.  移除对 `cascade.graph.model` 的直接导入。
3.  使用 `typing.Any` 替代 `Node` 和 `Graph` 的类型提示，以打破循环。
4.  确保测试收集能够成功。

### 基本原理
Python 的动态特性允许我们移除编译时的类型依赖，只要在运行时对象具有预期的属性即可。通过将类型提示从 `Node` 改为 `Any`，我们告诉静态分析器“相信我，这个对象在运行时会有我需要的属性”，从而在不改变运行时行为的情况下解决了导入问题。

### 标签
#intent/fix #flow/ready #priority/critical #comp/compiler #comp/graph #scope/dx #ai/instruct #task/domain/architecture #task/object/dependency-graph #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 修改 `hashing.py` 以打破循环

我们将修改 `hashing.py`，移除对 `cascade.graph.model` 的导入，并相应地调整类型提示。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/hashing.py
~~~~~
~~~~~python.old
import hashlib
from typing import Any, List, Dict
from cascade.graph.model import Graph, Node
from cascade.spec.ir.models import TaskDef
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import Inject


class HashingService:
    def compute_node_instance_hash(
        self,
        definition: TaskDef,
        result: Any,  # LazyResult or MappedLazyResult
        dep_nodes: Dict[str, Node],
    ) -> str:
        # 1. Start with the Stable Code Fingerprint
        code_hash = definition.fingerprint["current_code_structure_hash"]
        components = [f"CodeHash:{code_hash}"]
~~~~~
~~~~~python.new
import hashlib
from typing import Any, List, Dict
from cascade.spec.ir.models import TaskDef
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import Inject


class HashingService:
    def compute_node_instance_hash(
        self,
        definition: TaskDef,
        result: Any,  # LazyResult or MappedLazyResult
        dep_nodes: Dict[str, Any],  # Changed from Node to Any to break import cycle
    ) -> str:
        # 1. Start with the Stable Code Fingerprint
        code_hash = definition.fingerprint["current_code_structure_hash"]
        components = [f"CodeHash:{code_hash}"]
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/hashing.py
~~~~~
~~~~~python.old
    def _get_merkle_hash(self, components: List[str]) -> str:
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _build_hash_components(self, obj: Any, dep_nodes: Dict[str, Node]) -> List[str]:
        # This recursive helper remains largely similar, just updated type hints if needed
        components = []

        if isinstance(obj, (LazyResult, MappedLazyResult)):
            node = dep_nodes[obj._uuid]
            components.append(f"LAZY({node.current_node_instance_hash})")

        elif isinstance(obj, Router):
            components.append("Router{")
~~~~~
~~~~~python.new
    def _get_merkle_hash(self, components: List[str]) -> str:
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _build_hash_components(self, obj: Any, dep_nodes: Dict[str, Any]) -> List[str]:
        # This recursive helper remains largely similar, just updated type hints if needed
        components = []

        if isinstance(obj, (LazyResult, MappedLazyResult)):
            node = dep_nodes[obj._uuid]
            components.append(f"LAZY({node.current_node_instance_hash})")

        elif isinstance(obj, Router):
            components.append("Router{")
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/hashing.py
~~~~~
~~~~~python.old
class BlueprintHasher:
    # Existing logic for Blueprint hashing (can be updated later if needed)
    def compute_hash(self, graph: Graph) -> str:
        all_components = []
        sorted_nodes = sorted(graph.nodes, key=lambda n: n.current_node_instance_hash)
        for node in sorted_nodes:
            all_components.extend(self._get_node_components(node, graph))
        return self._get_merkle_hash(all_components)

    def _get_merkle_hash(self, components: List[str]) -> str:
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _get_node_components(self, node: Node, graph: Graph) -> List[str]:
        # Updated to use node.definition
        components = [f"Node({node.definition.name}, type={node.node_type})"]
        components.append(
            f"CodeHash({node.definition.fingerprint['current_code_structure_hash']})"
        )
~~~~~
~~~~~python.new
class BlueprintHasher:
    # Existing logic for Blueprint hashing (can be updated later if needed)
    def compute_hash(self, graph: Any) -> str:
        all_components = []
        sorted_nodes = sorted(graph.nodes, key=lambda n: n.current_node_instance_hash)
        for node in sorted_nodes:
            all_components.extend(self._get_node_components(node, graph))
        return self._get_merkle_hash(all_components)

    def _get_merkle_hash(self, components: List[str]) -> str:
        fingerprint = "|".join(components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _get_node_components(self, node: Any, graph: Any) -> List[str]:
        # Updated to use node.definition
        components = [f"Node({node.definition.name}, type={node.node_type})"]
        components.append(
            f"CodeHash({node.definition.fingerprint['current_code_structure_hash']})"
        )
~~~~~

### 下一步建议
我们已经解决了阻断性的导入错误。现在，我将重新运行测试，以确认之前的重构 (`feat: 实现 Backend 拓扑生成器`) 是否能按预期通过。如果通过，我们将继续进行 **Phase 3.3**。
