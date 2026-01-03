## [WIP] fix: 修复 build_graph 解包错误和 Mock Executor 签名不匹配问题

### 用户需求
修复由于 API 变更（`build_graph` 返回值增加、`Executor` 协议变更）导致的大量测试失败。

### 评论
这些错误主要是由于最近的重构（解耦 Node 和 Callable，增加 Registry）没有同步更新所有下游代码和测试工具导致的。

### 目标
1.  更新 `SpyExecutor` 和 `MockExecutor` 以匹配新的 `Executor.execute` 签名。
2.  更新 `packages/cascade-application` 和 `packages/cascade-sdk` 中对 `build_graph` 的调用，正确处理 3 个返回值。
3.  更新 `serialize.py` 以支持从 `executable_registry` 查找 callable，而不是从 `Node` 对象直接获取。
4.  读取并修复具体的测试文件，解决 `NameError` 和本地 Mock 类签名不匹配的问题。

### 基本原理
-   **协议一致性**: `SpyExecutor` 作为测试工具，必须严格遵守 `Executor` Protocol。
-   **构建一致性**: `build_graph` 的签名变更必须在所有调用处传播。
-   **序列化修复**: 由于 `TaskNode` 不再持有 `callable_obj`，序列化逻辑必须依赖外部传入的 `registry`。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #comp/runtime #scope/core #ai/instruct #task/domain/testing #task/object/executor-mock #task/action/fix-signature #task/state/begin

---

### Script

#### Acts 1: 读取受影响的测试文件
我们需要查看那些包含本地 Mock 类或引用错误的测试文件。

~~~~~act
read_file
packages/cascade-engine/tests/integration/test_engine_concurrency.py
~~~~~

~~~~~act
read_file
packages/cascade-engine/tests/integration/test_engine_constraints.py
~~~~~

~~~~~act
read_file
packages/cascade-graph/tests/unit/test_serialize.py
~~~~~

~~~~~act
read_file
packages/cascade-sdk/tests/unit/test_visualize.py
~~~~~

#### Acts 2: 修复 `testing.py` 中的 Mock Executor
更新 `MockExecutor` 和 `SpyExecutor` 以接受 `callable_obj` 参数。

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


class MockExecutor(Executor):
    def __init__(self, delay: float = 0, return_value: Any = "result"):
        self.delay = delay
        self.return_value = return_value

    async def execute(self, node: Node, args: List[Any], kwargs: Dict[str, Any]):
        if self.delay > 0:
            await asyncio.sleep(self.delay)

        # A simple logic to return something from inputs if available
        if args:
            return args[0]
        if kwargs:
            return next(iter(kwargs.values()))

        return self.return_value
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


class MockExecutor(Executor):
    def __init__(self, delay: float = 0, return_value: Any = "result"):
        self.delay = delay
        self.return_value = return_value

    async def execute(
        self,
        node: Node,
        callable_obj: Callable,
        args: List[Any],
        kwargs: Dict[str, Any],
    ):
        if self.delay > 0:
            await asyncio.sleep(self.delay)

        # A simple logic to return something from inputs if available
        if args:
            return args[0]
        if kwargs:
            return next(iter(kwargs.values()))

        return self.return_value
~~~~~

#### Acts 3: 修复 `cascade-application` 中的 `build_graph` 调用
`build_graph` 现在返回 `(graph, instance_map, registry)`。

~~~~~act
patch_file
packages/cascade-application/src/cascade/app/__init__.py
~~~~~
~~~~~python.old
        # 1. Build Graph
        graph, _ = build_graph(self.workflow_target)

        # 2. Resolve Plan using the app's solver
~~~~~
~~~~~python.new
        # 1. Build Graph
        graph, _, _ = build_graph(self.workflow_target)

        # 2. Resolve Plan using the app's solver
~~~~~

~~~~~act
patch_file
packages/cascade-application/src/cascade/app/__init__.py
~~~~~
~~~~~python.old
        if isinstance(self.raw_target, (list, tuple)) and not self.raw_target:
            return "\n".join(["digraph CascadeWorkflow {", '  rankdir="TB";', "}"])

        graph, _ = build_graph(self.workflow_target)

        dot_parts = [
~~~~~
~~~~~python.new
        if isinstance(self.raw_target, (list, tuple)) and not self.raw_target:
            return "\n".join(["digraph CascadeWorkflow {", '  rankdir="TB";', "}"])

        graph, _, _ = build_graph(self.workflow_target)

        dot_parts = [
~~~~~

#### Acts 4: 修复 `cascade-sdk` 中的 `lisp.py`

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

### 下一步建议
等待测试文件内容读取完毕后，我将：
1.  修复 `test_engine_concurrency.py` 和 `test_engine_constraints.py` 中的 Mock 类定义。
2.  修复 `test_serialize.py` 和 `test_visualize.py` 中的 `build_graph` 解包。
3.  更新 `serialize.py` 逻辑以支持 Registry。
