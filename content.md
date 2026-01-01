我们将修正 `packages/cascade-vm/tests/reactor/test_result_emission.py`，为 `EmitterNode` 提供一个符合公理规范的哈希值。

## [WIP] fix: 修正 EmitterNode 测试用例中的构造函数调用

### 用户需求
修复 `test_reactor_emits_result_to_sink` 中的 `TypeError`，确保 `EmitterNode` 实例化时包含必需的 `canonical_code_structure_hash` 参数。

### 评论
随着架构演进到“全对称物理模型”，系统中的每一个动作（即使是内置的发射动作）都应该拥有其规范的身份哈希。这确保了可观测性系统在记录发射动作时，能像记录普通任务一样提供稳定的 ID。

### 目标
1.  更新 `test_result_emission.py` 中的 `EmitterNode` 初始化代码。
2.  使用符合 `canonical_*_hash` 规范的占位符字符串。

### 基本原理
直接修复参数缺失。这是一个纯粹的代码对齐任务，不涉及逻辑变更。

### 标签
#intent/fix #flow/ready #priority/high #comp/vm #comp/tests #concept/physics #scope/dx #ai/instruct #task/domain/testing #task/object/emitter-node #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 修正 `EmitterNode` 的初始化

~~~~~act
patch_file
packages/cascade-vm/tests/reactor/test_result_emission.py
~~~~~
~~~~~python.old
    # 1. Setup simplified topology: D_in -> Emitter
    d_in = DataNode(name="result_slot")
    emitter = EmitterNode(name="emit", sink_id="main_output")
    emitter.add_input(Port(name="data", source=d_in))
~~~~~
~~~~~python.new
    # 1. Setup simplified topology: D_in -> Emitter
    d_in = DataNode(name="result_slot")
    emitter = EmitterNode(
        name="emit",
        canonical_code_structure_hash="canonical_system_emitter_hash",
        sink_id="main_output",
    )
    emitter.add_input(Port(name="data", source=d_in))
~~~~~

### 下一步建议
修复此测试后，建议运行 `pytest packages/cascade-vm/tests/reactor/` 以确保物理引擎（Reactor）的所有核心能力（包括路由、资源感知和生命周期信号）在新的统一模型下依然保持稳健。
