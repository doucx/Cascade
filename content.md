You are absolutely correct. My previous refactoring was incomplete. I removed the `PortName` class but failed to update the unit test that depended on it, causing the build to break. This is a critical oversight.

I will now generate a plan to fix the broken test file.

## [WIP] fix(compiler): 修复因移除 PortName 导致的测试失败

### 错误分析
测试 `packages/cascade-compiler/tests/unit/backend/test_builder.py` 失败，原因是 `ImportError: cannot import name 'PortName'`。在上一批次的重构中，我删除了 `PortName` 类，但忘记更新此测试文件以移除对它的依赖。该文件仍在使用 `PortName.PULSE` 来验证脉冲连线逻辑。

### 用户需求
修复 `test_builder.py`，使其不再依赖已删除的 `PortName` 类，恢复测试套件的正常运行。

### 评论
这是一个典型的重构疏忽，未能同步更新测试用例。修复此问题是验证上一批次重构是否真正成功的必要步骤，也是维护 TDD 流程完整性的关键。

### 目标
1.  修改 `packages/cascade-compiler/tests/unit/backend/test_builder.py`。
2.  移除对 `PortName` 的导入。
3.  改为导入 `cascade.std.specs.BleacherSpec`。
4.  将所有 `PortName.PULSE` 的引用替换为 `BleacherSpec.pulse.name`。

### 基本原理
测试代码也应遵循与生产代码相同的架构原则。通过在测试中断言 Spec 定义，我们不仅修复了错误，还提高了测试用例的健壮性和可读性，使其与 PIDL 策略保持一致。

### 标签
#intent/fix #flow/ready #priority/critical #comp/compiler #comp/tests #scope/core #task/domain/compiler #task/object/wiring-policy #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修正测试文件的导入
将 `PortName` 的导入替换为 `BleacherSpec`。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder.py
~~~~~
~~~~~python.old
from cascade.reflection import PhysicalIdGenerator
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.ports import PortName
~~~~~
~~~~~python.new
from cascade.reflection import PhysicalIdGenerator
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.std.specs import BleacherSpec
~~~~~

#### Acts 2: 更新测试断言
使用 `BleacherSpec.pulse.name` 替换 `PortName.PULSE`。

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder.py
~~~~~
~~~~~python.old
    # 2. Assert Bleacher port definition
    bleacher_id = "source_node.bleach"
    bleacher_node = graph.nodes[bleacher_id]
    assert PortName.PULSE in bleacher_node.input_ports

    # 3. Assert Connection: D_pulse -> F_bleach
    pulse_channel = next(
        c
        for c in graph.channels
        if c.source_node_id == pulse_id and c.target_node_id == bleacher_id
    )
    assert pulse_channel is not None
    assert pulse_channel.target_port == PortName.PULSE
~~~~~
~~~~~python.new
    # 2. Assert Bleacher port definition
    bleacher_id = "source_node.bleach"
    bleacher_node = graph.nodes[bleacher_id]
    assert BleacherSpec.pulse.name in bleacher_node.input_ports

    # 3. Assert Connection: D_pulse -> F_bleach
    pulse_channel = next(
        c
        for c in graph.channels
        if c.source_node_id == pulse_id and c.target_node_id == bleacher_id
    )
    assert pulse_channel is not None
    assert pulse_channel.target_port == BleacherSpec.pulse.name
~~~~~

### 下一步建议
测试修复后，PIDL 阶段四的所有任务都已完成。我建议运行完整的测试套件 (`pytest packages/`) 以确保没有其他回归问题。确认通过后，我们可以将这个系列的工作标记为 `[COMMIT]` 并进行提交。
