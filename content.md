简要回答：
这是一个经典的递归闭包签名不匹配错误。我们在重构 `firefly_agent` 时，给内部的递归函数 `firefly_cycle` 增加了一个参数 `agent_type`，但在 `firefly_cycle` 内部的一些**回调（Callback）**或**分支路径（Branch）**中，调用自身的代码没有更新以包含这个新参数。

具体来说，在处理不应期（Refractory Period）的 `after_refractory` 回调中，我们漏传了 `agent_type`。

## [WIP] fix(agent): 修复递归闭包中的签名不匹配问题

### 错误分析
Traceback 明确指出了错误位置：`kuramoto.py` 中的 `after_refractory` 函数在调用 `firefly_cycle` 时缺少了 `agent_type` 参数。
此外，我们也需要检查 `loop_reset` 回调，确保它也正确传递了该参数。

### 用户需求
修复 `TypeError`，确保 Agent 在所有状态分支（正常闪烁、不应期等待）下都能正确递归。

### 评论
这种错误在手动维护递归状态机时很常见。

### 目标
1.  修改 `observatory/agents/kuramoto.py`。
2.  定位到 `after_refractory` 和 `loop_reset` 函数。
3.  将缺失的 `agent_type` 参数补上。

### 基本原理
闭包需要捕获并传递所有状态变量以维持递归。

### 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #scope/core #ai/instruct
#task/domain/agent-logic
#task/object/firefly-agent
#task/action/bug-fix
#task/state/continue

---

### Script

#### Acts 1: 修复递归调用签名

~~~~~act
read_file
observatory/agents/kuramoto.py
~~~~~

~~~~~act
patch_file
observatory/agents/kuramoto.py
~~~~~
~~~~~python
            @cs.task
            def after_refractory(_):
                # We have advanced time by 'blind_wait_duration'.
                # Our phase is now exactly 'refractory_period'.
                return firefly_cycle(
                    agent_id,
                    refractory_period,
                    period,
                    nudge,
                    neighbors,
                    my_channel,
                    connector,
                    refractory_period,
                )

            return after_refractory(wait_action)
~~~~~
~~~~~python
            @cs.task
            def after_refractory(_):
                # We have advanced time by 'blind_wait_duration'.
                # Our phase is now exactly 'refractory_period'.
                return firefly_cycle(
                    agent_id,
                    refractory_period,
                    period,
                    nudge,
                    neighbors,
                    my_channel,
                    connector,
                    refractory_period,
                    agent_type,
                )

            return after_refractory(wait_action)
~~~~~

### 下一步建议
再次运行 `python -m observatory.experiments.run_fireflies`。这次应该能稳定运行了。我们将密切关注控制台输出，看是否存在 R 值（同步率）的周期性波动，那将是 BZ 反应成功的标志。
