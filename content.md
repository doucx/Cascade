修复：**`discrete_allocator` 必须在 `ledger.available == 0` 且有请求时，直接返回（重新循环）`req_token` 和 `ledger_token`，而不进行任何处理。** 这样，`Ledger` 令牌被立即释放，`Reclaimer` 就有机会在下一个 `step` 中获得它。

## [WIP] fix(std): 改进 `discrete_allocator` 以避免资源饥饿下的活锁

### 错误分析
资源竞争测试在高负载下因死锁而超时。详细日志显示，当资源耗尽（`ledger.available == 0`）时，`Allocator` 节点会进入一个高频的“请求风暴”活锁：它不断地消耗并立即归还 `Ledger` 令牌，尝试处理永远无法满足的请求。这使得真正能释放资源的 `Reclaimer` 节点被“饿死”，无法获得 `Ledger` 令牌来更新账本，从而导致整个系统死锁。

### 用户需求
修复 `discrete_allocator` 的活锁问题，确保 `Reclaimer` 在资源耗尽时拥有更高的有效优先级，打破死锁。

### 评论
这是一个经典的并发控制问题。我们的 `Allocator` 表现得像一个“不礼貌”的循环，没有在失败后进行任何形式的退让。通过让它在检测到资源为零时立即归还所有输入令牌，我们模拟了一种“快速失败并让出锁”的策略，给了其他关键节点（`Reclaimer`）执行的机会，从而打破了致命拥抱。

### 目标
-   修改 `packages/cascade-std/src/cascade/std/resource/discrete.py`。
-   在 `discrete_allocator` 中增加一个前置检查：如果 `ledger.available` 为 0，则不进行任何分配尝试，立即将 `req_in` 和 `ledger_in` 令牌重新循环，从而将 `Ledger` 锁的持有时间降至最低。

### 标签
#intent/fix #flow/ready #priority/critical #comp/std #concept/concurrency #scope/core #task/domain/core #task/object/allocator #task/action/deadlock-fix #task.state/continue

---

### Script

#### Acts 1: 修复 `discrete_allocator` 的活锁逻辑

我们将为 `discrete_allocator` 增加一个“快速失败”路径，以避免在资源池为空时无意义地持有 `Ledger` 令牌。

~~~~~act
patch_file
packages/cascade-std/src/cascade/std/resource/discrete.py
~~~~~
~~~~~python.old
async def discrete_allocator(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    # Ideally we should clone or re-instantiate if immutable, but for now we mutate in place for perf
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    req_token = inputs["req_in"]
    req_amount = req_token.payload

    outputs: Dict[str, Token] = {}

    if ledger.available >= req_amount:
        # Grant
        ledger.available -= req_amount

        # Sovereignty Routing: Determine output port based on requestor_id in trace
        requestor_id = req_token.trace.get("requestor_id")
        if requestor_id:
            # The Builder constructs the port name as f"gnt_for_{requestor_id}"
            out_port = f"gnt_for_{requestor_id}"
            outputs[out_port] = Token(payload=req_amount, trace=req_token.trace)
        else:
            # Fallback for legacy/testing (should generally not happen in valid graph)
            outputs["gnt_out"] = Token(payload=req_amount, trace=req_token.trace)
    else:
        # Reject & Recirculate
        outputs["req_out"] = req_token

    outputs["ledger_out"] = Token(payload=ledger)
    return outputs
~~~~~
~~~~~python.new
async def discrete_allocator(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    # Ideally we should clone or re-instantiate if immutable, but for now we mutate in place for perf
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    req_token = inputs["req_in"]
    
    # --- Deadlock Prevention ---
    # If there are no resources available AT ALL, immediately fail and recirculate both
    # the request and the ledger. This minimizes the time the Ledger token is held,
    # giving the Reclaimer a chance to run and break the deadlock.
    if ledger.available == 0:
        return {
            "req_out": req_token,
            "ledger_out": ledger_token,
        }

    req_amount = req_token.payload
    outputs: Dict[str, Token] = {}

    if ledger.available >= req_amount:
        # Grant
        ledger.available -= req_amount
        
        # Sovereignty Routing: Determine output port based on requestor_id in trace
        requestor_id = req_token.trace.get("requestor_id")
        if requestor_id:
            # The Builder constructs the port name as f"gnt_for_{requestor_id}"
            out_port = f"gnt_for_{requestor_id}"
            outputs[out_port] = Token(payload=req_amount, trace=req_token.trace)
        else:
            # Fallback for legacy/testing (should generally not happen in valid graph)
            outputs["gnt_out"] = Token(payload=req_amount, trace=req_token.trace)
    else:
        # Reject & Recirculate
        outputs["req_out"] = req_token

    outputs["ledger_out"] = Token(payload=ledger)
    return outputs
~~~~~

### 下一步建议
这是对核心调度逻辑的一次关键修复。请重新运行 `test_resource_contention.py`（可以使用 `TASK_COUNT=20` 的版本，也可以大胆地调回 50）。

如果这次测试通过，我们将一举解决 Phase 1 遗留下的最棘手的架构安全问题，并可以非常自信地宣布 Phase 1 和 3 的核心工作已全部完成且经过了压力验证。
