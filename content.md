好的，我分析了 `pyright` 报告的 9 个错误。你的判断是正确的，根源主要在于模块间的接口定义（`__init__.py` 的导出和 `Protocol` 定义）与实现不匹配，以及一些类型检查器难以静态推断的代码模式。

我将分步修复这些问题，确保类型系统的一致性。

## [WIP] fix: 解决 pyright 类型检查错误

### 错误分析

`pyright` 报告的错误可以归结为四个主要类别：

1.  **未知导入符号 (Unknown Import Symbol)**: 在 `cascade/runtime/host/instance.py` 中，多个类（如 `ConstraintManager`, `InMemoryStateBackend` 等）无法被正确解析。这是因为它们虽然定义在子模块中，但并未被其所在包的 `__init__.py` 文件导出，导致从包级别导入失败。
2.  **协议与实现不匹配 (Protocol Mismatch)**: 在 `cascade/runtime/legacy/processor.py` 中，调用 `executor.execute` 时传递了 4 个参数，但这与 `Executor` 协议中定义的 3 个参数不符。`LocalExecutor` 的实现接受 4 个参数，因此需要更新 `Executor` 协议以使其与实现保持一致。
3.  **类型属性与异步错误 (Attribute & Async Errors)**: 在 `cascade/runtime/legacy/strategies/vm.py` 中存在三个问题：
    *   一个同步函数被用作需要异步函数的 `add_sink` 回调，违反了 `Awaitable` 协议。
    *   `_collect_lazy_results` 函数错误地尝试访问 `MappedLazyResult` 对象上不存在的 `.args` 和 `.kwargs` 属性，它应该访问 `.mapping_kwargs`。
4.  **动态属性分配 (Dynamic Attribute Assignment)**: 在 `cascade/runtime/services/observability/events.py` 中，通过“猴子补丁”的方式为 `Event` 类动态分配了 `from_ir` 方法。`pyright` 无法静态地知道这个属性的存在，因此报错。

### 用户需求

修复 `pyright packages/cascade-runtime` 命令报告的所有 9 个类型检查错误。

### 评论

这些是大型 Python 项目中常见的类型静态分析问题。通过修复它们，我们可以增强代码的健壮性、可维护性和开发者的编码体验（DX），确保重构和未来的功能开发更加安全。

### 目标

1.  修复所有模块的 `__init__.py` 文件，确保必要的类被正确导出。
2.  更新 `Executor` 协议，使其 `execute` 方法的签名与 `LocalExecutor` 的实现和 `NodeProcessor` 中的调用相匹配。
3.  修正 `VMExecutionStrategy` 中的异步回调类型错误和对 `MappedLazyResult` 的属性访问错误。
4.  修改 `Event` 类的定义，使其静态地声明 `from_ir` 方法，以满足类型检查器的要求。
5.  最终目标是让 `pyright` 检查通过，不再报告任何错误。

### 基本原理

我们将采用最直接和正确的方式解决这些问题：

-   对于导入错误，我们将通过在相应的 `__init__.py` 文件中添加 `from .module import Class` 和 `__all__` 列表来显式导出接口。
-   对于协议不匹配，我们将更新 `cascade-spec` 中的 `protocols.py` 文件，使协议成为其实现的“超集”，保证类型兼容性。
-   对于 `vm.py` 中的错误，我们将把回调函数改为 `async def`，并重构 `_collect_lazy_results` 以正确处理两种不同的 `LazyResult` 类型。
-   对于动态分配问题，我们将在 `Event` 类中添加一个 `from_ir` 的静态方法存根（stub），然后在模块加载时用真实实现覆盖它。这既解决了循环导入问题，也满足了静态分析。

### 标签

#intent/fix #flow/ready #priority/high #comp/runtime #comp/spec #scope/dx #ai/instruct #task/domain/testing #task/object/type-checking #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 修复 `__init__.py` 导出问题

首先，我们将修复 `cascade-runtime` 包内几个模块的 `__init__.py` 文件，以正确导出它们的类，解决未知导入符号错误。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/services/constraints/__init__.py
~~~~~
~~~~~python
from .manager import ConstraintManager

__all__ = ["ConstraintManager"]
~~~~~

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/io/state/__init__.py
~~~~~
~~~~~python
from .in_memory import InMemoryStateBackend
from .redis import RedisStateBackend

__all__ = ["InMemoryStateBackend", "RedisStateBackend"]
~~~~~

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/__init__.py
~~~~~
~~~~~python
from .graph import GraphExecutionStrategy
from .vm import VMExecutionStrategy
from .base import ExecutionContext, ExecutionStrategy

__all__ = ["GraphExecutionStrategy", "VMExecutionStrategy", "ExecutionContext", "ExecutionStrategy"]
~~~~~

#### Acts 2: 更新 Executor 协议

接下来，修正 `Executor` 协议，使其与实现和调用保持一致。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/protocols.py
~~~~~
~~~~~python.old
class Executor(Protocol):
    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any: ...
~~~~~
~~~~~python.new
class Executor(Protocol):
    async def execute(
        self,
        node: Node,
        callable_obj: Callable,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any: ...
~~~~~

#### Acts 3: 修复 VM 策略中的类型错误

现在，我们处理 `vm.py` 中的异步回调和属性访问错误。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/vm.py
~~~~~
~~~~~python.old
            # Bridge: Sink to Future
            def _result_sink(token: Token):
                if not result_future.done():
                    result_future.set_result(token.payload)

            reactor.add_sink(target_stainer_id, "output_default", _result_sink)
~~~~~
~~~~~python.new
            # Bridge: Sink to Future
            async def _result_sink(token: Token):
                if not result_future.done():
                    result_future.set_result(token.payload)

            reactor.add_sink(target_stainer_id, "output_default", _result_sink)
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/legacy/strategies/vm.py
~~~~~
~~~~~python.old
    def _collect_lazy_results(self, target: Any) -> Dict[str, Any]:
        results = {}
        if isinstance(target, (LazyResult, MappedLazyResult)):
            results[target._uuid] = target
            for arg in target.args:
                results.update(self._collect_lazy_results(arg))
            for k, v in target.kwargs.items():
                results.update(self._collect_lazy_results(v))

            # Traverse Control Flow & Dependencies
            if target._condition:
                results.update(self._collect_lazy_results(target._condition))
            for dep in target._dependencies:
                results.update(self._collect_lazy_results(dep))

        elif isinstance(target, (list, tuple)):
            for item in target:
                results.update(self._collect_lazy_results(item))
        elif isinstance(target, dict):
            for v in target.values():
                results.update(self._collect_lazy_results(v))
        return results
~~~~~
~~~~~python.new
    def _collect_lazy_results(self, target: Any) -> Dict[str, Any]:
        results = {}
        # Use a stack to avoid deep recursion
        stack = [target]
        processed_uuids = set()

        while stack:
            current = stack.pop()

            if isinstance(current, (LazyResult, MappedLazyResult)):
                if current._uuid in processed_uuids:
                    continue
                processed_uuids.add(current._uuid)
                results[current._uuid] = current

                # Common dependencies
                if current._condition:
                    stack.append(current._condition)
                if hasattr(current, "_dependencies"):
                    stack.extend(current._dependencies)

                # Type-specific arguments
                if isinstance(current, LazyResult):
                    stack.extend(current.args)
                    stack.extend(current.kwargs.values())
                elif isinstance(current, MappedLazyResult):
                    stack.extend(current.mapping_kwargs.values())

            elif isinstance(current, (list, tuple)):
                stack.extend(current)
            elif isinstance(current, dict):
                stack.extend(current.values())

        return results
~~~~~

#### Acts 4: 解决 `events.py` 中的动态分配问题

最后，为 `Event` 类添加一个静态方法存根，以满足 `pyright` 的要求。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/observability/events.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class Event:
    event_id: str = field(default_factory=lambda: str(next(_event_id_gen)))
    timestamp: float = field(default_factory=time.time)

    # In a real run, this would be injected by the Engine context
    run_id: Optional[str] = None
~~~~~
~~~~~python.new
@dataclass(frozen=True)
class Event:
    event_id: str = field(default_factory=lambda: str(next(_event_id_gen)))
    timestamp: float = field(default_factory=time.time)

    # In a real run, this would be injected by the Engine context
    run_id: Optional[str] = None

    @staticmethod
    def from_ir(ir: "EventIR") -> "Event":
        # This is a stub for the type checker. The real implementation is assigned later
        # at the end of the file to break a circular dependency while keeping pyright happy.
        raise NotImplementedError
~~~~~

### 下一步建议

所有已知的 `pyright` 错误都已通过上述操作解决。我建议你现在重新运行 `pyright packages/cascade-runtime` 来验证所有问题是否已经修复。如果一切顺利，我们可以将这些修改作为一个完整的提交。
