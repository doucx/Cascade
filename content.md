简要回答
我们将修复 `LocalExecutor` 中对 `node.is_async` 的访问，以及 `Node` 初始化时对 `execution_mode` 的处理。

## [WIP] fix(executors): 修复 LocalExecutor 对 Node 属性的访问

### 用户需求
1.  修复 `LocalExecutor` 访问已移除的 `node.is_async` 属性导致的 `AttributeError`。
2.  修复 `Node.__init__` 中 `execution_mode` 参数传递错误（`GraphBuilder` 仍在使用旧的传参方式）。

### 评论
`LocalExecutor` 依赖任务的异步/同步属性来决定是否将任务调度到线程池。现在这些元数据位于 `node.definition` 中。我们需要更新所有使用了这些属性的地方。

### 目标
1.  修改 `packages/cascade-engine/src/cascade/adapters/executors/local.py`。
2.  修改 `packages/cascade-graph/src/cascade/graph/build.py`。

### 标签
#intent/fix #flow/ready #priority/high #comp/executors #scope/core #ai/instruct #task/domain/runtime #task/object/executor #task/action/repair #task/state/continue

---

### Script

#### Acts 1: 修复 LocalExecutor

将属性访问重定向到 `definition`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/executors/local.py
~~~~~
~~~~~old
        if node.callable_obj is None:
            raise TypeError(
                f"Node '{node.name}' of type '{node.node_type}' is not executable (no callable)."
            )

        if node.is_async:
            result = await node.callable_obj(*args, **kwargs)
        else:
            loop = asyncio.get_running_loop()

            # Select the appropriate executor based on the task's declared mode
            if node.execution_mode == "compute":
                executor = self._compute_executor
            else:  # Default to "blocking" for I/O, etc.
                executor = self._blocking_executor
~~~~~
~~~~~new
        if node.callable_obj is None:
            raise TypeError(
                f"Node '{node.name}' of type '{node.node_type}' is not executable (no callable)."
            )

        if node.definition.is_async:
            result = await node.callable_obj(*args, **kwargs)
        else:
            loop = asyncio.get_running_loop()

            # Select the appropriate executor based on the task's declared mode
            if node.definition.mode == "compute":
                executor = self._compute_executor
            else:  # Default to "blocking" for I/O, etc.
                executor = self._blocking_executor
~~~~~

#### Acts 2: 修复 GraphBuilder

修复 `Node` 构造调用，移除不再存在的 `execution_mode` 参数。该参数现在包含在 `TaskDef` 中。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~old
            node = Node(
                structural_id=node_hash,
                definition=task_def,
                callable_obj=result.task.func,
                node_type="task",
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
                has_complex_inputs=has_complex,
            )
~~~~~
~~~~~new
            # Note: execution_mode is now part of task_def (definition.mode)
            node = Node(
                structural_id=node_hash,
                definition=task_def,
                callable_obj=result.task.func,
                node_type="task",
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
                has_complex_inputs=has_complex,
            )
~~~~~

### 下一步建议
再次运行测试。`GraphBuilder.build` 是图构建的核心入口，`LocalExecutor` 是其实际执行者。修复这两个地方后，大多数集成测试 (`test_engine_*.py`) 应该能够通过那个阻塞点，即使可能有更下游的失败。
