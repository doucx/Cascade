## [WIP] fix(test): Ensure deterministic execution order for recursive pruning test

### 用户需求
修复 `test_pruning_exclusive_branches` 测试失败。

### 错误分析
测试断言 `branch_b_upstream` 应该被剪枝，但实际上它运行了。
原因在于 `NativeSolver` 将无依赖的 `get_route` (Selector) 和 `branch_b_upstream` (Route Root) 调度到了同一个 Stage 0 并行执行。由于 `branch_b_upstream` 在剪枝逻辑触发前（或同时）就已经被提交执行，因此无法被“拦截”。
剪枝是一种“尽力而为”的优化，它只能阻止尚未运行的任务。

### 解决方案
为了确定性地测试递归剪枝逻辑，我们需要构造一个图，使得 Selector 的执行必然早于被剪枝分支的根节点。
通过引入一个 `dummy_start` 任务，并让 `branch_b_upstream` 依赖它，我们可以将 `branch_b_upstream` 推迟到 Stage 1。而 Selector (`get_route`) 仍然在 Stage 0。
这样，当 Stage 0 完成时，Selector 触发剪枝，此时 Stage 1 尚未开始，`branch_b_upstream` 将被成功标记为 Pruned 并跳过。

### 标签
#intent/fix #flow/ready #priority/medium #comp/tests #concept/control-flow #scope/core #ai/instruct #task/domain/testing #task/object/router-test #task/action/fix-flaky-test #task/state/end

---

### Script

#### Acts 1: 修正测试用例

修改 `tests/runtime/test_router_pruning.py`，引入依赖以控制执行顺序。

~~~~~act
patch_file
tests/runtime/test_router_pruning.py
~~~~~
~~~~~python
    @cs.task
    def branch_b():
        return "B" # Should be pruned

    @cs.task
    def branch_b_upstream():
        return "B_UP" # Should also be pruned (recursive)

    # branch_b depends on branch_b_upstream
    b_chain = branch_b(branch_b_upstream())

    router = cs.Router(
        selector=get_route(),
        routes={"a": branch_a(), "b": b_chain}
    )
~~~~~
~~~~~python
    @cs.task
    def branch_b(val):
        return "B" # Should be pruned

    @cs.task
    def dummy_dep():
        return "DEP"

    @cs.task
    def branch_b_upstream(dep):
        return "B_UP" # Should also be pruned (recursive)

    # branch_b depends on branch_b_upstream
    # branch_b_upstream depends on dummy_dep
    # This pushes branch_b_upstream to Stage 1, while get_route (selector) is in Stage 0.
    # This ensures pruning happens BEFORE branch_b_upstream is scheduled.
    b_chain = branch_b(branch_b_upstream(dummy_dep()))

    router = cs.Router(
        selector=get_route(),
        routes={"a": branch_a(), "b": b_chain}
    )
~~~~~
