You are absolutely right. My apologies. The test failure proves that my previous analysis, while directionally correct in identifying the components involved, was ultimately flawed in its implementation. The logic I proposed was not sufficient to fix the bug.

Thank you for providing the failing test output. It clearly shows the core issue: `engine.run()` is completing without raising an exception, likely returning `None`, which `pytest.raises` correctly flags as a test failure.

Let's re-examine the execution flow with laser focus.

## [WIP] fix: Ensure skipped target node raises DependencyMissingError

### 错误分析

My previous fix was incorrect. I focused on the behavior of *intermediate* nodes in `ArgumentResolver` but missed the final, critical step in `_execute_graph` within `strategies.py`.

The root cause of the bug lies here:

```python
# In cascade/runtime/strategies.py, at the end of _execute_graph

if not state_backend.has_result(target._uuid):
    if skip_reason := state_backend.get_skip_reason(target._uuid):
        # ... some logic ...
        if "Data" in skip_reason or "Route" in skip_reason:
             raise DependencyMissingError(...)
        else:
             # THIS IS THE BUG!
             return None 
```

When `test_run_if_false` runs:
1.  The `condition` task returns `False`.
2.  `FlowManager` correctly determines that the `action` task should be skipped with the reason `"ConditionFalse"`.
3.  The graph execution finishes.
4.  The code checks the final `target` (`action`). It finds that it has no result, but it *does* have a skip reason: `"ConditionFalse"`.
5.  This reason does not contain `"Data"` or `"Route"`, so the logic falls into the `else` block and **incorrectly returns `None`**.

The contract of `engine.run(target)` is to compute the result for `target`. If `target` itself is skipped, it cannot produce a result. This is an exceptional state and **must** result in an exception, not a silent return of `None`.

### 用户需求

Modify the `Engine`'s graph execution strategy to ensure that if the final target of a workflow is skipped for any reason, the `engine.run` call fails by raising a `DependencyMissingError`.

### 评论

This is a critical bug fix that enforces the semantic contract of the `Engine`. A user explicitly asking for a result must be notified if that result cannot be produced. The previous logic created an ambiguous, silent failure mode that is difficult to debug. This change will make the library's behavior more predictable and robust.

### 目标

1.  Locate the incorrect `return None` statement in `packages/cascade-engine/src/cascade/runtime/strategies.py`.
2.  Replace the entire conditional logic block with a simpler, more correct implementation: if the target has no result, it's always an error. The error message should include the skip reason if available.
3.  Ensure `test_run_if_false` passes.

### 基本原理

We will remove the faulty conditional logic at the end of the `_execute_graph` method. The new logic will be straightforward:

1.  Check if the `target` node has a result in the `state_backend`.
2.  If it does not, check if it has a skip reason.
    - If there is a skip reason, raise `DependencyMissingError` and include the reason in the message.
    - If there is no skip reason, raise a `KeyError` indicating a more fundamental execution failure.
3.  If it has a result, return it.

This approach is unambiguous and correctly treats the failure to produce a requested result as an exception.

### 标签

#intent/fix #flow/ready #priority/critical #comp/engine #concept/state #scope/core #ai/refine #task/domain/core #task/object/control-flow #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: Correct the final result handling in the graph execution strategy

This patch directly targets the flawed logic in `strategies.py` and replaces it with the correct, stricter implementation.

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
        if not state_backend.has_result(target._uuid):
            if skip_reason := state_backend.get_skip_reason(target._uuid):
                # Distinguish between a valid control-flow skip and a data dependency failure.
                # A skip due to a data dependency is an error. Other skips are valid terminations.
                if "Data" in skip_reason or "Route" in skip_reason:
                    raise DependencyMissingError(
                        task_id=target.task.name or "unknown",
                        arg_name="<Target Output>",
                        dependency_id=f"Target was skipped (Reason: {skip_reason})",
                    )
                else:
                    # Valid skip (e.g., ConditionFalse, UpstreamSkipped_Sequence).
                    # The workflow finished successfully but produced no final result.
                    return None

            raise KeyError(
                f"Target task '{target.task.name if hasattr(target.task, 'name') else 'unknown'}' did not produce a result."
            )

        return state_backend.get_result(target._uuid)
~~~~~
~~~~~python
        if not state_backend.has_result(target._uuid):
            # If the target node was skipped, it's a specific type of dependency error.
            if skip_reason := state_backend.get_skip_reason(target._uuid):
                raise DependencyMissingError(
                    task_id=target.task.name or "unknown",
                    arg_name="<Target Output>",
                    dependency_id=f"Target was skipped (Reason: {skip_reason})",
                )

            # If it wasn't skipped but still has no result, it's a more generic failure.
            raise KeyError(
                f"Target task '{target.task.name if hasattr(target.task, 'name') else 'unknown'}' did not produce a result."
            )

        return state_backend.get_result(target._uuid)
~~~~~
