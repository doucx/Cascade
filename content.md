## [WIP] fix(runtime): Correct recursive call to `_execute_graph` in map node

### 用户需求
Fix the widespread test failures caused by the incorrect method signature call within `_execute_map_node`.

### 评论
This is a critical regression fix. By correcting the internal API call, we will restore the integrity of the test suite and ensure that the map functionality correctly interoperates with the TCO optimizations.

### 目标
1.  Modify `_execute_map_node` in `packages/cascade-runtime/src/cascade/runtime/engine.py`.
2.  Inside the method, for each sub-task, explicitly build its graph using `build_graph()` before calling `_execute_graph`, thus satisfying the new method signature.

### 基本原理
The contract of `_execute_graph` has changed to require a pre-built `Graph` object. All call sites must adhere to this new contract. The fix involves making `_execute_map_node` responsible for building the graphs for its sub-tasks before execution.

### 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #concept/tco #scope/api
#task/domain/infra
#task/object/engine-concurrency
#task/action/fix
#task/state/continue

---

### Script

#### Acts 1: Fix the `_execute_map_node` Call Site

We will patch `engine.py` to update the recursive call, ensuring it aligns with the new signature of `_execute_graph`.

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        # Each sub-task is a full workflow run from the engine's perspective
        # but shares the parent's state backend to see results.
        coros = [
            self._execute_graph(
                target, params, active_resources, run_id, parent_state_backend
            )
            for target in sub_targets
        ]
        return await asyncio.gather(*coros)
~~~~~
~~~~~python
        # Each sub-task needs its own graph built before execution.
        # They share the parent's state backend to see results of upstream tasks.
        coros = []
        for target in sub_targets:
            # For each sub-target, build its graph and call _execute_graph with the correct signature.
            sub_graph = build_graph(target)
            coros.append(
                self._execute_graph(
                    sub_graph,
                    target,
                    params,
                    active_resources,
                    run_id,
                    parent_state_backend,
                )
            )
        return await asyncio.gather(*coros)
~~~~~

### 下一步建议
The immediate priority is to verify this fix. Please run the test suite again. We expect the vast majority, if not all, of the `AttributeError` failures to be resolved. Once the tests are passing, we can finally return to the performance profiling task to confirm that the TCO optimizations are now effective.
