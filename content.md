Excellent point. You've uncovered the next layer of complexity. My previous fix was a sledgehammer when a scalpel was needed. By making the engine *always* raise an error when the target is skipped, I correctly fixed the simple `run_if(False)` case but broke the more nuanced `sequence` case.

The test `test_sequence_aborts_on_skipped_node` fails because it *expects* the workflow to terminate gracefully without an exception when a sequence is aborted. The sequence correctly skips its later steps, and the test just wants to verify this happened by checking the event log. My aggressive fix turns this correct behavior into an unexpected error.

Let's refine the logic with the necessary nuance.

## [WIP] fix: Differentiate between graceful and exceptional workflow termination

### 错误分析

The current failure in `test_sequence_aborts_on_skipped_node` is a direct result of my previous "always raise" fix. The core issue is that not all "skipped target" scenarios are errors.

1.  **Exceptional Skip (Error)**: A user calls `engine.run(some_task.run_if(False))`. The user has explicitly requested the result of `some_task`. The fact that it was skipped means the engine failed to fulfill its primary contract. This **must** raise an exception. The skip reason here is `ConditionFalse`.

2.  **Graceful Skip (Success)**: A user calls `engine.run(cs.sequence([..., skipped_task, final_task]))`. The contract of `sequence` is to abort if a step is skipped. `final_task` (the target) is correctly skipped with reason `UpstreamSkipped_Sequence`. The `sequence` has executed its logic perfectly. The workflow should terminate successfully, returning `None` because the final task didn't produce a value.

My previous patch treated both cases as errors. The correct solution is to empower the engine to distinguish between them. We can do this by inspecting the skip reason of the final target node.

### 用户需求

The `Engine` must be able to distinguish between a graceful termination (like an aborted `sequence`) and an exceptional one (like a direct target being skipped by a condition). It should only raise `DependencyMissingError` in the exceptional case.

### 评论

This refinement is crucial for building intuitive and expressive control flow primitives. Users expect constructs like `sequence` to follow their defined rules without causing the entire run to fail if they terminate early as designed. This change makes the engine's behavior align with user expectations for higher-level patterns.

### 目标

1.  Modify the final result-checking logic in `packages/cascade-engine/src/cascade/runtime/strategies.py`.
2.  The logic will now check the `skip_reason`. If the reason is `UpstreamSkipped_Sequence`, it will return `None`, indicating a successful but result-less run.
3.  For all other skip reasons, it will raise `DependencyMissingError`.
4.  This will satisfy both `test_run_if_false` (which has a `ConditionFalse` reason and should raise) and `test_sequence_aborts_on_skipped_node` (which has an `UpstreamSkipped_Sequence` reason and should not).

### 基本原理

We will revert to a conditional check at the end of `_execute_graph`, but with more precise logic than the original implementation. The key is the insight that the reason `UpstreamSkipped_Sequence` explicitly signals a graceful termination of a control flow primitive. Any other reason for a skip on the final target implies the engine could not produce the value the user asked for, which is an error.

### 标签

#intent/fix #flow/ready #priority/critical #comp/engine #concept/state #scope/core #ai/refine #task/domain/core #task/object/control-flow #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: Implement nuanced skip handling in the execution strategy

This patch modifies my previous fix in `strategies.py`, adding back the conditional logic but with the correct distinction between graceful and exceptional skips.

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies.py
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
~~~~~python
        if not state_backend.has_result(target._uuid):
            if skip_reason := state_backend.get_skip_reason(target._uuid):
                # A skip due to a sequence aborting is a valid, graceful termination.
                # The workflow succeeded but produced no final value.
                if skip_reason == "UpstreamSkipped_Sequence":
                    return None

                # For all other reasons, failing to produce the target result is an error.
                raise DependencyMissingError(
                    task_id=target.task.name or "unknown",
                    arg_name="<Target Output>",
                    dependency_id=f"Target was skipped (Reason: {skip_reason})",
                )

            # If it wasn't skipped but still has no result, it's a generic failure.
            raise KeyError(
                f"Target task '{target.task.name if hasattr(target.task, 'name') else 'unknown'}' did not produce a result."
            )

        return state_backend.get_result(target._uuid)
~~~~~
