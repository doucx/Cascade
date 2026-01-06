这是并发编程中的经典时序竞态问题。

在 `LocalComputeService._process_request` 中，`self._active_count -= 1`（标记任务完成）与 `self.outbound_queue.put`（提交结果）之间存在一个微小的时间窗口。

如果 `Machine` 的主循环恰好在这个窗口期进行检查，它会观察到：
1.  `ComputeService` 是空闲的（因为计数已减为 0）。
2.  `IngressQueue` 是空的（因为结果还没放进去）。

于是 `Machine` 错误地判断系统已达到全局静止状态（Quiescence），并立即终止运行，导致结果丢失。

修复方案是将 `_active_count -= 1` 的操作推迟到结果成功入队之后执行。

## 标签
#intent/fix #flow/ready #priority/critical #comp/vm #concept/concurrency #scope/core #task/domain/runtime #task/object/compute-service #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 LocalComputeService 的竞态条件

我们将修改 `packages/cascade-vm/src/cascade/vm/compute/service.py`，调整 `finally` 块中的逻辑顺序。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/service.py
~~~~~
~~~~~python.old
        except Exception as e:
            logger.exception(
                f"Computation failed for request on code {request.code_hash}"
            )
            # Per v3.1 spec, exceptions are treated as values
            result = e
        finally:
            self._active_count -= 1

        # 4. Store Result and Prepare Token
        result_ref = self.store.put(result)
        result_token = Token(payload=result_ref, trace=request.trace)

        # 5. Report Completion to Outbound Queue
        await self.outbound_queue.put((request.reply_to_nid, result_token))

    def _resolve_arguments(
~~~~~
~~~~~python.new
        except Exception as e:
            logger.exception(
                f"Computation failed for request on code {request.code_hash}"
            )
            # Per v3.1 spec, exceptions are treated as values
            result = e

        try:
            # 4. Store Result and Prepare Token
            result_ref = self.store.put(result)
            result_token = Token(payload=result_ref, trace=request.trace)

            # 5. Report Completion to Outbound Queue
            await self.outbound_queue.put((request.reply_to_nid, result_token))
        finally:
            # CRITICAL: We must only decrement the active count AFTER the result
            # is visible in the outbound queue. Otherwise, the Machine might
            # see (active=0, queue=empty) in the gap and exit prematurely.
            self._active_count -= 1

    def _resolve_arguments(
~~~~~

### 下一步建议
修复此竞态条件后，`Machine` 应该能正确地等待结果产生。我们将再次运行测试以验证修复效果。

执行 `pytest packages/cascade-runtime/tests/integration/test_vm_strategy.py`。
