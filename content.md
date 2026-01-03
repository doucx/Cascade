你的分析非常精准。目前的 `id` 和 `structural_id` 命名确实成为了系统中的语义噪声，掩盖了逻辑层身份（基于哈希的实例唯一性）与物理层身份（基于路径的可读性）之间的本质区别。

根据《架构公理：哈希强制长命名规范 v3.0》，我将执行这次全局重构，重点清理 `cascade-graph` 和 `cascade-engine` 中的模糊命名，并建立清晰的身份边界。

## [WIP] refactor: 统一逻辑层身份命名为 `current_node_instance_hash` 并清理模糊 ID

### 用户需求
1.  **全局更名**：将 `Node.structural_id` 及其在 `cascade-graph` 和 `cascade-engine` 中的所有相关引用统一更名为 `current_node_instance_hash`。
2.  **消除歧义**：根据盘点清单，将模糊的 `id` 变量根据其语义角色重命名（如 `run_id` -> `current_run_id`, `msg_id` -> `semantic_message_id` 等）。
3.  **身份隔离**：在物理层（`cascade-spec` 中的物理节点）保留 `id`（代表物理路径），但在逻辑层（v2.0 节点）强制使用哈希命名。

### 评论
这是一次具有战略意义的“去模糊化”操作。通过将 `structural_id` 更名为 `current_node_instance_hash`，我们不仅遵循了 v3.0 的长命名公理，更在代码层面明确了：逻辑节点的身份是**计算出来的瞬时状态**（Current Instance Hash），而不是一个随意的字符串。

### 目标
1.  修改 `cascade-spec` 接口协议，使参数名体现角色。
2.  重构 `cascade-graph` 的核心模型和构建逻辑。
3.  重构 `cascade-engine` 的状态存储、解析器和执行策略。
4.  确保所有重命名操作字节级准确，不破坏现有功能。

### 基本原理
遵循 `[State]_[Source]_[Object]_hash` 的四段式构造法：
- `current_node_instance_hash`：代表逻辑图中一个特定参数化的节点实例身份。
- `current_run_id`：代表一次执行会话的 UUID。
- `semantic_message_id`：代表消息总线中的语义契约。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/engine #comp/graph #comp/spec #concept/state #scope/core
#ai/instruct
#task/domain/core #task/object/identity-refactor #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 重构 `cascade-spec` 协议层

我们将首先修改底层协议定义，为上层实现提供明确的语义导向。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/fingerprint.py
~~~~~
~~~~~python.old
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Fingerprint":
        internal_hashes = {}
        for key, value in data.items():
            cls._validate_key(key)
            if value is not None:
                internal_hashes[key] = str(value)
        return cls(_hashes=internal_hashes)
~~~~~
~~~~~python.new
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Fingerprint":
        current_fingerprint_hashes = {}
        for key, value in data.items():
            cls._validate_key(key)
            if value is not None:
                current_fingerprint_hashes[key] = str(value)
        return cls(_hashes=current_fingerprint_hashes)
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/protocols.py
~~~~~
~~~~~python.old
class CachePolicy(Protocol):
    async def check(self, task_id: str, inputs: Dict[str, Any]) -> Any: ...

    async def save(self, task_id: str, inputs: Dict[str, Any], output: Any) -> None: ...


class StateBackend(Protocol):
    async def put_result(self, node_id: str, result: Any) -> None: ...

    async def get_result(self, node_id: str) -> Optional[Any]: ...

    async def has_result(self, node_id: str) -> bool: ...

    async def mark_skipped(self, node_id: str, reason: str) -> None: ...

    async def get_skip_reason(self, node_id: str) -> Optional[str]: ...
~~~~~
~~~~~python.new
class CachePolicy(Protocol):
    async def check(self, current_node_instance_hash: str, inputs: Dict[str, Any]) -> Any: ...

    async def save(self, current_node_instance_hash: str, inputs: Dict[str, Any], output: Any) -> None: ...


class StateBackend(Protocol):
    async def put_result(self, current_node_instance_hash: str, result: Any) -> None: ...

    async def get_result(self, current_node_instance_hash: str) -> Optional[Any]: ...

    async def has_result(self, current_node_instance_hash: str) -> bool: ...

    async def mark_skipped(self, current_node_instance_hash: str, reason: str) -> None: ...

    async def get_skip_reason(self, current_node_instance_hash: str) -> Optional[str]: ...
~~~~~

#### Acts 2: 重构 `cascade-graph` 逻辑层

现在修改逻辑图模型，将 `structural_id` 正式退役。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python.old
@dataclass
class Node:
    # Stable identifier for the node instance in the graph.
    structural_id: str
~~~~~
~~~~~python.new
@dataclass
class Node:
    # Stable identifier for the node instance in the graph (Current Instance Hash).
    current_node_instance_hash: str
~~~~~
~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python.old
    def __eq__(self, other):
        if not isinstance(other, Node):
            return NotImplemented
        return self.structural_id == other.structural_id

    def __hash__(self):
        return hash(self.structural_id)
~~~~~
~~~~~python.new
    def __eq__(self, other):
        if not isinstance(other, Node):
            return NotImplemented
        return self.current_node_instance_hash == other.current_node_instance_hash

    def __hash__(self):
        return hash(self.current_node_instance_hash)
~~~~~
~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python.old
@dataclass
class Graph:
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    _node_index: Dict[str, Node] = field(default_factory=dict, init=False, repr=False)

    def add_node(self, node: Node):
        if node.structural_id not in self._node_index:
            self.nodes.append(node)
            self._node_index[node.structural_id] = node

    def get_node(self, node_id: str) -> Optional[Node]:
        return self._node_index.get(node_id)
~~~~~
~~~~~python.new
@dataclass
class Graph:
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    _node_index: Dict[str, Node] = field(default_factory=dict, init=False, repr=False)

    def add_node(self, node: Node):
        if node.current_node_instance_hash not in self._node_index:
            self.nodes.append(node)
            self._node_index[node.current_node_instance_hash] = node

    def get_node(self, current_node_instance_hash: str) -> Optional[Node]:
        return self._node_index.get(current_node_instance_hash)
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python.old
        # ... Edge logic remains same
        incoming_edges = sorted(
            [e for e in graph.edges if e.target.structural_id == node.structural_id],
            key=lambda e: e.source.structural_id,
        )
        for edge in incoming_edges:
            components.append(
                f"Edge(from={edge.source.structural_id}, to={node.structural_id}, type={edge.edge_type.name})"
            )
~~~~~
~~~~~python.new
        # ... Edge logic remains same
        incoming_edges = sorted(
            [e for e in graph.edges if e.target.current_node_instance_hash == node.current_node_instance_hash],
            key=lambda e: e.source.current_node_instance_hash,
        )
        for edge in incoming_edges:
            components.append(
                f"Edge(from={edge.source.current_node_instance_hash}, to={node.current_node_instance_hash}, type={edge.edge_type.name})"
            )
~~~~~

#### Acts 3: 重构 `cascade-engine` 适配器与运行时

修改状态后端和执行流，确保它们与新的命名契约一致。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/state/in_memory.py
~~~~~
~~~~~python.old
class InMemoryStateBackend:
    def __init__(self, run_id: str):
        self._run_id = run_id
        self._results: Dict[str, Any] = {}
        self._skipped: Dict[str, str] = {}

    async def put_result(self, node_id: str, result: Any) -> None:
        self._results[node_id] = result

    async def get_result(self, node_id: str) -> Optional[Any]:
        return self._results.get(node_id)

    async def has_result(self, node_id: str) -> bool:
        return node_id in self._results

    async def mark_skipped(self, node_id: str, reason: str) -> None:
        self._skipped[node_id] = reason

    async def get_skip_reason(self, node_id: str) -> Optional[str]:
        return self._skipped.get(node_id)
~~~~~
~~~~~python.new
class InMemoryStateBackend:
    def __init__(self, current_run_id: str):
        self._current_run_id = current_run_id
        self._results: Dict[str, Any] = {}
        self._skipped: Dict[str, str] = {}

    async def put_result(self, current_node_instance_hash: str, result: Any) -> None:
        self._results[current_node_instance_hash] = result

    async def get_result(self, current_node_instance_hash: str) -> Optional[Any]:
        return self._results.get(current_node_instance_hash)

    async def has_result(self, current_node_instance_hash: str) -> bool:
        return current_node_instance_hash in self._results

    async def mark_skipped(self, current_node_instance_hash: str, reason: str) -> None:
        self._skipped[current_node_instance_hash] = reason

    async def get_skip_reason(self, current_node_instance_hash: str) -> Optional[str]:
        return self._skipped.get(current_node_instance_hash)
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/flow.py
~~~~~
~~~~~python.old
class FlowManager:
    def __init__(
        self, graph: Graph, target_node_id: str, instance_map: Dict[str, Node]
    ):
        self.graph = graph
        self.target_node_id = target_node_id
        self.instance_map = instance_map

        self.in_edges: Dict[str, List[Edge]] = defaultdict(list)
        self.routers_by_selector: Dict[str, List[Edge]] = defaultdict(list)
        self.route_source_map: Dict[str, Dict[str, Any]] = defaultdict(dict)

        # Reference counting for pruning
        # Initial demand = Out-degree (number of consumers)
        self.downstream_demand: Dict[str, int] = defaultdict(int)

        for edge in self.graph.edges:
            self.in_edges[edge.target.structural_id].append(edge)
            self.downstream_demand[edge.source.structural_id] += 1

            if edge.router:
                selector_node = self._get_node_from_instance(edge.router.selector)
                if selector_node:
                    self.routers_by_selector[selector_node.structural_id].append(edge)

                for key, route_result in edge.router.routes.items():
                    route_node = self._get_node_from_instance(route_result)
                    if route_node:
                        self.route_source_map[edge.target.structural_id][
                            route_node.structural_id
                        ] = key

        # The final target always has at least 1 implicit demand (the user wants it)
        self.downstream_demand[target_node_id] += 1
~~~~~
~~~~~python.new
class FlowManager:
    def __init__(
        self, graph: Graph, target_node_instance_hash: str, instance_map: Dict[str, Node]
    ):
        self.graph = graph
        self.target_node_instance_hash = target_node_instance_hash
        self.instance_map = instance_map

        self.in_edges: Dict[str, List[Edge]] = defaultdict(list)
        self.routers_by_selector: Dict[str, List[Edge]] = defaultdict(list)
        self.route_source_map: Dict[str, Dict[str, Any]] = defaultdict(dict)

        # Reference counting for pruning
        # Initial demand = Out-degree (number of consumers)
        self.downstream_demand: Dict[str, int] = defaultdict(int)

        for edge in self.graph.edges:
            self.in_edges[edge.target.current_node_instance_hash].append(edge)
            self.downstream_demand[edge.source.current_node_instance_hash] += 1

            if edge.router:
                selector_node = self._get_node_from_instance(edge.router.selector)
                if selector_node:
                    self.routers_by_selector[selector_node.current_node_instance_hash].append(edge)

                for key, route_result in edge.router.routes.items():
                    route_node = self._get_node_from_instance(route_result)
                    if route_node:
                        self.route_source_map[edge.target.current_node_instance_hash][
                            route_node.current_node_instance_hash
                        ] = key

        # The final target always has at least 1 implicit demand (the user wants it)
        self.downstream_demand[target_node_instance_hash] += 1
~~~~~

### 下一步建议

我们已经开启了这次大规模重命名重构的第一步。目前只完成了 `cascade-spec` 和部分 `cascade-graph` 与 `cascade-engine` 的核心类。

由于涉及文件较多，且 lint report 指出了 168 处警告，接下来的计划建议：
1.  **分模块推进**：依次完成 `cascade-compiler` 和 `cascade-vm` 的重命名。
2.  **清理局部变量**：特别是在 `resolvers.py` 和 `processor.py` 中，将函数内部的 `node_id`, `run_id`, `msg_id` 彻底按照公理规范化。
3.  **验证测试**：在重构完 `cascade-engine` 和 `cascade-graph` 后，立即运行集成测试确保 `Node` 对象的 interning 和 hash-consing 依然有效。

如果你准备好了，我将继续生成针对 `resolvers.py` 和 `processor.py` 的重构指令。
