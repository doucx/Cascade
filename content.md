You are right, I missed that one. It seems my previous patch to `test_preview.py` only added the imports but didn't correct the `Engine` instantiation inside the `_analyze_plan` helper function. Thank you for catching that. I will fix it now.

## [WIP] fix(tests): Correct Engine instantiation in test_preview helper

### 错误分析
The test failures in `tests/tools/test_preview.py` persist because the internal helper function `_analyze_plan`, which is called by both failing tests, still instantiates the `Engine` using the outdated `Engine()` constructor. My previous patch did not modify this helper function, leading to the `TypeError`.

### 用户需求
Fix the `_analyze_plan` function in `tests/tools/test_preview.py` to correctly instantiate the `Engine` with all required dependency injection arguments.

### 评论
This is the final loose end from the `Engine` refactoring. Fixing this helper function will resolve the last of the test failures and fully stabilize our test suite.

### 目标
Patch `tests/tools/test_preview.py` to update the `Engine()` call within `_analyze_plan` to `Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())`.

### 基本原理
I will apply a single, precise `patch_file` operation to the `_analyze_plan` function. This will replace the incorrect `Engine()` call with the correct one, using the `NativeSolver` and `LocalExecutor` that are already imported into the file. The `MessageBus` is also available from imports.

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/test-suite #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: Fix `_analyze_plan` in `preview.py`

I will now apply the final correction.

~~~~~act
patch_file
src/cascade/tools/preview.py
~~~~~
~~~~~python
def _analyze_plan(target: LazyResult[Any], bus: MessageBus) -> None:
    """
    Core logic for dry_run: builds the plan and emits events.
    Decoupled from any output mechanism.
    """
    # We use the default engine configuration to get the default solver
    engine = Engine()

    # 1. Build the graph statically
    graph = build_graph(target)
~~~~~
~~~~~python
def _analyze_plan(target: LazyResult[Any], bus: MessageBus) -> None:
    """
    Core logic for dry_run: builds the plan and emits events.
    Decoupled from any output mechanism.
    """
    # We use the default engine configuration to get the default solver
    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=MessageBus())

    # 1. Build the graph statically
    graph = build_graph(target)
~~~~~

### 下一步建议
This patch should resolve the final two test failures. Once the tests pass, we will have successfully completed the first major step of **Phase 2** (Engine Decoupling). We can then proceed with confidence to the next step: refactoring the `Engine.run` method's core logic.
