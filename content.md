好的，我们继续。

现在我们需要将 `ConstraintManager` 真正地集成到 `Engine` 中，并改造调度循环以使其能够感知并响应约束。这是一个核心的架构升级，它将使 `Engine` 从一个简单的分阶段执行器，演变为一个能够在运行时动态调整任务提交流程的智能调度器。

我将生成一个计划来执行这个关键的集成步骤。

## [WIP] feat: 集成 ConstraintManager 到 Engine 调度循环

### 用户需求
将 `ConstraintManager` 集成到 `Engine` 中，并修改调度循环以支持基于约束的执行控制。

### 评论
这是第三阶段的核心所在。通过这次重构，`Engine` 的调度逻辑将发生质的改变。简单的、确定性的分阶段执行将被一个更动态的、能在每个阶段内部处理“等待”和“重试”的微循环所取代。这为实现全局暂停、速率限制等高级控制功能铺平了道路，是 Cascade 迈向自适应系统的重要一步。

### 目标
1.  在 `Engine` 的 `__init__` 方法中实例化一个新的 `ConstraintManager` 成员。
2.  重构 `Engine` 的 `_execute_graph` 方法的核心调度循环。
3.  新的循环必须在提交任务执行前，调用 `self.constraint_manager.check_permission(node)`。
4.  如果 `check_permission` 返回 `False`，该任务的执行将被推迟，调度器会进入一个短暂的等待周期，然后重新评估。这必须在不阻塞同阶段其他可执行任务的前提下完成。

### 基本原理
原有的 `for stage in plan:` 循环模型过于刚性，无法处理单个任务的动态挂起。如果一个任务因约束被阻塞，整个 `asyncio.gather` 调用也会被阻塞，从而暂停了整个阶段的执行。

为了解决这个问题，我们将引入一个嵌套的 `while` 循环。外层循环依旧按阶段推进，但内层循环负责在一个阶段内不断地尝试执行待处理的任务。它会将通过约束检查的任务提交执行，并将被阻塞的任务放回待处理队列，然后短暂休眠以避免忙等待。这种模式确保了资源和约束的利用率最大化，是实现动态调度的关键。

### 标签
#intent/refine #flow/ready #priority/high
#comp/runtime #concept/constraints #concept/scheduler #scope/core
#ai/instruct
#task/domain/runtime #task/object/constraint-system #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 在 Engine 中引入 ConstraintManager

我们将修改 `engine.py` 文件，导入 `ConstraintManager` 并在 `Engine` 的构造函数中实例化它。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.runtime.resolvers import ArgumentResolver, ConstraintResolver
from cascade.runtime.flow import FlowManager
from cascade.adapters.state import InMemoryStateBackend


class Engine:
    """
    Orchestrates the entire workflow execution.
    """

    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: MessageBus,
        state_backend_cls: Type[StateBackend] = InMemoryStateBackend,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        self.state_backend_cls = state_backend_cls
        self.resource_manager = ResourceManager(capacity=system_resources)
        self._resource_providers: Dict[str, Callable] = {}

        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()
        self.flow_manager: Optional[FlowManager] = None
~~~~~
~~~~~python
from cascade.runtime.resolvers import ArgumentResolver, ConstraintResolver
from cascade.runtime.flow import FlowManager
from cascade.runtime.constraints import ConstraintManager
from cascade.adapters.state import InMemoryStateBackend


class Engine:
    """
    Orchestrates the entire workflow execution.
    """

    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: MessageBus,
        state_backend_cls: Type[StateBackend] = InMemoryStateBackend,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        self.state_backend_cls = state_backend_cls
        self.resource_manager = ResourceManager(capacity=system_resources)
        self.constraint_manager = ConstraintManager()
        self._resource_providers: Dict[str, Callable] = {}

        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()
        self.flow_manager: Optional[FlowManager] = None
~~~~~

#### Acts 2: 重构调度循环以支持约束检查

现在，我们将用新的动态微循环逻辑替换 `_execute_graph` 方法中原有的简单阶段迭代。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        plan = self.solver.resolve(graph)

        for stage in plan:
            tasks_to_run = []
            nodes_in_execution = []

            for node in stage:
                if node.node_type == "param":
                    continue

                skip_reason = self.flow_manager.should_skip(node, state_backend)
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

                tasks_to_run.append(
                    self._execute_node_with_policies(
                        node, graph, state_backend, active_resources, run_id, params
                    )
                )
                nodes_in_execution.append(node)

            if not tasks_to_run:
                continue

            stage_results = await asyncio.gather(*tasks_to_run)

            for node, res in zip(nodes_in_execution, stage_results):
                state_backend.put_result(node.id, res)
                if self.flow_manager:
                    self.flow_manager.register_result(node.id, res, state_backend)
~~~~~
~~~~~python
        plan = self.solver.resolve(graph)

        for stage in plan:
            pending_nodes_in_stage = list(stage)

            while pending_nodes_in_stage:
                executable_this_pass: List[Node] = []
                deferred_this_pass: List[Node] = []

                for node in pending_nodes_in_stage:
                    if node.node_type == "param":
                        continue  # Skip params, they don't execute

                    skip_reason = self.flow_manager.should_skip(node, state_backend)
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
                        # Node is resolved (skipped), so not pending for next pass
                        continue

                    if self.constraint_manager.check_permission(node):
                        executable_this_pass.append(node)
                    else:
                        deferred_this_pass.append(node)

                if executable_this_pass:
                    tasks_to_run = [
                        self._execute_node_with_policies(
                            node, graph, state_backend, active_resources, run_id, params
                        )
                        for node in executable_this_pass
                    ]

                    pass_results = await asyncio.gather(*tasks_to_run)

                    for node, res in zip(executable_this_pass, pass_results):
                        state_backend.put_result(node.id, res)
                        if self.flow_manager:
                            self.flow_manager.register_result(node.id, res, state_backend)

                pending_nodes_in_stage = deferred_this_pass

                if pending_nodes_in_stage and not executable_this_pass:
                    # All remaining nodes are blocked by constraints, wait before retrying.
                    await asyncio.sleep(0.1)  # TODO: Make backoff configurable
~~~~~

### 下一步建议
我们已经成功地将约束检查的逻辑结构集成到了 `Engine` 中。现在，为了让这个系统真正地“活”起来，我们需要实现外部世界与 `ConstraintManager` 之间的通信。

根据路线图，下一步是：
1.  **实现约束同步**: 利用 `Connector` 的订阅功能，让 `Engine` 能够接收来自外部（如 MQTT）的约束更新指令。
2.  **更新管理器**: 当收到指令时，回调函数将解析消息并调用 `constraint_manager.update_constraint` 来更新本地的约束状态。

这将使我们能够从外部动态地控制正在运行的工作流。如果你同意，我将开始制定实现这一功能的计划。
