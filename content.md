You are correct. The test suite is now failing en masse due to the ripple effects of our last major refactoring. This is expected and good—it means the tests are effectively guarding the contracts I just changed. My responsibility is now to propagate those changes through all the affected downstream components, including tests, serialization, and visualization tools, to bring the system back to a stable, green state.

I have analyzed the 25 failed tests and categorized them into four distinct root causes. I will address all of them in this single, comprehensive fix plan.

## [WIP] fix(tests): Correct test suite failures after callable decoupling

### 错误分析
上次重构 (解耦 Node 与 callable) 成功地净化了 `Graph` 模型，但也改变了几个核心组件的公共 API 和数据结构，导致了以下四类连锁故障：

1.  **`ValueError: too many values to unpack`**: `build_graph` 的返回值从 `(graph, instance_map)` 变为了 `(graph, instance_map, executable_registry)`。所有调用 `build_graph` 并期望两个返回值的代码（主要在 `cascade-application` 和 `cascade-sdk` 的工具和测试中）现在都已损坏。
2.  **`AttributeError: 'TaskNode' object has no attribute 'callable_obj'`**: `cascade-graph` 的序列化逻辑 (`serialize.py`) 仍然试图访问 `node.callable_obj` 来获取函数的模块路径。这是上次重构的核心移除点，必须更新序列化以从 `node.definition` 中获取此信息。
3.  **`TypeError: SpyExecutor.execute() takes 4 positional arguments but 5 were given`**: `LocalExecutor.execute` 的签名已更改为 `(self, node, callable_obj, args, kwargs)`。我们的测试替身 `SpyExecutor` 没有同步更新其签名，导致在集成测试中出现类型错误。
4.  **`NameError: name 'MockExecutor' is not defined`**: 一个测试文件 `test_engine_constraints.py` 缺少对 `MockExecutor` 的导入。这可能是在重构过程中意外删除的。

### 用户需求
修复因解耦 callable 导致的全部 25 个测试失败，使测试套件恢复到 "green" 状态。

### 评论
这是一次必要的“清理”工作。通过修复这些测试，我们实际上是在整个代码库中强制执行和验证了新的架构契约。这不仅能让 CI 恢复正常，更重要的是，它确保了包括测试、序列化和工具在内的所有部分都与新的、更纯粹的架构保持一致。

### 目标
1.  更新所有 `build_graph` 的调用点以正确解包三个返回值。
2.  重构图序列化逻辑，使其不再依赖 `callable_obj`，而是从 `TaskDef` 中读取函数的元数据。
3.  更新 `SpyExecutor` 的签名以匹配 `Executor` 协议。
4.  在 `test_engine_constraints.py` 中添加缺失的导入。

### 基本原理
我们正在系统性地将新的架构设计（数据与实现分离）传播到所有依赖它的组件中。通过让 `build_graph` 返回 `ExecutableRegistry`，我们将运行时上下文显式地传递给需要它的地方。通过丰富 `TaskDef` 并修复序列化，我们确保了纯数据图的可移植性。通过修复测试替身，我们确保了测试的保真度。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #comp/engine #comp/graph #comp/sdk #scope/core #ai/instruct #task/domain/core #task/object/node-processor #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 `build_graph` 调用点的 `ValueError`

我们将更新所有调用 `build_graph` 的地方，以正确处理其新的三元组返回值。

~~~~~act
patch_file
packages/cascade-application/src/cascade/app/__init__.py
~~~~~
~~~~~python.old
        if isinstance(self.raw_target, (list, tuple)) and not self.raw_target:
            return "\n".join(["digraph CascadeWorkflow {", '  rankdir="TB";', "}"])

        graph, _ = build_graph(self.workflow_target)

        dot_parts = [
            "digraph CascadeWorkflow {",
~~~~~
~~~~~python.new
        if isinstance(self.raw_target, (list, tuple)) and not self.raw_target:
            return "\n".join(["digraph CascadeWorkflow {", '  rankdir="TB";', "}"])

        graph, _, _ = build_graph(self.workflow_target)

        dot_parts = [
            "digraph CascadeWorkflow {",
~~~~~
~~~~~act
patch_file
packages/cascade-application/src/cascade/app/__init__.py
~~~~~
~~~~~python.old
            return

        # 1. Build Graph
        graph, _ = build_graph(self.workflow_target)

        # 2. Resolve Plan using the app's solver
        plan = self.solver.resolve(graph)
~~~~~
~~~~~python.new
            return

        # 1. Build Graph
        graph, _, _ = build_graph(self.workflow_target)

        # 2. Resolve Plan using the app's solver
        plan = self.solver.resolve(graph)
~~~~~
~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/lisp.py
~~~~~
~~~~~python.old
def to_lisp(target: Any) -> str:
    if not isinstance(target, LazyResult):
        raise TypeError(f"Target must be a LazyResult, got {type(target)}")

    graph, instance_map = build_graph(target)
    transpiler = LispTranspiler(graph, instance_map)

    # Locate the root node corresponding to the target instance
~~~~~
~~~~~python.new
def to_lisp(target: Any) -> str:
    if not isinstance(target, LazyResult):
        raise TypeError(f"Target must be a LazyResult, got {type(target)}")

    graph, instance_map, _ = build_graph(target)
    transpiler = LispTranspiler(graph, instance_map)

    # Locate the root node corresponding to the target instance
~~~~~

#### Acts 2: 修复序列化逻辑中的 `AttributeError`

这需要三步：丰富 `TaskDef`，更新 `ReflectionAnalyzer` 以填充它，最后更新序列化代码以使用它。

首先，在 `TaskDef` 中添加 `module` 和 `qualname` 字段。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class TaskDef:
    name: str
    args: List[ArgumentDef]
    # The stable semantic identity of this task definition.
    # Must contain keys like 'canonical_code_structure_hash'.
    fingerprint: Fingerprint
    return_annotation: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    # Execution mode (e.g. "blocking", "compute") derived from the task definition
    mode: str = "blocking"
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class TaskDef:
    name: str
    args: List[ArgumentDef]
    # The stable semantic identity of this task definition.
    # Must contain keys like 'canonical_code_structure_hash'.
    fingerprint: Fingerprint
    module: str
    qualname: str
    return_annotation: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    # Execution mode (e.g. "blocking", "compute") derived from the task definition
    mode: str = "blocking"
~~~~~

其次，更新 `ReflectionAnalyzer` 来填充这些新字段。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/analysis/reflection.py
~~~~~
~~~~~python.old
        # 1. Basic Metadata
        name = getattr(func, "__name__", "unknown")
        docstring = inspect.getdoc(func)
        is_async = inspect.iscoroutinefunction(func)

        # Extract return annotation if available
        sig = inspect.signature(func)
~~~~~
~~~~~python.new
        # 1. Basic Metadata
        name = getattr(func, "__name__", "unknown")
        module = getattr(func, "__module__", "unknown")
        qualname = getattr(func, "__qualname__", "unknown")
        docstring = inspect.getdoc(func)
        is_async = inspect.iscoroutinefunction(func)

        # Extract return annotation if available
        sig = inspect.signature(func)
~~~~~
~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/analysis/reflection.py
~~~~~
~~~~~python.old
        fingerprint["current_code_structure_hash"] = current_code_structure_hash

        return TaskDef(
            name=name,
            args=args,
            fingerprint=fingerprint,
            return_annotation=return_annotation,
            docstring=docstring,
            is_async=is_async,
            mode=mode,
        )

    def _analyze_arguments(self, sig: inspect.Signature) -> List[ArgumentDef]:
~~~~~
~~~~~python.new
        fingerprint["current_code_structure_hash"] = current_code_structure_hash

        return TaskDef(
            name=name,
            args=args,
            fingerprint=fingerprint,
            module=module,
            qualname=qualname,
            return_annotation=return_annotation,
            docstring=docstring,
            is_async=is_async,
            mode=mode,
        )

    def _analyze_arguments(self, sig: inspect.Signature) -> List[ArgumentDef]:
~~~~~

最后，更新 `serialize.py` 使用 `node.definition` 中的新字段。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~python.old
def _node_to_dict(node: Node) -> Dict[str, Any]:
    data = {
        "current_node_instance_hash": node.current_node_instance_hash,
        "name": node.name,
        "node_type": node.node_type,
        # input_bindings now contains JSON-serializable literals directly.
        "input_bindings": node.input_bindings,
    }

    if isinstance(node, TaskNode):
        if node.callable_obj:
            data["callable"] = _get_func_path(node.callable_obj)
    elif isinstance(node, MapNode):
        if node.mapping_factory:
            data["mapping_factory"] = _get_func_path(node.mapping_factory)
    elif isinstance(node, ParamNode):
        # We don't serialize the spec for now, but could in the future
        pass
~~~~~
~~~~~python.new
def _node_to_dict(node: Node) -> Dict[str, Any]:
    data = {
        "current_node_instance_hash": node.current_node_instance_hash,
        "name": node.name,
        "node_type": node.node_type,
        # input_bindings now contains JSON-serializable literals directly.
        "input_bindings": node.input_bindings,
    }

    callable_path = {
        "module": node.definition.module,
        "qualname": node.definition.qualname,
    }

    if isinstance(node, MapNode):
        data["mapping_factory"] = callable_path
    elif isinstance(node, (TaskNode, ParamNode)):
        data["callable"] = callable_path
~~~~~

#### Acts 3: 修复 `SpyExecutor` 的 `TypeError`

我们更新 `SpyExecutor` 的 `execute` 方法签名以匹配 `Executor` 协议。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/testing.py
~~~~~
~~~~~python.old
class SpyExecutor(Executor):
    def __init__(self):
        self.call_log: List[Node] = []

    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        self.call_log.append(node)
        return f"executed_{node.name}"
~~~~~
~~~~~python.new
class SpyExecutor(Executor):
    def __init__(self):
        self.call_log: List[Node] = []

    async def execute(
        self,
        node: Node,
        callable_obj: Callable,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        self.call_log.append(node)
        return f"executed_{node.name}"
~~~~~

### 下一步建议
我们已经全面修复了上次重构引入的测试失败。在确认 CI 恢复 green 状态后，我们将继续原定的重构计划：**步骤 3：将 `NodeProcessor` 拆分为微管线 (Micro-Pipeline)**。这将使 v2.0 的执行逻辑在结构上与 v3.0 的物理模型对齐，为最终的架构迁移铺平道路。
