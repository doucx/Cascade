My deepest apologies. That is a simple but critical typo on my part, introduced during the last major refactoring. The error message is exactly right. I used a variable `phase` that wasn't defined in that scope.

This is not an architectural flaw, but a straightforward implementation bug. I will correct it immediately.

## [WIP] fix(agent): Correct variable name in firefly agent logic

### 错误分析
`NameError: name 'phase' is not defined` occurred in `kuramoto.py` because I incorrectly used the variable `phase` inside the `firefly_agent` function. The function's parameter is named `initial_phase`, and the code should have used that. This was a copy-paste error during the last `write_file` operation when restoring the elegant recursive structure.

### 用户需求
Fix the `NameError` so the simulation can run and we can proceed with the performance analysis.

### 评论
This is a minor but blocking bug. Fixing it will allow us to finally validate whether the new `StructuralHasher` in the `Engine` has solved our core performance problem. The architectural direction remains sound.

### 目标
1.  Correct the variable name from `phase` to `initial_phase` in the `firefly_agent` function's "Refractory Path".

### 基本原理
The code must reference variables that are defined within its scope. The previous `write_file` operation introduced a reference to an undefined variable, which this patch will correct.

### 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #scope/core #ai/instruct
#task/domain/infra
#task/object/agent-logic
#task/action/bug-fix
#task/state/continue

---

### Script

#### Acts 1: Correct the NameError

A targeted patch is sufficient to fix this typo.

~~~~~act
patch_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
    # 1. Refractory Path
    if initial_phase < refractory_period:
        wait_duration = refractory_period - phase
        wait_action = cs.wait(wait_duration)

        @cs.task
~~~~~
~~~~~python
    # 1. Refractory Path
    if initial_phase < refractory_period:
        wait_duration = refractory_period - initial_phase
        wait_action = cs.wait(wait_duration)

        @cs.task
~~~~~

### 下一步建议
The bug is now fixed. Please execute the performance profiling commands one last time. This time, it should run to completion, and we will finally have the data we need to confirm our victory over the performance bottleneck.

Run the profiler:
```bash
python -m cProfile -s tottime -o profile.out observatory/scripts/profile_entry.py
```
And then view the results:
```bash
python -c "import pstats; p = pstats.Stats('profile.out'); p.sort_stats('tottime').print_stats(30)"
```
