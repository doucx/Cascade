好的，我们已经完成了针对 `ArgumentResolver` 优先级缺陷的修复，并为“快速路径”和“复杂路径”都建立了稳固的回归测试。现在我们将这些变更作为一个完整的逻辑单元提交到版本库中。

## [COMMIT] fix(engine): 确保 TCO 跳转参数优先于静态图依赖

### 用户需求
修复在使用 `cs.Param` 作为递归任务初始值时，`cs.Jump` 传递的更新参数被原始参数值覆盖，导致死循环的问题。

### 评论
这个修复解决了运行时参数解析逻辑中的一个核心优先级冲突。在 TCO（尾调用优化）场景下，明确的运行时干预（Jump 数据）在语义上必须覆盖静态图定义的默认依赖。该修复同时覆盖了 `ArgumentResolver` 的优化路径和通用路径，保证了系统行为的一致性和稳健性。

### 目标
1.  提交对 `packages/cascade-engine/src/cascade/runtime/resolvers.py` 的修复，确保 `input_overrides` 的优先级最高。
2.  提交新增的 `tests/engine/e2e/test_tco_param_override.py` 测试文件，作为该问题的永久性回归测试。

### 基本原理
通过在 `ArgumentResolver` 解析数据边（DATA Edges）之前引入显式的优先级检查，如果参数已由 `input_overrides` 提供，则跳过对该参数对应依赖边的解析。这确保了递归状态能通过 Jump 信号正确传递，不受静态图中 `cs.Param` 或其他上游任务的影响。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #comp/tests #concept/tco #scope/core #ai/instruct #task/domain/core #task/object/argument-resolver #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 提交修复与测试

我们将修复后的代码和新增的测试用例添加到 Git 暂存区并执行提交。

~~~~~act
git_add
packages/cascade-engine/src/cascade/runtime/resolvers.py
tests/engine/e2e/test_tco_param_override.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(engine): ensure TCO overrides take precedence over dependencies

Fixed a critical bug in ArgumentResolver where data provided via 'cs.Jump'
(input_overrides) was being overwritten by static graph dependencies
(e.g., 'cs.Param') during the resolution process.

In recursive TCO workflows, this led to infinite loops because the
decremented state passed to the next iteration was ignored in favor of
re-resolving the original param value from the starting node.

Changes:
1.  Modified 'ArgumentResolver' to check if an argument is already present
    in 'input_overrides' before resolving its corresponding edge in the
    static graph.
2.  Applied the fix to both the 'Fast Path' (simple tasks) and the
    'Complex Path' (tasks with injections or complex structures).
3.  Added a new E2E test suite 'tests/engine/e2e/test_tco_param_override.py'
    that explicitly verifies the fix for both resolution paths.
~~~~~

### 下一步建议
- **性能回归检查**: 虽然此修复引入的 `if` 检查开销极低，但在超大规模 TCO 循环（百万级迭代）中，建议观察一下 CPU 使用率的变化。
- **文档更新**: 可以在开发者文档中明确说明 Jump 数据的覆盖优先级，帮助用户更好地理解 Cascade 的动态调度行为。
