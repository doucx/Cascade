好，这是一个简单的调用错误。我忘记在 `wait_idle()` 调用中传递 `reactor` 实例。

我将立即修复它，以便我们能看到真正的测试结果。

## [WIP] fix(test): 修正饿死诊断测试中的调用错误

### 错误分析
`test_broker_starvation.py` 中的 `wait_idle()` 辅助函数需要一个 `reactor` 参数，但在测试用例中被错误地以无参数方式调用，导致 `TypeError`。

### 用户需求
修复 `wait_idle` 函数的调用，使其能正确接收 `reactor` 实例。

### 目标
1.  在 `test_broker_starvation.py` 中，将所有 `await wait_idle()` 调用修改为 `await wait_idle(reactor)`。

### 基本原理
这是一个简单的编码疏忽，修正调用签名即可。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/test-harness #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复 `wait_idle` 调用

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_broker_starvation.py
~~~~~
~~~~~python.old
    # Step 1
    # Allocator should fire (it sees Ledger and Req).
    # Reclaimer sees Ledger and Rel, BUT Ledger is consumed by Allocator first.
    fired = await reactor.step()
    await wait_idle()
    
    assert fired == 1
~~~~~
~~~~~python.new
    # Step 1
    # Allocator should fire (it sees Ledger and Req).
    # Reclaimer sees Ledger and Rel, BUT Ledger is consumed by Allocator first.
    fired = await reactor.step()
    await wait_idle(reactor)
    
    assert fired == 1
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_broker_starvation.py
~~~~~
~~~~~python.old
    # Step 2
    # Allocator fires AGAIN.
    fired = await reactor.step()
    await wait_idle()
    
    assert fired == 1
~~~~~
~~~~~python.new
    # Step 2
    # Allocator fires AGAIN.
    fired = await reactor.step()
    await wait_idle(reactor)
    
    assert fired == 1
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_broker_starvation.py
~~~~~
~~~~~python.old
    # Step 1
    # Reclaimer should fire first.
    fired = await reactor.step()
    await wait_idle()
    
    assert fired >= 1 # Could be 1 (Reclaim) or 2 (Reclaim then Alloc in same step?)
~~~~~
~~~~~python.new
    # Step 1
    # Reclaimer should fire first.
    fired = await reactor.step()
    await wait_idle(reactor)
    
    assert fired >= 1 # Could be 1 (Reclaim) or 2 (Reclaim then Alloc in same step?)
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_broker_starvation.py
~~~~~
~~~~~python.old
    # Step 2
    # Now Allocator should fire and SUCCEED
    fired = await reactor.step()
    await wait_idle()
    
    # Ledger should be 0 again (Granted)
~~~~~
~~~~~python.new
    # Step 2
    # Now Allocator should fire and SUCCEED
    fired = await reactor.step()
    await wait_idle(reactor)
    
    # Ledger should be 0 again (Granted)
~~~~~

### 下一步建议
现在测试文件语法正确，请重新运行测试。这将揭示我们关于资源饿死问题的假设是否成立。
