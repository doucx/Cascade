测试已全部通过，这标志着**阶段 5.A：基础物理模型强化与通道极化**在逻辑实现和运行时验证上都取得了圆满成功。我们现在拥有了一个在底层支持“双势垒”激活逻辑的纯粹物理引擎。

现在，我将清理 `FuncNode` 中的调试日志，使其回归生产状态。

## [WIP] chore(spec): 清理 FuncNode 中的调试日志

### 用户需求
测试已通过，按照要求移除 `packages/cascade-spec/src/cascade/spec/physics.py` 中用于调试的 `print` 语句。

### 评论
这是一个常规的清理操作，确保代码库的整洁。调试日志已经完成了它的使命，即验证了双势垒逻辑在 `Reactor.step` 内部的正确触发时序。

### 目标
1.  移除 `cascade.spec.physics.FuncNode.is_ready` 方法中的所有 `print` 调用。

### 基本原理
使用 `patch_file` 精确移除调试代码，恢复 `is_ready` 方法的简洁性。

### 标签
#intent/tune #flow/ready #priority/low #comp/engine #scope/core #ai/instruct #task/domain/spec #task/object/reactor-physics #task/action/cleanup #task/state/continue

---

### Script

#### Acts 1: 清理调试日志

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics.py
~~~~~
~~~~~python.old
    def is_ready(self) -> bool:
        """
        Dual-Barrier Potential Check:
        Returns True if and only if ALL connected input ports have an excited source DataNode.
        """
        print(f"\n[is_ready CHECK for {self.name}]")
        if not self.inputs:
            print(" -> No inputs, node is ready.")
            return True  # A node with no inputs is always ready.

        all_ready = True
        for port in self.inputs.values():
            is_excited = port.source and port.source.is_excited()
            print(f" -> Port '{port.name}' ({port.kind.name}) source excited: {is_excited}")
            if not is_excited:
                all_ready = False
        
        print(f" -> Final is_ready result: {all_ready}")
        return all_ready
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
~~~~~

### 下一步建议
我们已经完成了阶段 5.A 的所有代码修改和清理。

下一步，我建议生成一个 **`[COMMIT]` 计划**，将这一系列关于“通道极化与双势垒激活”的重大架构改进正式提交到 Git 历史中。

完成提交后，我们将开启 **阶段 5.B：原生物理执行器与生命周期解耦**。在这个阶段，我们将创建一个独立的 `PhysicsExecutor`，并废除旧的 `TerminatorNode`。
