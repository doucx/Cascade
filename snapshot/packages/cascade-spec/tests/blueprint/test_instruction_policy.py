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