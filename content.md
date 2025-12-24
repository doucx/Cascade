好的，现在核心逻辑已在两个代码路径中都得到修复和验证，我们应当为这个修复创建一个完整的测试覆盖，以防止未来发生回归。

我将为您生成一个计划，在现有的测试文件中增加一个专门针对“复杂路径”的测试用例。

## [WIP] test(engine): 为 TCO 参数覆盖添加复杂路径测试用例

### 用户需求
在 `tests/engine/e2e/test_tco_param_override.py` 文件中增加一个新的测试用例，该用例通过引入 `cs.inject` 来强制 `ArgumentResolver` 走“复杂路径”，从而验证我们的修复在两种实现路径下都有效。

### 评论
这是一个优秀的测试实践。通过为代码的两个主要分支（Fast Path 和 Complex Path）分别创建专门的测试用例，我们极大地增强了测试套件的健壮性，并确保了 `ArgumentResolver` 的行为在未来重构中保持一致。

### 目标
1.  在 `test_tco_param_override.py` 中添加一个新的测试函数 `test_jump_overrides_param_complex_path`。
2.  该函数将定义一个带有 `cs.inject` 依赖的递归任务，以触发 `ArgumentResolver` 的复杂解析逻辑。
3.  验证在该路径下，`cs.Jump` 的参数覆盖依然能够正确工作。

### 基本原理
`GraphBuilder` 在构建图时，如果检测到任务的默认参数中包含 `cs.inject`，会将节点的 `has_complex_inputs` 标志位设为 `True`。`ArgumentResolver` 会根据这个标志位选择不同的代码路径。通过创建一个注入了虚拟资源的测试任务，我们可以确保覆盖到我们之前修复的第二个代码分支，从而完成对整个功能的验证。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/core #task/object/argument-resolver #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 增加复杂路径测试用例

我们将通过 `patch_file` 在 `test_tco_param_override.py` 的末尾追加新的测试函数。

~~~~~act
patch_file
tests/engine/e2e/test_tco_param_override.py
~~~~~
~~~~~python
    # Expect: [3, 2, 1, 0]
    # If bug: [3, 3, 3, ...] -> "InfiniteLoopDetected"
    assert results == [3, 2, 1, 0]
    assert final_res == "Done"
~~~~~
~~~~~python
    # Expect: [3, 2, 1, 0]
    # If bug: [3, 3, 3, ...] -> "InfiniteLoopDetected"
    assert results == [3, 2, 1, 0]
    assert final_res == "Done"


@pytest.mark.asyncio
async def test_jump_overrides_param_complex_path():
    """
    Same as the above test, but forces the ArgumentResolver's "complex path"
    by including a resource injection, ensuring the fix works in both code paths.
    """
    results = []

    # Define a dummy resource to trigger the complex path
    @cs.resource
    def dummy_resource():
        yield "dummy_value"

    @cs.task
    def recursive_task_with_injection(n, injected=cs.inject("dummy_resource")):
        # Ensure resource was injected correctly
        assert injected == "dummy_value"

        if len(results) > 10:
            return "InfiniteLoopDetected"
            
        results.append(n)
        if n <= 0:
            return "Done"
        
        return cs.Jump(target_key="continue", data=n - 1)

    t = recursive_task_with_injection(cs.Param("n", 3, int))
    cs.bind(t, cs.select_jump({"continue": t}))

    bus = MessageBus()
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=bus
    )
    # Register the resource required by the task
    engine.register(dummy_resource)
    
    final_res = await engine.run(t, params={"n": 3})

    assert results == [3, 2, 1, 0]
    assert final_res == "Done"
~~~~~

### 下一步建议
我们已经完成了对 `ArgumentResolver` 错误的修复，并为简单和复杂两种路径都添加了回归测试。现在是时候将这些修改作为一个完整的逻辑单元提交了。

我将生成一个 `[COMMIT]` 计划来提交这些变更。
