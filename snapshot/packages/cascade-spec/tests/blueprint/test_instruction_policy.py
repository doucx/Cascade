import pytest
from cascade.spec.blueprint import Call, Register, RetryPolicySpec, ExecutionPolicy

def test_execution_policy_structure():
    """
    验证 ExecutionPolicy 聚合对象的存在。
    它将作为元数据附加在指令上，包含 Retry, Constraints, Timeouts 等。
    """
    try:
        # 定义一个重试策略规格
        retry = RetryPolicySpec(max_attempts=3, delay=1.0, backoff=2.0)
        # 定义聚合策略
        policy = ExecutionPolicy(retry=retry, resources={"gpu": 1})
    except NameError:
        pytest.fail("Strategies (RetryPolicySpec, ExecutionPolicy) are not defined in cascade.spec.blueprint")

    assert policy.retry.max_attempts == 3
    assert policy.resources["gpu"] == 1

def test_call_instruction_has_policy_field():
    """
    验证 Call 指令包含 structured 'policy' 字段。
    """
    policy = ExecutionPolicy(resources={"memory": "1Gi"})
    
    instr = Call(
        output=Register(0),
        task_name="t",
        current_code_structure_hash="h",
        policy=policy # 这里应该由于字段不存在而失败
    )
    
    assert instr.policy == policy
    assert instr.policy.resources["memory"] == "1Gi"