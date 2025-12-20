You've hit upon a classic and fundamental concept in declarative, graph-based programming. Your analysis is spot on.

The error `TypeError: cannot unpack non-iterable LazyResult object` occurs because the line `neighbors_data, next_mailbox = collect_neighbors(...)` is executed at **graph-building time**, not at **execution time**.

1.  **Graph-Building Time**: When Python first runs `conway_agent`, it's not executing the logic. It's building a computation graph. The call to `collect_neighbors(...)` doesn't return a tuple of data; it returns a single `LazyResult` object which is a *promise* that a tuple will be available in the future. Trying to unpack this single object into two variables (`neighbors_data`, `next_mailbox`) immediately fails.

2.  **Execution Time**: The `Engine` takes this graph and executes it. Only when the `collect_neighbors` task actually runs will its result (the tuple) be computed.

**The solution is to embrace the dataflow model**: The logic that needs the unpacked tuple must be placed *inside another task* that takes the single `LazyResult` (representing the future tuple) as its input.

I will now generate a plan to fix this by correctly composing the tasks.

## [WIP] fix(agent): Correctly chain dependent tasks in conway_agent

### 错误分析
`conway_agent` 在图构建阶段尝试解包 (unpack) `collect_neighbors` 任务返回的 `LazyResult` 对象。`LazyResult` 是一个单一对象，代表未来的计算结果，而不是一个可迭代的元组，因此导致了 `TypeError`。

这个错误暴露了一个对 Cascade 声明式编程模型的误用：试图在定义计算图时，命令式地处理一个只有在运行时才存在的数据。

### 用户需求
`conway_agent` 的工作流逻辑需要被正确地链接起来。`collect_neighbors` 任务的输出（一个包含邻居状态和新邮箱的元组）必须能够被后续的 `compute_next` 和递归调用正确地消费。

### 评论
这是一个非常好的教学案例，它清晰地展示了“图构建时”和“运行时”的区别。正确的模式是将数据处理逻辑封装在任务中，并通过将 `LazyResult` 作为参数传递来构建依赖关系，而不是在顶层代码中直接操作它们。

### 目标
1.  重构 `conway_agent` 中的 `lifecycle` 函数。
2.  创建一个新的包装任务，该任务接收 `collect_neighbors` 返回的单一 `LazyResult`。
3.  将解包、调用 `compute_next` 和递归调用 `lifecycle` 的逻辑移动到这个新的包装任务内部。

### 基本原理
通过将后续逻辑移入一个新的 `@cs.task`，我们确保了解包操作发生在**运行时**。届时，`Engine` 已经执行了 `collect_neighbors`，其具体的元组结果会作为参数传递给我们的新任务，此时解包操作就可以安全地进行了。这完全符合 Cascade 的数据流和延迟执行模型。

### 标签
#intent/fix #flow/ready #priority/high #comp/observatory #concept/dataflow #scope/core #ai/instruct #task/domain/simulation #task/object/agent-logic #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 conway_agent 的数据流

我们将重构 `lifecycle` 函数，将依赖于 `collect_neighbors` 结果的逻辑封装到一个新的任务中。

~~~~~act
patch_file
observatory/protoplasm/agents/conway.py
~~~~~
~~~~~python
        neighbors_data, next_mailbox = collect_neighbors(
            broadcast, report, gen, mailbox, neighbor_ids, connector
        )

        # 3. Compute next state based on neighbors
        @cs.task
        def compute_next(neighbor_states: Dict[int, int], my_state: int) -> int:
            alive_neighbors = sum(neighbor_states.values())
            
            if my_state == 1:
                if alive_neighbors in (2, 3):
                    return 1
                else:
                    return 0
            else:
                if alive_neighbors == 3:
                    return 1
                else:
                    return 0
        
        next_state = compute_next(neighbors_data[0], current_state)
        
        # 4. Recurse
        @cs.task
        def step_recursion(ns, nmb):
            return lifecycle(gen + 1, ns, nmb)
            
        return step_recursion(next_state, neighbors_data[1])
~~~~~
~~~~~python
        collected_data = collect_neighbors(
            broadcast, report, gen, mailbox, neighbor_ids, connector
        )

        # 3. Chain the computation and recursion into a subsequent task
        # This task will only execute after 'collect_neighbors' is done,
        # and it will receive the actual tuple result.
        @cs.task
        def process_and_compute(collected_tuple: Tuple[Dict[int, int], Dict[int, Dict[int, int]]]):
            # Unpacking happens here, at EXECUTION time, which is correct.
            neighbors_data, next_mailbox = collected_tuple

            # --- Compute next state based on neighbors ---
            @cs.task
            def compute_next(neighbor_states: Dict[int, int], my_state: int) -> int:
                alive_neighbors = sum(neighbor_states.values())
                
                if my_state == 1:
                    if alive_neighbors in (2, 3):
                        return 1
                    else:
                        return 0
                else:
                    if alive_neighbors == 3:
                        return 1
                    else:
                        return 0
            
            next_state = compute_next(neighbors_data, current_state)
            
            # --- Recurse ---
            @cs.task
            def step_recursion(ns):
                return lifecycle(gen + 1, ns, next_mailbox)
                
            return step_recursion(next_state)

        return process_and_compute(collected_data)
~~~~~

### 下一步建议
这个逻辑修复非常精确地解决了 `TypeError` 的根源。现在，整个 `conway_agent` 的数据流应该是正确且符合 Cascade 设计哲学的。

请再次运行实验：
`python -m observatory.protoplasm/truth/run_conway_experiment`

我们现在应该能看到模拟正确启动，并开始打印验证日志。
