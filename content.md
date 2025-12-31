好的，既然我们已经明确了架构硬化的路线图，现在立刻开始执行**阶段 1：定义富语义契约 (Spec & Data)**。

根据“焦土政策”和 TDD 流程，我们将通过编写测试用例来强制定义 `cascade-spec` 中所需的新的数据结构和协议。即使部分代码结构可能已存在，我们也将通过这些严格的测试来锁定其行为契约。

以下是阶段 1 的测试编写计划。

## [WIP] test: 定义富语义契约 (Spec & Data) 的 TDD 测试用例

### 用户需求
编写“架构硬化”阶段 1 的所有测试文件，以定义 `Blueprint` 指令集中的策略元数据 (`policy`) 和多态操作数 (`ResourceOperand`, `ContextOperand`)。

### 评论
这是 TDD 的第一步 (RED)。我们将创建针对 `cascade-spec` 包的单元测试。这些测试将定义 `Call` 和 `MapCall` 指令如何携带重试和资源策略，以及指令参数如何支持除字面量和寄存器之外的引用类型（如依赖注入和上下文参数）。

### 目标
1.  创建 `packages/cascade-spec/tests/blueprint/test_instruction_policy.py`：验证指令携带 `ExecutionPolicy`。
2.  创建 `packages/cascade-spec/tests/blueprint/test_rich_operands.py`：验证多态操作数的结构和兼容性。

### 基本原理
通过在 Spec 层定义清晰的数据契约，我们确保编译器后端生成的指令集包含足够的信息供 VM 运行时执行高级调度（如重试、资源申请），从而解决“大过滤器效应”。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #comp/interfaces #scope/core #ai/instruct #task/domain/spec #task/object/ir #task/action/define #task/state/begin

---

### Script

#### Acts 1: 编写指令策略测试 (Policy Specs)

我们将定义 `test_instruction_policy.py`，它强制要求 `Call` 和 `MapCall` 指令拥有一个结构化的 `policy` 字段。

~~~~~act
write_file
packages/cascade-spec/tests/blueprint/test_instruction_policy.py
~~~~~
~~~~~python
import pytest
from dataclasses import is_dataclass
from cascade.spec.blueprint import Call, MapCall, Register, ExecutionPolicy, RetryPolicySpec

def test_execution_policy_structure():
    """
    验证 ExecutionPolicy 及其子组件的结构定义。
    Policy 对象负责携带运行时所需的非功能性约束（如重试、资源）。
    """
    try:
        # 验证 RetryPolicySpec 的存在和字段
        retry = RetryPolicySpec(max_attempts=3, delay=1.0, backoff=2.0)
        assert retry.max_attempts == 3
        assert retry.delay == 1.0
        
        # 验证 ExecutionPolicy 的聚合能力
        policy = ExecutionPolicy(
            retry=retry,
            resources={"gpu": 1, "memory": "2Gi"},
            timeouts={"execution": 60.0}
        )
    except NameError:
        pytest.fail("Critical Strategy classes (RetryPolicySpec, ExecutionPolicy) are missing in cascade.spec.blueprint")
    except TypeError as e:
        pytest.fail(f"Strategy classes have incorrect signature: {e}")

    assert policy.retry == retry
    assert policy.resources["gpu"] == 1
    assert policy.timeouts["execution"] == 60.0

def test_call_instruction_has_policy_field():
    """
    验证 Call 指令包含 'policy' 字段，用于传递单任务策略。
    """
    policy = ExecutionPolicy(resources={"cpu": 1})
    
    try:
        instr = Call(
            output=Register(0),
            task_name="t",
            structure_hash="h",
            policy=policy
        )
    except TypeError:
        pytest.fail("Call instruction does not accept 'policy' argument")
    
    assert instr.policy == policy
    assert instr.policy.resources["cpu"] == 1

def test_map_call_instruction_has_policy_field():
    """
    验证 MapCall 指令包含 'policy' 字段。
    Map 操作的策略通常应用于生成的每一个子任务。
    """
    policy = ExecutionPolicy(retry=RetryPolicySpec(max_attempts=5))
    
    try:
        instr = MapCall(
            output=Register(0),
            task_name="map_t",
            structure_hash="h",
            policy=policy
        )
    except TypeError:
        pytest.fail("MapCall instruction does not accept 'policy' argument")
        
    assert instr.policy == policy
    assert instr.policy.retry.max_attempts == 5
~~~~~

#### Acts 2: 编写多态操作数测试 (Rich Operands Specs)

我们将定义 `test_rich_operands.py`，它强制要求 `Operand` 体系支持资源引用和上下文引用，并且这些新类型可以被用于 `Call` 指令的参数列表中。

~~~~~act
write_file
packages/cascade-spec/tests/blueprint/test_rich_operands.py
~~~~~
~~~~~python
import pytest
from dataclasses import is_dataclass
from cascade.spec.blueprint import Call, Register, Literal, ContextOperand, ResourceOperand, Operand

def test_resource_operand_structure():
    """
    验证 ResourceOperand 的存在和结构。
    它用于在指令层面表示 'cs.inject("db")'，推迟解析到运行时。
    """
    try:
        # 对应 code: cs.inject("db_connection")
        op = ResourceOperand(name="db_connection")
    except NameError:
        pytest.fail("ResourceOperand class is not defined in cascade.spec.blueprint")

    assert is_dataclass(op)
    assert isinstance(op, Operand)
    assert op.name == "db_connection"

def test_context_operand_structure():
    """
    验证 ContextOperand 的存在和结构。
    它用于直接从运行时上下文（如 params, env）中加载数据，
    这对应 'cs.Param("env_name")' 的编译结果。
    """
    try:
        # 对应 code: cs.Param("env_name")
        op = ContextOperand(scope="params", key="env_name")
    except NameError:
        pytest.fail("ContextOperand class is not defined in cascade.spec.blueprint")

    assert is_dataclass(op)
    assert isinstance(op, Operand)
    assert op.scope == "params"
    assert op.key == "env_name"

def test_call_instruction_accepts_polymorphic_operands():
    """
    验证 Call 指令的 args/kwargs 可以混合接受 Literal, Register 以及新的 Operand 类型。
    """
    # 构造混合参数列表
    mixed_args = [
        Literal(1),                      # 常量
        Register(0),                     # 运行时中间结果
        ResourceOperand("db"),           # 依赖注入
        ContextOperand("params", "key")  # 全局参数
    ]
    
    try:
        instr = Call(
            output=Register(1),
            task_name="test_task",
            args=mixed_args,
            kwargs={"ctx": ContextOperand("env", "HOME")},
            structure_hash="hash_abc"
        )
    except TypeError as e:
        pytest.fail(f"Call instruction failed to accept polymorphic operands: {e}")
    
    # 验证类型保持
    assert isinstance(instr.args[2], ResourceOperand)
    assert isinstance(instr.args[3], ContextOperand)
    assert isinstance(instr.kwargs["ctx"], ContextOperand)
~~~~~

### 下一步建议
执行测试（`pytest packages/cascade-spec`）。
如果测试失败（RED），则修改 `cascade-spec` 中的代码以实现这些数据结构。
如果测试通过（GREEN，如果代码已存在），则确认契约已锁定，并继续进行 **阶段 2：编译器升级 (The Compiler)**。
