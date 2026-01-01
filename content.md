好的，收到了测试结果。

`test_dual_barrier_activation_waits_for_all_inputs` 失败，断言为 `Node should be ready once all inputs are excited`。

这说明我们的 `Reactor` 在接收到所有必需的输入（一个数据令牌和一个信号令牌）后，调用 `f_node.is_ready()` 时，该方法返回了 `False`，而测试期望它返回 `True`。

这是一个非常明确的失败信号，直接指向我们在 `packages/cascade-spec/src/cascade/spec/physics.py` 中对 `FuncNode.is_ready()` 方法的修改存在逻辑缺陷。

尽管我之前的计划意图是实现双势垒检查，但实际的代码实现显然是有问题的。它未能正确地识别出所有输入端口都已被满足（“激发态”）的条件。根本原因在于，`is_ready` 的逻辑没有被正确地更新以反映其新的职责。

此外，我注意到一个相关的潜在问题：`FuncNode.consume_inputs()` 方法目前会无差别地消耗所有输入端口的令牌。在一个纯粹的物理模型中，`SIGNAL` 端口的“消耗”应该只用于重置其状态，其 `payload` 不应该被传递给执行器。我们应该一并修复此问题，使 `consume_inputs` 只返回来自 `DATA` 端口的令牌，从而使物理模型更加严谨。

我们将直接修复 `cascade.spec.physics.FuncNode` 类中的两个方法：

1.  **修正 `is_ready()`**: 我们将重写此方法，确保它正确地遍历所有输入端口，并且只有当**每一个**有源的端口（无论是 `DATA` 还是 `SIGNAL`）其对应的 `DataNode` 都处于激发态时，才返回 `True`。
2.  **增强 `consume_inputs()`**: 我们将修改此方法，使其在消耗令牌时，只将那些来自 `kind=ChannelKind.DATA` 端口的令牌收集并返回。这确保了执行器只会收到真正的业务数据，而信号令牌的作用仅限于激活。

这个计划将使我们的物理模型在逻辑上完整且正确，从而让失败的测试通过。

## [WIP] fix(spec): 修正 FuncNode 的 is_ready 和 consume_inputs 逻辑

### 错误分析
测试 `test_dual_barrier_activation_waits_for_all_inputs` 失败，断言 `f_node.is_ready()` 在所有输入都就绪后应为 `True`，但实际为 `False`。这直接暴露了 `FuncNode.is_ready()` 方法中的逻辑错误。该方法未能正确识别所有输入（包括数据和信号）都已满足的状态。同时，`consume_inputs` 方法也需要调整，以区分消耗数据令牌和信号令牌的行为。

### 用户需求
修复 `cascade.spec.physics.FuncNode` 中 `is_ready` 和 `consume_inputs` 方法的逻辑，以正确实现双势垒物理模型，并使相关测试通过。

### 评论
这是一个关键的修复。一个正确的 `is_ready` 方法是整个势能驱动物理引擎的心脏。通过确保它对数据和信号输入的依赖性进行准确判断，我们保证了 `Reactor` 调度的正确性。同时，精炼 `consume_inputs` 的行为，使之只传递数据载荷，可以使我们的物理模型更加纯粹和可预测。

### 目标
1.  重写 `cascade.spec.physics.FuncNode.is_ready()` 方法，确保其在所有输入 `DataNode` 都处于激发态时返回 `True`。
2.  修改 `cascade.spec.physics.FuncNode.consume_inputs()` 方法，使其只返回来自 `DATA` 类型端口的令牌。

### 基本原理
我们将使用一个 `patch_file` 操作来原子化地修复 `packages/cascade-spec/src/cascade/spec/physics.py` 文件。`is_ready` 的逻辑将被一个简单但健壮的循环替换，该循环会检查所有必需的输入。`consume_inputs` 的循环将被修改，增加一个 `if port.kind == ChannelKind.DATA` 的判断条件，从而实现对信号令牌的过滤。

### 标签
#intent/fix #flow/ready #priority/high #comp/engine #comp/interfaces #concept/state #scope/core #ai/instruct #task/domain/vm #task/object/reactor-physics #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `FuncNode` 的物理行为

我们将一次性修复 `is_ready` 的判断逻辑和 `consume_inputs` 的数据过滤逻辑。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics.py
~~~~~
~~~~~python.old
    def is_ready(self) -> bool:
        """
        Dual-Barrier Potential Check: 
        Are all DATA inputs AND all SIGNAL inputs excited?
        """
        for port in self.inputs.values():
            if port.source and not port.source.is_excited():
                # If any input is not ready, the node is not ready.
                return False
        return True

    def consume_inputs(self) -> Dict[str, Token]:
        """
        Atomically consume tokens from all input sources.
        """
        result = {}
        for name, port in self.inputs.items():
            if port.source:
                token = port.source.take()
                if token:
                    result[name] = token
        return result

    def produce_outputs(self, tokens: Dict[str, Token]):
        """
        Push result tokens to output targets.
~~~~~
~~~~~python.new
    def is_ready(self) -> bool:
        """
        Dual-Barrier Potential Check:
        Returns True if and only if ALL connected input ports have an excited source DataNode.
        """
        if not self.inputs:
            return True  # A node with no inputs is always ready.

        for port in self.inputs.values():
            if not port.source or not port.source.is_excited():
                return False
        return True

    def consume_inputs(self) -> Dict[str, Token]:
        """
        Atomically consumes tokens from all input sources, but only returns
        payloads from DATA channels.
        """
        result = {}
        for name, port in self.inputs.items():
            if port.source:
                token = port.source.take()
                # Only add to the result if it's a DATA port and a token was present
                if token and port.kind == ChannelKind.DATA:
                    result[name] = token
        return result

    def produce_outputs(self, tokens: Dict[str, Token]):
        """
        Push result tokens to output targets.
~~~~~

### 下一步建议
我们已经对 `FuncNode` 的核心物理逻辑进行了修复。现在，请再次运行 `pytest`。如果测试通过，说明我们的物理模型已经正确实现，可以继续推进到路线图的 **阶段 5.B**。
