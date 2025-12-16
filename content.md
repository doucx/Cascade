这是实现计划的第二部分：**运行时升级**。

我们将首先更新图模型和构建器，使其能够理解并构建“映射节点”。然后，我们将重构执行引擎，使其能够动态地展开并并行执行这些节点。

## [WIP] feat(core): Upgrade runtime to support mapped execution

### 用户需求
1.  修改 `Node` 模型以支持映射节点。
2.  更新 `GraphBuilder` 以解析 `MappedLazyResult`。
3.  重构 `Engine` 以支持资源共享的子图执行，并实现映射节点的动态展开逻辑。

### 评论
这是实现动态工作流的核心步骤。特别是 `Engine` 的重构（分离资源管理与图执行），不仅是为了支持 `.map()`，也为未来支持子工作流 (`cs.subflow`) 等高级功能打下了基础，因为它允许在同一资源上下文中嵌套执行图。

### 目标
1.  更新 `src/cascade/graph/model.py`，添加 `mapping_factory` 字段。
2.  更新 `src/cascade/graph/build.py`，添加对 `MappedLazyResult` 的处理逻辑。
3.  重构 `src/cascade/runtime/engine.py`，实现 `_execute_graph` 内部方法，并在其中添加 `map` 节点的执行逻辑。

### 基本原理
通过将 `Engine.run` 拆分为“资源上下文管理”和“图执行”两个部分，我们优雅地解决了并行子任务需要共享父任务资源（如数据库连接）的问题。这种设计避免了为每个子任务重新创建昂贵资源的开销，也保证了事务的一致性。

### 标签
#intent/build #flow/ready #priority/high #comp/core #comp/runtime #concept/map #scope/core #ai/instruct #task/domain/core #task/object/engine #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新图模型 (`model.py`)

我们需要在 `Node` 类中添加 `mapping_factory` 字段，用于存储生成子任务的工厂对象。

~~~~~act
patch_file
src/cascade/graph/model.py
~~~~~
~~~~~python
    node_type: str = "task" # "task" or "param"
    callable_obj: Optional[Callable] = None
    param_spec: Optional[Param] = None

    # Metadata for execution strategies
    retry_policy: Optional[Any] = None  # Typed as Any to avoid circular deps with spec
~~~~~
~~~~~python
    node_type: str = "task" # "task", "param", or "map"
    callable_obj: Optional[Callable] = None
    param_spec: Optional[Param] = None
    mapping_factory: Optional[Any] = None # Implements LazyFactory

    # Metadata for execution strategies
    retry_policy: Optional[Any] = None  # Typed as Any to avoid circular deps with spec
~~~~~

#### Acts 2: 更新图构建器 (`build.py`)

我们需要教 `GraphBuilder` 如何处理 `MappedLazyResult`。它的处理逻辑与 `LazyResult` 类似，但它创建的是 `map` 类型的节点，并且需要处理 `mapping_kwargs` 中的依赖关系。

~~~~~act
patch_file
src/cascade/graph/build.py
~~~~~
~~~~~python
from typing import Dict, Any
from cascade.graph.model import Graph, Node, Edge
from cascade.spec.task import LazyResult
from cascade.spec.common import Param
from cascade.spec.routing import Router


class GraphBuilder:
    def __init__(self):
        self.graph = Graph()
        self._visited: Dict[str, Node] = {}

    def build(self, target: LazyResult) -> Graph:
        self._visit_lazy_result(target)
        return self.graph

    def _visit(self, value: Any) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value)
        elif isinstance(value, Param):
            return self._visit_param(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")
~~~~~
~~~~~python
from typing import Dict, Any
from cascade.graph.model import Graph, Node, Edge
from cascade.spec.task import LazyResult, MappedLazyResult
from cascade.spec.common import Param
from cascade.spec.routing import Router


class GraphBuilder:
    def __init__(self):
        self.graph = Graph()
        self._visited: Dict[str, Node] = {}

    def build(self, target: LazyResult) -> Graph:
        # Target could be a MappedLazyResult too
        self._visit(target)
        return self.graph

    def _visit(self, value: Any) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        elif isinstance(value, Param):
            return self._visit_param(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")
~~~~~

~~~~~act
patch_file
src/cascade/graph/build.py
~~~~~
~~~~~python
        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(source=source_node, target=node, arg_name="_condition")
            self.graph.add_edge(edge)

        return node

    def _process_dependencies(self, target_node: Node, inputs: Any, is_kwargs: bool):
~~~~~
~~~~~python
        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(source=source_node, target=node, arg_name="_condition")
            self.graph.add_edge(edge)

        return node

    def _visit_mapped_result(self, result: MappedLazyResult) -> Node:
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        node = Node(
            id=result._uuid,
            name=f"map({getattr(result.factory, 'name', 'factory')})",
            node_type="map",
            mapping_factory=result.factory,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        # Process dependencies in mapping_kwargs
        # Note: These arguments are treated as kwargs
        self._process_dependencies(node, result.mapping_kwargs, is_kwargs=True)

        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(source=source_node, target=node, arg_name="_condition")
            self.graph.add_edge(edge)

        return node

    def _process_dependencies(self, target_node: Node, inputs: Any, is_kwargs: bool):
~~~~~

#### Acts 3: 重构引擎与实现 Map 逻辑 (`engine.py`)

这是最关键的一步。我们将：
1.  重构 `Engine.run`，提取 `_execute_graph` 以支持递归调用和资源共享。
2.  在 `_execute_node_with_policies` 中添加对 `map` 节点的处理逻辑：解析输入列表 -> 动态生成子任务 -> 并行执行。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    async def run(
        self, target: LazyResult, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        run_id = str(uuid4())
        start_time = time.time()

        target_task_names = [target.task.name]

        event = RunStarted(
            run_id=run_id, target_tasks=target_task_names, params=params or {}
        )
        self.bus.publish(event)

        # ExitStack manages the teardown of resources
        with ExitStack() as stack:
            try:
                graph = build_graph(target)
                plan = self.solver.resolve(graph)

                # Scan for all required resources
                required_resources = self._scan_for_resources(plan)

                # Setup resources and get active instances
                active_resources = self._setup_resources(
                    required_resources, stack, run_id
                )

                results: Dict[str, Any] = {}
                skipped_node_ids: set[str] = set()

                # Pre-populate results with parameter values
                self._inject_params(plan, params or {}, results)

                for node in plan:
                    # Skip param nodes as they are not "executed"
                    if node.node_type == "param":
                        continue
                        
                    # Check if we should skip this node
                    skip_reason = self._should_skip(node, graph, results, skipped_node_ids)
                    
                    if skip_reason:
                        skipped_node_ids.add(node.id)
                        self.bus.publish(
                            TaskSkipped(
                                run_id=run_id,
                                task_id=node.id,
                                task_name=node.name,
                                reason=skip_reason,
                            )
                        )
                        continue

                    results[node.id] = await self._execute_node_with_policies(
                        node, graph, results, active_resources, run_id
                    )

                run_duration = time.time() - start_time
                final_event = RunFinished(
                    run_id=run_id, status="Succeeded", duration=run_duration
                )
                self.bus.publish(final_event)

                return results[target._uuid]

            except Exception as e:
                run_duration = time.time() - start_time
                final_fail_event = RunFinished(
                    run_id=run_id,
                    status="Failed",
                    duration=run_duration,
                    error=f"{type(e).__name__}: {e}",
                )
                self.bus.publish(final_fail_event)
                raise
~~~~~
~~~~~python
    async def run(
        self, target: Any, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        run_id = str(uuid4())
        start_time = time.time()

        # Handle MappedLazyResult or LazyResult
        target_name = getattr(target, "name", "unknown")
        if hasattr(target, "task"):
            target_name = target.task.name
        
        event = RunStarted(
            run_id=run_id, target_tasks=[target_name], params=params or {}
        )
        self.bus.publish(event)

        # ExitStack manages the teardown of resources
        with ExitStack() as stack:
            try:
                # 1. Build graph to discover resources
                # We need to build the graph once here to find global resources for this run.
                # Note: Sub-graphs generated by .map() might need resources not discovered here if they depend on 
                # parameters that change resources. But typically resources are static.
                # For dynamic resources, we might need a more complex strategy.
                # For now, we assume top-level graph building reveals all needed resources for the initial plan.
                initial_graph = build_graph(target)
                initial_plan = self.solver.resolve(initial_graph)
                
                required_resources = self._scan_for_resources(initial_plan)
                active_resources = self._setup_resources(
                    required_resources, stack, run_id
                )

                # 2. Execute
                final_result = await self._execute_graph(
                    target, params or {}, active_resources, run_id
                )

                run_duration = time.time() - start_time
                final_event = RunFinished(
                    run_id=run_id, status="Succeeded", duration=run_duration
                )
                self.bus.publish(final_event)

                return final_result

            except Exception as e:
                run_duration = time.time() - start_time
                final_fail_event = RunFinished(
                    run_id=run_id,
                    status="Failed",
                    duration=run_duration,
                    error=f"{type(e).__name__}: {e}",
                )
                self.bus.publish(final_fail_event)
                raise

    async def _execute_graph(
        self, 
        target: Any, 
        params: Dict[str, Any], 
        active_resources: Dict[str, Any],
        run_id: str
    ) -> Any:
        """
        Executes a dependency graph for a given target.
        Can be called recursively for sub-graphs (e.g. inside .map()).
        """
        graph = build_graph(target)
        plan = self.solver.resolve(graph)
        
        results: Dict[str, Any] = {}
        skipped_node_ids: set[str] = set()

        self._inject_params(plan, params, results)

        for node in plan:
            if node.node_type == "param":
                continue
                
            skip_reason = self._should_skip(node, graph, results, skipped_node_ids)
            
            if skip_reason:
                skipped_node_ids.add(node.id)
                self.bus.publish(
                    TaskSkipped(
                        run_id=run_id,
                        task_id=node.id,
                        task_name=node.name,
                        reason=skip_reason,
                    )
                )
                continue

            results[node.id] = await self._execute_node_with_policies(
                node, graph, results, active_resources, run_id, params
            )
            
        return results[target._uuid]
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    async def _execute_node_with_policies(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
    ) -> Any:
        task_start_time = time.time()

        # 0. Check Cache
        if node.cache_policy:
            inputs_for_cache = self._resolve_inputs(node, graph, upstream_results)
            cached_value = node.cache_policy.check(node.id, inputs_for_cache)
            if cached_value is not None:
                self.bus.publish(
                    TaskSkipped(
                        run_id=run_id,
                        task_id=node.id,
                        task_name=node.name,
                        reason="CacheHit",
                    )
                )
                return cached_value

        start_event = TaskExecutionStarted(
            run_id=run_id, task_id=node.id, task_name=node.name
        )
        self.bus.publish(start_event)

        # Determine retry policy
        retry_policy = node.retry_policy
        max_attempts = 1 + (retry_policy.max_attempts if retry_policy else 0)
        delay = retry_policy.delay if retry_policy else 0.0
        backoff = retry_policy.backoff if retry_policy else 1.0

        attempt = 0
        last_exception = None

        while attempt < max_attempts:
            attempt += 1
            try:
                result = await self.executor.execute(
                    node, graph, upstream_results, active_resources
                )

                task_duration = time.time() - task_start_time
                finish_event = TaskExecutionFinished(
                    run_id=run_id,
                    task_id=node.id,
                    task_name=node.name,
                    status="Succeeded",
                    duration=task_duration,
                    result_preview=repr(result)[:100],
                )
                self.bus.publish(finish_event)

                # Save to cache if policy exists
                if node.cache_policy:
                    inputs_for_save = self._resolve_inputs(node, graph, upstream_results)
                    node.cache_policy.save(node.id, inputs_for_save, result)

                return result

            except Exception as e:
~~~~~
~~~~~python
    async def _execute_node_with_policies(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
    ) -> Any:
        task_start_time = time.time()

        # 0. Check Cache
        if node.cache_policy:
            inputs_for_cache = self._resolve_inputs(node, graph, upstream_results)
            cached_value = node.cache_policy.check(node.id, inputs_for_cache)
            if cached_value is not None:
                self.bus.publish(
                    TaskSkipped(
                        run_id=run_id,
                        task_id=node.id,
                        task_name=node.name,
                        reason="CacheHit",
                    )
                )
                return cached_value

        start_event = TaskExecutionStarted(
            run_id=run_id, task_id=node.id, task_name=node.name
        )
        self.bus.publish(start_event)

        # Special handling for Map Nodes
        if node.node_type == "map":
            try:
                result = await self._execute_map_node(
                    node, graph, upstream_results, active_resources, run_id, params
                )
                
                task_duration = time.time() - task_start_time
                self.bus.publish(TaskExecutionFinished(
                    run_id=run_id,
                    task_id=node.id,
                    task_name=node.name,
                    status="Succeeded",
                    duration=task_duration,
                    result_preview=f"List[{len(result)} items]",
                ))
                return result
            except Exception as e:
                task_duration = time.time() - task_start_time
                self.bus.publish(TaskExecutionFinished(
                    run_id=run_id,
                    task_id=node.id,
                    task_name=node.name,
                    status="Failed",
                    duration=task_duration,
                    error=str(e),
                ))
                raise e

        # Determine retry policy
        retry_policy = node.retry_policy
        max_attempts = 1 + (retry_policy.max_attempts if retry_policy else 0)
        delay = retry_policy.delay if retry_policy else 0.0
        backoff = retry_policy.backoff if retry_policy else 1.0

        attempt = 0
        last_exception = None

        while attempt < max_attempts:
            attempt += 1
            try:
                result = await self.executor.execute(
                    node, graph, upstream_results, active_resources
                )

                task_duration = time.time() - task_start_time
                finish_event = TaskExecutionFinished(
                    run_id=run_id,
                    task_id=node.id,
                    task_name=node.name,
                    status="Succeeded",
                    duration=task_duration,
                    result_preview=repr(result)[:100],
                )
                self.bus.publish(finish_event)

                # Save to cache if policy exists
                if node.cache_policy:
                    inputs_for_save = self._resolve_inputs(node, graph, upstream_results)
                    node.cache_policy.save(node.id, inputs_for_save, result)

                return result

            except Exception as e:
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    def _teardown_resource(self, gen: Generator, run_id: str, resource_name: str):
        """Helper to exhaust a resource generator for cleanup."""
        try:
            next(gen)
        except StopIteration:
            self.bus.publish(
                ResourceReleased(run_id=run_id, resource_name=resource_name)
            )
~~~~~
~~~~~python
    async def _execute_map_node(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
    ) -> List[Any]:
        """
        Dynamically unfolds and executes a map node.
        """
        # 1. Resolve inputs
        # The node inputs (from edges) correspond to the iterables passed to .map()
        mapped_inputs = self._resolve_inputs(node, graph, upstream_results)
        
        if not mapped_inputs:
            return []
            
        # 2. Validate input lengths
        lengths = {k: len(v) for k, v in mapped_inputs.items()}
        first_len = list(lengths.values())[0]
        if not all(l == first_len for l in lengths.values()):
            raise ValueError(f"Mapped inputs have mismatched lengths: {lengths}")
            
        # 3. Generate sub-tasks
        # We invoke the factory for each item to get a LazyResult (a sub-graph root)
        sub_targets = []
        factory = node.mapping_factory
        
        for i in range(first_len):
            # Extract the i-th item from each iterable input
            kwargs_for_item = {k: v[i] for k, v in mapped_inputs.items()}
            # Invoke factory to get the LazyResult
            sub_target = factory.map(**kwargs_for_item) if hasattr(factory, "map_item") else factory(**kwargs_for_item)
            sub_targets.append(sub_target)
            
        # 4. Execute sub-tasks in parallel
        # We recursively call _execute_graph for each sub-target.
        # This supports sub-targets being complex graphs themselves.
        # We share active_resources with them.
        
        # Note: factory(**kwargs) calls the Task.__call__ which returns a LazyResult.
        # Task class does NOT implement map_item, it implements __call__.
        # So factory(**kwargs_for_item) is correct for Task objects.
        
        coros = [
            self._execute_graph(target, params, active_resources, run_id) 
            for target in sub_targets
        ]
        
        return await asyncio.gather(*coros)

    def _teardown_resource(self, gen: Generator, run_id: str, resource_name: str):
        """Helper to exhaust a resource generator for cleanup."""
        try:
            next(gen)
        except StopIteration:
            self.bus.publish(
                ResourceReleased(run_id=run_id, resource_name=resource_name)
            )
~~~~~

### 下一步建议
我们已经完成了运行时的所有核心改造。现在 `Engine` 具备了处理递归子图和动态映射的能力。接下来的步骤是**编写测试用例**来验证这一切是否按预期工作。我们需要验证基本映射、空列表处理以及与其他功能（如 `router`）的组合使用。
