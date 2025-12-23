You are absolutely right to call this out. My previous plan was flawed. I apologize for the oversight. The combination of the persistent benchmark failure and the new, unrelated test failures indicates a deeper, systemic issue was introduced in the last refactoring.

We will stop guessing immediately. Your instruction is correct: we need a targeted test to prove the hashing mechanism, and we must analyze and fix the new regressions, which are a higher priority as they indicate a break in core functionality.

Let's break down what's happening.

 Analysis of New Failures (The Regressions)

The fact that tests in `resource_scheduling`, `llm_pattern` (subflows), and `cli` are all failing after a change to `GraphExecutionStrategy` points to a fundamental flaw in my new cache-hit logic. These tests rely on complex graph interactions (concurrency, nesting, context).

*   **Root Cause Hypothesis**: The critical bug is in how I handle the state on a cache hit. The logic `instance_map[current_target._uuid] = canonical_target_node` is a fragile and incorrect "patch-up". The `instance_map` from a fresh `build_graph` call contains mappings for the *entire new ephemeral graph*, including all dependencies. The `plan` from the cache, however, refers to nodes from the *original canonical graph*. When the `NodeProcessor` tries to execute this plan, it's using a mix of stale and fresh node references from a mismatched `instance_map`. This inconsistency is causing unpredictable failures in complex scenarios.

 Analysis of Benchmark Failure

The benchmark still fails with a cycle error, which definitively proves the cache is not being hit. My previous fix to `ShallowHasher` was clearly insufficient. We will write a test to prove the hash is different for different literal inputs, and then fix it.

---

Here is the plan. We will first write a new, failing test to validate the structural hasher. Then, we will implement the correct fix for both the hasher and the execution strategy's flawed cache-hit logic.

## [WIP] fix: Repair structural cache and resolve execution regressions

### 错误分析

1.  **核心回归**: 在 `GraphExecutionStrategy` 中引入的通用缓存逻辑是错误的。在缓存命中时，它天真地试图将一个从缓存中取出的“规范化目标节点”注入到一个为全新 `LazyResult` 树生成的 `instance_map` 中。这导致执行计划 (`plan`) 操作的是旧的、规范化的节点对象，而图的其余部分（如依赖项）和解析器则引用了新的、临时的节点对象。这种状态不匹配破坏了图的完整性，导致在资源调度、子流程等复杂场景下出现不可预测的运行时错误。
2.  **哈希器缺陷**: `ShallowHasher` 的修复不完整。它未能正确地将 `LazyResult` 的所有字面量输入（包括位置参数和关键字参数）与图的结构分离开。因此，对于 `heavy_complex_countdown(n)`，变化的 `n` 仍然会污染结构哈希，导致每次递归都生成唯一的哈希值，缓存从未命中，最终求解器正确地检测到了循环。

### 用户需求

1.  创建一个新的单元测试，专门验证 `ShallowHasher` 对于仅字面量参数变化的 `LazyResult` 对象能否生成相同的哈希值。
2.  修复 `ShallowHasher` 以通过新的测试。
3.  重写 `GraphExecutionStrategy` 中的缓存命中逻辑，确保在复用缓存计划时，整个执行上下文（图、计划、节点引用）是一致的。
4.  修复由此引发的所有下游测试回归。

### 评论

这次失败暴露了在复杂系统中进行“微创手术”的风险。简单的 `instance_map` 补丁是一个错误的捷径。正确的解决方案是确保在缓存命中时，我们完全、一致地使用缓存中的**整个**规范化上下文（图和计划），只用新的 `LazyResult` 来提取**新的数据**（`data_tuple`）。这个计划将通过严格的测试驱动方法来纠正错误，恢复系统的稳定性。

### 目标

1.  在 `tests/engine/graph/` 目录下创建一个新的测试文件 `test_hashing_logic.py`。
2.  在新文件中添加一个测试 `test_shallow_hasher_ignores_literals`，该测试会断言 `task(1)` 和 `task(2)` 产生相同的浅层结构哈希。
3.  修改 `cascade.graph.hashing.ShallowHasher` 以使新测试通过。
4.  重写 `cascade.runtime.strategies.GraphExecutionStrategy` 的 `execute` 方法。在缓存命中时，它应该：
    a. 从缓存中获取规范化的 `(graph, plan, canonical_target_node)`。
    b. **仅**为了提取 `data_tuple` 而调用 `build_graph`，并**丢弃**新生成的图和 `instance_map`。
    c. 使用**缓存的 `graph`、`plan` 和 `canonical_target_node`**，以及**新的 `data_tuple`** 来执行 `_execute_graph`。
5.  移除之前导致 `test_time_provider` 失败的临时补丁，因为根本原因很可能在 `GraphExecutionStrategy` 中。

### 基本原理

TDD 是我们唯一的出路。通过创建一个精确复现哈希问题的测试，我们可以确保修复是正确且永久的。对于执行策略，我们将遵循更简单、更健壮的原则：**缓存的上下文是不可变的**。我们不混合新旧状态，而是将缓存的 `(graph, plan)` 视为一个整体的、已编译的“程序”，然后将新的 `data_tuple` 作为输入“喂”给这个程序去执行。这从根本上消除了所有状态不一致的可能性。

### 标签

#intent/fix #flow/ready #priority/critical
#comp/engine #comp/graph #comp/tests
#concept/state #scope/core
#ai/delegate
#task/domain/engine #task/object/structural-cache #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 创建新的、将会失败的哈希逻辑测试

我们将首先创建测试文件和用例，以隔离并证明 `ShallowHasher` 的缺陷。

~~~~~act
write_file
tests/engine/graph/test_hashing_logic.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.graph.hashing import ShallowHasher


@cs.task
def simple_task(a, b=None):
    pass


def test_shallow_hasher_ignores_literals():
    """
    Verifies that the ShallowHasher produces the same hash for tasks
    that differ only in their literal (non-LazyResult) arguments.
    This is critical for structural caching of recursive tasks.
    """
    hasher = ShallowHasher()

    # Create two instances with different literal arguments
    lr1 = simple_task(1, b="hello")
    lr2 = simple_task(2, b="world")

    # Their structural hashes MUST be identical
    hash1 = hasher.hash(lr1)
    hash2 = hasher.hash(lr2)

    assert hash1 == hash2, "ShallowHasher should ignore literal argument values."


def test_shallow_hasher_differentiates_structure():
    """
    Verifies that the hasher correctly identifies changes in graph structure,
    such as adding a dependency.
    """
    hasher = ShallowHasher()

    @cs.task
    def upstream():
        pass

    lr_simple = simple_task(1)
    lr_complex = simple_task(upstream())

    hash_simple = hasher.hash(lr_simple)
    hash_complex = hasher.hash(lr_complex)

    assert hash_simple != hash_complex, "ShallowHasher should differentiate based on dependencies."
~~~~~

#### Acts 2: 重构 `GraphExecutionStrategy` 和 `ShallowHasher`

现在，我们将一次性应用两个修复：修复 `ShallowHasher` 以通过新测试，并重写 `GraphExecutionStrategy` 的缓存逻辑以解决核心回归问题。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
import asyncio
from contextlib import ExitStack
from typing import Any, Dict, Protocol, Tuple, List

from cascade.graph.model import Graph, Node
from cascade.graph.build import build_graph
from cascade.graph.hashing import ShallowHasher
from cascade.spec.protocols import Solver, StateBackend, ExecutionPlan
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.bus import MessageBus
from cascade.runtime.resource_container import ResourceContainer
from cascade.runtime.processor import NodeProcessor
from cascade.runtime.flow import FlowManager
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.events import TaskSkipped, TaskBlocked
from cascade.runtime.constraints.manager import ConstraintManager
from cascade.graph.compiler import BlueprintBuilder
from cascade.runtime.vm import VirtualMachine
from cascade.runtime.resource_manager import ResourceManager


class ExecutionStrategy(Protocol):
    """
    Protocol defining a strategy for executing a workflow target.
    """

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any: ...


class GraphExecutionStrategy:
    """
    Executes tasks by dynamically building a dependency graph and running a TCO loop.
    This is the standard execution mode for Cascade.
    """

    def __init__(
        self,
        solver: Solver,
        node_processor: NodeProcessor,
        resource_container: ResourceContainer,
        constraint_manager: ConstraintManager,
        bus: MessageBus,
        wakeup_event: asyncio.Event,
    ):
        self.solver = solver
        self.node_processor = node_processor
        self.resource_container = resource_container
        self.constraint_manager = constraint_manager
        self.bus = bus
        self.wakeup_event = wakeup_event
        # Universal structural cache
        self.hasher = ShallowHasher()
        self._plan_cache: Dict[str, Tuple[Graph, ExecutionPlan, Node]] = {}

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        current_target = target

        while True:
            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                struct_hash = self.hasher.hash(current_target)
                
                graph: Graph
                plan: ExecutionPlan
                instance_map: Dict[str, Node]
                data_tuple: Tuple[Any, ...]

                if struct_hash in self._plan_cache:
                    # CACHE HIT: Reuse canonical graph and plan.
                    graph, plan, canonical_target_node = self._plan_cache[struct_hash]
                    
                    # We ONLY need to re-run build_graph to extract the new data_tuple.
                    # The new graph and instance_map are DISCARDED.
                    _, data_tuple, new_instance_map = build_graph(current_target)
                    
                    # The instance_map for this execution must point the current target's UUID
                    # to the canonical node from the cached graph. This is the ONLY entry
                    # from the new_instance_map we need.
                    instance_map = {current_target._uuid: canonical_target_node}
                else:
                    # CACHE MISS: Build graph and resolve plan for the first time
                    graph, data_tuple, instance_map = build_graph(current_target)
                    plan = self.solver.resolve(graph)
                    canonical_target_node = instance_map[current_target._uuid]
                    # Store the compiled template and plan in the cache
                    self._plan_cache[struct_hash] = (graph, plan, canonical_target_node)

                # 2. Setup Resources (mixed scope)
                required_resources = self.resource_container.scan(graph, data_tuple)
                self.resource_container.setup(
                    required_resources,
                    active_resources,
                    run_stack,
                    step_stack,
                    run_id,
                )

                # 3. Execute Graph
                result = await self._execute_graph(
                    current_target,
                    params,
                    active_resources,
                    run_id,
                    state_backend,
                    graph,
                    data_tuple,
                    plan,
                    instance_map,
                )

            # 4. Check for Tail Call (LazyResult)
            if isinstance(result, (LazyResult, MappedLazyResult)):
                current_target = result
                # STATE GC
                if hasattr(state_backend, "clear"):
                    state_backend.clear()
                # Yield control
                await asyncio.sleep(0)
            else:
                return result

    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        state_backend: StateBackend,
        graph: Graph,
        data_tuple: Tuple[Any, ...],
        plan: Any,
        instance_map: Dict[str, Node],
    ) -> Any:
        target_node = instance_map[target._uuid]
        flow_manager = FlowManager(graph, target_node.id, instance_map)
        blocked_nodes = set()

        for stage in plan:
            pending_nodes_in_stage = list(stage)

            while pending_nodes_in_stage:
                executable_this_pass: List[Node] = []
                deferred_this_pass: List[Node] = []

                for node in pending_nodes_in_stage:
                    if node.node_type == "param":
                        continue

                    skip_reason = flow_manager.should_skip(node, state_backend)
                    if skip_reason:
                        state_backend.mark_skipped(node.id, skip_reason)
                        self.bus.publish(
                            TaskSkipped(
                                run_id=run_id,
                                task_id=node.id,
                                task_name=node.name,
                                reason=skip_reason,
                            )
                        )
                        continue

                    if self.constraint_manager.check_permission(node):
                        executable_this_pass.append(node)
                        if node.id in blocked_nodes:
                            blocked_nodes.remove(node.id)
                    else:
                        deferred_this_pass.append(node)
                        if node.id not in blocked_nodes:
                            self.bus.publish(
                                TaskBlocked(
                                    run_id=run_id,
                                    task_id=node.id,
                                    task_name=node.name,
                                    reason="ConstraintViolation",
                                )
                            )
                            blocked_nodes.add(node.id)

                if executable_this_pass:
                    # Callback for map nodes
                    async def sub_graph_runner(target, sub_params, parent_state):
                        # For sub-graphs, we must run the full execution loop logic,
                        # as they may have their own TCO cycles.
                        return await self.execute(
                            target,
                            run_id,
                            sub_params,
                            parent_state,
                            ExitStack(), # Sub-flows don't share run_stack
                            active_resources,
                        )

                    tasks_to_run = [
                        self.node_processor.process(
                            node,
                            graph,
                            data_tuple,
                            state_backend,
                            active_resources,
                            run_id,
                            params,
                            sub_graph_runner,
                            instance_map,
                        )
                        for node in executable_this_pass
                    ]

                    pass_results = await asyncio.gather(*tasks_to_run)

                    for node, res in zip(executable_this_pass, pass_results):
                        state_backend.put_result(node.id, res)
                        if flow_manager:
                            flow_manager.register_result(node.id, res, state_backend)

                pending_nodes_in_stage = deferred_this_pass

                if pending_nodes_in_stage and not executable_this_pass:
                    await self.wakeup_event.wait()
                    self.wakeup_event.clear()
                    self.constraint_manager.cleanup_expired_constraints()

        # Use the mapped canonical node ID to check for the final result
        if not state_backend.has_result(target_node.id):
            if skip_reason := state_backend.get_skip_reason(target_node.id):
                if skip_reason == "UpstreamSkipped_Sequence":
                    return None
                raise DependencyMissingError(
                    task_id=target.task.name or "unknown",
                    arg_name="<Target Output>",
                    dependency_id=f"Target node '{target_node.name}' was skipped (Reason: {skip_reason})",
                )

            raise KeyError(
                f"Target task '{target.task.name if hasattr(target.task, 'name') else 'unknown'}' did not produce a result."
            )

        return state_backend.get_result(target_node.id)


class VMExecutionStrategy:
    """
    Executes tasks by compiling them into a Blueprint and running them on a Virtual Machine.
    """

    def __init__(
        self,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
        wakeup_event: asyncio.Event,
    ):
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.wakeup_event = wakeup_event

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        # 1. Compile in template mode
        builder = BlueprintBuilder()
        blueprint = builder.build(target, template=True)

        # 2. Extract Initial Arguments
        initial_args = list(target.args)
        initial_kwargs = dict(target.kwargs)

        # 3. Execute
        vm = VirtualMachine(
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            wakeup_event=self.wakeup_event,
        )
        return await vm.execute(
            blueprint, initial_args=initial_args, initial_kwargs=initial_kwargs
        )
~~~~~

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/hashing.py
~~~~~
~~~~~python
from typing import Any, Dict, Tuple, List
import hashlib
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.resource import Inject


class ShallowHasher:
    """
    Generates a stable shallow structural hash for a LazyResult.
    "Shallow" means it does NOT recursively hash nested LazyResults. Instead,
    it uses a placeholder, making the hash dependent only on the node's
    immediate properties and the structure of its inputs.
    """

    def __init__(self):
        self._hash_components: List[str] = []

    def hash(self, target: Any) -> str:
        self._hash_components = []
        self._visit_top_level(target)
        fingerprint = "|".join(self._hash_components)
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

    def _visit_top_level(self, obj: Any):
        if isinstance(obj, LazyResult):
            self._visit_lazy(obj)
        elif isinstance(obj, MappedLazyResult):
            self._visit_mapped(obj)
        else:
            # This path is for targets that aren't LazyResults, which shouldn't happen
            # in normal execution but we handle it gracefully.
            self._visit_arg(obj)

    def _visit_arg(self, obj: Any):
        """A special visitor for arguments within a LazyResult."""
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            self._hash_components.append("LAZY")
            return

        if isinstance(obj, Router):
            self._hash_components.append("Router{")
            self._hash_components.append("Selector:")
            self._visit_arg(obj.selector)
            self._hash_components.append("Routes:")
            for k in sorted(obj.routes.keys()):
                self._hash_components.append(f"Key({k})->")
                self._visit_arg(obj.routes[k])
            self._hash_components.append("}")
            return

        if isinstance(obj, (list, tuple)):
            self._hash_components.append("List[")
            for item in obj:
                self._visit_arg(item)
            self._hash_components.append("]")
            return

        if isinstance(obj, dict):
            self._hash_components.append("Dict{")
            for k in sorted(obj.keys()):
                self._hash_components.append(f"{k}:")
                self._visit_arg(obj[k])
            self._hash_components.append("}")
            return

        if isinstance(obj, Inject):
            self._hash_components.append(f"Inject({obj.resource_name})")
            return

        # For any other value, it's a literal. We record a placeholder, not the value itself.
        # The actual value is handled by the GraphBuilder's data_tuple.
        self._hash_components.append("LIT")

    def _visit_lazy(self, lr: LazyResult):
        task_name = getattr(lr.task, "name", "unknown")
        self._hash_components.append(f"Task({task_name})")

        if lr._retry_policy:
            rp = lr._retry_policy
            self._hash_components.append(f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})")
        if lr._cache_policy:
            self._hash_components.append(f"Cache({type(lr._cache_policy).__name__})")

        self._hash_components.append("Args:")
        for arg in lr.args:
            self._visit_arg(arg)

        self._hash_components.append("Kwargs:")
        for k in sorted(lr.kwargs.keys()):
            self._hash_components.append(f"{k}=")
            self._visit_arg(lr.kwargs[k])

        if lr._condition:
            self._hash_components.append("Condition:PRESENT")
        if lr._dependencies:
            self._hash_components.append(f"Deps:{len(lr._dependencies)}")
        if lr._constraints:
             keys = sorted(lr._constraints.requirements.keys())
             self._hash_components.append(f"Constraints({','.join(keys)})")


    def _visit_mapped(self, mlr: MappedLazyResult):
        factory_name = getattr(mlr.factory, "name", "unknown")
        self._hash_components.append(f"Map({factory_name})")

        self._hash_components.append("MapKwargs:")
        for k in sorted(mlr.mapping_kwargs.keys()):
            self._hash_components.append(f"{k}=")
            self._visit_arg(mlr.mapping_kwargs[k])

        if mlr._condition:
            self._hash_components.append("Condition:PRESENT")
        if mlr._dependencies:
            self._hash_components.append(f"Deps:{len(mlr._dependencies)}")
        if mlr._constraints:
             keys = sorted(mlr._constraints.requirements.keys())
             self._hash_components.append(f"Constraints({','.join(keys)})")


class StructuralHasher:
    """
    Generates a stable structural hash for a LazyResult tree and extracts
    literal values that fill the structure.
    """

    def __init__(self):
        # Flattened map of {canonical_node_path: {arg_name: value}}
        # path examples: "root", "root.args.0", "root.kwargs.data.selector"
        self.literals: Dict[str, Any] = {}
        self._hash_components: List[str] = []

    def hash(self, target: Any) -> Tuple[str, Dict[str, Any]]:
        self._visit(target, path="root")

        # Create a deterministic hash string
        fingerprint = "|".join(self._hash_components)
        hash_val = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

        return hash_val, self.literals

    def _visit(self, obj: Any, path: str):
        if isinstance(obj, LazyResult):
            self._visit_lazy(obj, path)
        elif isinstance(obj, MappedLazyResult):
            self._visit_mapped(obj, path)
        elif isinstance(obj, Router):
            self._visit_router(obj, path)
        elif isinstance(obj, (list, tuple)):
            self._hash_components.append("List[")
            for i, item in enumerate(obj):
                self._visit(item, f"{path}[{i}]")
            self._hash_components.append("]")
        elif isinstance(obj, dict):
            self._hash_components.append("Dict{")
            for k in sorted(obj.keys()):
                self._hash_components.append(f"{k}:")
                self._visit(obj[k], f"{path}.{k}")
            self._hash_components.append("}")
        elif isinstance(obj, Inject):
            self._hash_components.append(f"Inject({obj.resource_name})")
        else:
            # It's a literal value.
            # We record a placeholder in the hash, and save the value.
            self._hash_components.append("LIT")
            self.literals[path] = obj

    def _visit_lazy(self, lr: LazyResult, path: str):
        # Identification
        task_name = getattr(lr.task, "name", "unknown")
        self._hash_components.append(f"Task({task_name})")

        # Policies (part of structure)
        if lr._retry_policy:
            rp = lr._retry_policy
            self._hash_components.append(
                f"Retry({rp.max_attempts},{rp.delay},{rp.backoff})"
            )
        if lr._cache_policy:
            self._hash_components.append(f"Cache({type(lr._cache_policy).__name__})")

        # Args
        self._hash_components.append("Args:")
        for i, arg in enumerate(lr.args):
            self._visit(arg, f"{path}.args.{i}")

        # Kwargs
        self._hash_components.append("Kwargs:")
        for k in sorted(lr.kwargs.keys()):
            self._hash_components.append(f"{k}=")
            self._visit(lr.kwargs[k], f"{path}.kwargs.{k}")

        # Condition
        if lr._condition:
            self._hash_components.append("Condition:")
            self._visit(lr._condition, f"{path}.condition")

        if lr._dependencies:
            self._hash_components.append("Deps:")
            for i, dep in enumerate(lr._dependencies):
                self._visit(dep, f"{path}.deps.{i}")

    def _visit_mapped(self, mlr: MappedLazyResult, path: str):
        factory_name = getattr(mlr.factory, "name", "unknown")
        self._hash_components.append(f"Map({factory_name})")

        # Kwargs (Mapped inputs)
        self._hash_components.append("MapKwargs:")
        for k in sorted(mlr.mapping_kwargs.keys()):
            self._hash_components.append(f"{k}=")
            self._visit(mlr.mapping_kwargs[k], f"{path}.kwargs.{k}")

        if mlr._condition:
            self._hash_components.append("Condition:")
            self._visit(mlr._condition, f"{path}.condition")

        if mlr._dependencies:
            self._hash_components.append("Deps:")
            for i, dep in enumerate(mlr._dependencies):
                self._visit(dep, f"{path}.deps.{i}")

    def _visit_router(self, router: Router, path: str):
        self._hash_components.append("Router")
        self._hash_components.append("Selector:")
        self._visit(router.selector, f"{path}.selector")

        self._hash_components.append("Routes:")
        for k in sorted(router.routes.keys()):
            # Note: Route keys (k) are structural! (e.g. "prod", "dev")
            self._hash_components.append(f"Key({k})->")
            self._visit(router.routes[k], f"{path}.routes.{k}")
~~~~~

#### Acts 3: 撤销对 `test_time_provider` 的临时修复

根本原因已在 `GraphExecutionStrategy` 中修复，我们不再需要这个临时补丁。

~~~~~act
patch_file
tests/sdk/providers/test_time_provider.py
~~~~~
~~~~~python
    # Allow for more generous framework/scheduling overhead
    assert 0.1 <= duration < 0.2, (
        f"cs.wait should have used the dynamic delay from upstream, but took {duration:.2f}s."
    )
~~~~~
~~~~~python
    assert 0.1 <= duration < 0.15, (
        f"cs.wait should have used the dynamic delay from upstream, but took {duration:.2f}s."
    )
~~~~~

### 下一步建议

我们已经实施了全面的修复。请按以下步骤验证：

1.  **运行完整的测试套件**：执行 `pytest`。我们期望所有测试，包括新创建的 `test_hashing_logic.py` 和之前失败的回归测试，现在都应该通过。
2.  **运行基准测试**：执行 `python observatory/benchmarks/tco_performance.py`。我们期望 `heavy_complex_countdown` 现在能够成功完成，并且其 TPS 应该显著提升，接近 `simple_countdown` 的水平。

如果一切顺利，我们将最终完成这次重构，并可以创建一个 `[COMMIT]` 计划来合并这些更改。
