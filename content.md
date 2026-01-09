## [WIP] fix(compiler): 在 ExpansionPolicy 中恢复资源存在性验证

### 用户需求

修复 `test_builder_raises_on_missing_resource` 测试失败的问题。在处理任务的资源约束时，编译器必须首先验证所请求的资源是否在环境中被定义，如果未定义，则应抛出一个明确的 `ValueError`。

### 评论

这是一个典型的重构回归问题，也是 TDD 流程价值的体现。提供清晰、有上下文的错误信息是良好开发者体验（DX）的关键。直接抛出 `KeyError` 会让用户感到困惑，而一个明确指出“哪个节点需要哪个未定义的资源”的 `ValueError` 则能让他们快速定位问题。

### 目标

1.  修改 `packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/resource.py` 文件。
2.  在 `ResourceExpansionPolicy.expand` 方法中，遍历约束之前，添加一个检查，确保 `res_name` 存在于 `env_resources` 中。
3.  如果检查失败，则抛出与测试用例期望相匹配的 `ValueError`。

### 基本原理

验证逻辑应当尽可能地靠近使用逻辑，并尽早执行。在我们的新架构中，`Expansion` 阶段是第一个处理资源约束的地方，因此，这里是进行资源存在性验证的最合适位置。通过在此处添加验证，我们确保了在进入更复杂的 `Prism` 逻辑之前，所有的输入都是有效和完整的。

### 标签

#intent/fix #flow/ready #priority/high #task/domain/compiler #task/object/validation #task/action/bug-fix #task/state/continue #scope/core #scope/dx #ai/instruct

---

### Script

#### Acts 1: 为 `ResourceExpansionPolicy` 添加验证逻辑

我们将使用 `patch_file` 为 `ResourceExpansionPolicy` 的 `expand` 方法添加缺失的验证块。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/expansion/policies/resource.py
~~~~~
~~~~~python.old
    def expand(
        self, ctx: ExpansionContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None:
        env_resources = {r.name: r for r in ctx.environment.resources}

        for res_name, amount in node_ir.constraints.items():
            res_def = env_resources[res_name]
            prism = self._get_prism(res_def.type)
            prism.expand_task(ctx, node_ir, subgraph, res_name, amount)
~~~~~
~~~~~python.new
    def expand(
        self, ctx: ExpansionContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None:
        env_resources = {r.name: r for r in ctx.environment.resources}

        # First, validate that all required resources are defined in the environment.
        for res_name in node_ir.constraints:
            if res_name not in env_resources:
                raise ValueError(
                    f"Resource '{res_name}' required by node '{node_ir.current_node_instance_hash}' is not defined"
                )

        for res_name, amount in node_ir.constraints.items():
            res_def = env_resources[res_name]
            prism = self._get_prism(res_def.type)
            prism.expand_task(ctx, node_ir, subgraph, res_name, amount)
~~~~~

### 下一步建议

随着这个修复，我们已经完成了所有策略的迁移工作，并且修复了迁移过程中引入的回归问题。编译器后端现在应该能通过所有测试，并稳定地运行在新的两阶段模型之上。

现在，我们可以放心地进入路线图的**阶段四：协议锁定与验收**。我们将从 `4.1 实施 WiringHarness 读写分离` 开始，通过代码手段来固化我们的新架构，防止未来的修改无意中再次引入职责混淆的问题。

如果你同意，我将开始制定强化 `WiringHarness` 的计划。
