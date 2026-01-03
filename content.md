简要回答

我已识别到 `test_resource_backpressure_event_driven` 超时的原因可能隐藏在复杂的异步交互细节中。由于当前的错误信息仅显示“超时”，缺乏关于系统内部状态（如：是否有任何事件产生？任务是否卡在某个阶段？）的线索，我将采取诊断性修复策略。

我将修改测试文件，在捕获到 `EventTimeoutError` 时，打印所有已捕获的事件列表。这将帮助我们判断是**全链路静默**（任务根本没启动），还是**半途而废**（任务启动了但没结束，或者观测数据没传回来）。这通常是解决此类异步黑盒问题的最快路径。

## [WIP] fix(tests): 增强资源背压测试的调试信息以诊断超时

### 错误分析
测试抛出了 `EventTimeoutError`，表明在 5 秒内未收到预期的任务完成事件。
可能的故障点包括：
1.  **启动失败**: `Bleacher` 未能获取资源，导致任务从未开始。
2.  **观测链路断裂**: 任务执行了，但 `obs_token` 未能通过 `D_life` 传达到 `F_obs`。
3.  **执行崩溃**: Worker 或 Stainer 抛出了异常，且异常处理机制未如预期那样生成错误事件。

通过打印已捕获的事件序列，我们可以二分定位问题：
*   如果列表为空：说明 `Bleacher` 甚至没有发出 `start` 事件 -> 资源分配或输入就绪问题。
*   如果有 `start` 无 `end`：说明 Worker 挂起或 Stainer 失败。
*   如果有 `end` 但 predicate 没匹配：说明事件数据结构不符合预期。

### 用户需求
增强测试的可观测性，以便诊断集成测试中的超时问题。

### 评论
这是解决异步测试不稳定性（Flakiness）的标准操作程序。

### 目标
修改 `test_resource_backpressure.py`，在断言失败时输出诊断信息。

### 基本原理
不改变测试逻辑，仅增强错误报告。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/test-suite #task/action/debug

---

### Script

#### Acts 1: 增强测试的错误报告

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_backpressure.py
~~~~~
~~~~~python.old
        # Wait until both are done (timeout generous because of backoff/recirculation latency)
        await runner.wait_for_event(completion_predicate, timeout=5.0)
        
        assert "node_1" in completed_tasks
        assert "node_2" in completed_tasks

        # 7. Final State Verification
~~~~~
~~~~~python.new
        # Wait until both are done (timeout generous because of backoff/recirculation latency)
        try:
            await runner.wait_for_event(completion_predicate, timeout=5.0)
        except Exception:
            print("\n!!! TIMEOUT DIAGNOSTICS !!!")
            print(f"Captured Events ({len(runner._captured_events)}):")
            for i, evt in enumerate(runner._captured_events):
                print(f"  [{i}] Type: {evt.event_type}, Trace: {evt.trace_data}")
            raise
        
        assert "node_1" in completed_tasks
        assert "node_2" in completed_tasks

        # 7. Final State Verification
~~~~~

### 下一步建议
运行修改后的测试，检查控制台输出。根据捕获到的事件列表（或空列表），我将能够精确定位是物理图的哪一部分发生了阻塞或断裂，并生成相应的修复计划。例如，如果没有任何事件，我将检查 `Bleacher` 的输入是否满足激发条件；如果只有 start 事件，我将检查 Worker 的执行或 Stainer 的连接。
