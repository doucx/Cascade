## [WIP] 这是 **架构硬化 (Architecture Hardening)** 的第一步。我们将定义 Spec 和 Compiler 在处理上下文注入和策略元数据时必须满足的新契约。

这个计划将创建 4 个新的测试文件，直接将项目置于 **RED** 状态。这些测试定义了系统应该长什么样，即使现在代码还完全不支持。

### 计划概览

1.  **Spec 层**: 定义 `ContextOperand` (用于 params), `ResourceOperand` (用于 inject), 以及指令上的 `policy` 字段 (用于 retry/constraints)。
2.  **Compiler 前端**: 验证 Frontend 不再忽略 `LazyResult` 上的 `_retry_policy` 和 `_constraints`，而是将其打包进 `NodeIR`。
3.  **Compiler 后端**: 验证 Backend 能够识别 `Inject` 标记并编译为 `ResourceOperand`，同时将 IR 中的策略透传给 `Call` 指令。

---

## 标签
#intent/architect #flow/ready #priority/critical
#comp/spec #comp/compiler
#task/domain/core #task/object/hardening-enrichment #task/action/tdd-scaffold
#task/state/begin

---

### Script

#### Acts 1: 定义 Spec 层的新契约 (Spec Hardening)

我们需要扩充 `Blueprint` 的表达能力。指令不再只是简单的 "Register + Literal"，它需要能引用环境上下文。同时，指令需要携带执行策略。

~~~~~act
write_file
packages/cascade-spec/tests/blueprint/test_rich_operands.py
~~~~~
~~~~~python
import pytest
from dataclasses import is_dataclass
from cascade.spec.blueprint import Call, Register, Literal, ContextOperand, ResourceOperand

def test_resource_operand_structure():
    """
    验证 ResourceOperand 的存在和结构。
    用于替代运行时魔法 ArgumentResolver，显式表达 'cs.inject'。
    """
    try:
        # 对应 code: cs.inject("db_connection")
        op = ResourceOperand(name="db_connection")
    except NameError:
        pytest.fail("ResourceOperand class is not defined in cascade.spec.blueprint")

    assert is_dataclass(op)
    assert op.name == "db_connection"

def test_context_operand_structure():
    """
    验证 ContextOperand 的存在和结构。
    用于直接从 params/context 中加载数据，对应 'cs.Param' 的优化编译。
    """
    try:
        # 对应 code: cs.Param("env_name")
        op = ContextOperand(scope="params", key="env_name")
    except NameError:
        pytest.fail("ContextOperand class is not defined in cascade.spec.blueprint")

    assert is_dataclass(op)
    assert op.scope == "params"
    assert op.key == "env_name"

def test_call_instruction_accepts_polymorphic_operands():
    """
    验证 Call 指令的 args/kwargs 可以接受新的 Operand 类型。
    """
    instr = Call(
        output=Register(0),
        task_name="test_task",
        args=[
            Literal(1), 
            ResourceOperand("db"), 
            ContextOperand("params", "timeout")
        ],
        kwargs={},
        structure_hash="hash_abc"
    )
    
    assert isinstance(instr.args[1], ResourceOperand)
    assert isinstance(instr.args[2], ContextOperand)
~~~~~

~~~~~act
write_file
packages/cascade-spec/tests/blueprint/test_instruction_policy.py
~~~~~
~~~~~python
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
        structure_hash="h",
        policy=policy # 这里应该由于字段不存在而失败
    )
    
    assert instr.policy == policy
    assert instr.policy.resources["memory"] == "1Gi"
~~~~~

#### Acts 2: 验证 Compiler Frontend 的数据提取 (Information Preservation)

Frontend 必须停止丢弃信息。它需要将 `LazyResult` 上的策略“吸入”到 `NodeIR` 中。

~~~~~act
write_file
packages/cascade-compiler/tests/unit/test_frontend_enrichment.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.compiler.frontend import Frontend
from cascade.spec.ir.models import NodeIR

def test_frontend_preserves_retry_policy():
    """
    验证 Frontend 将 LazyResult.with_retry() 的信息编码进 NodeIR。
    """
    @cs.task
    def flaky_task(): pass

    # 用户定义了重试策略
    target = flaky_task().with_retry(max_attempts=5, delay=0.5)

    result = Frontend.compile(target)
    node: NodeIR = result.ir.nodes[0]

    # RED: 目前 NodeIR 没有 standardized 的 policy 存储位置
    # 我们期望 Frontend 将其放到 node.policy 或者 node.meta['policy'] 中
    # 为了硬化架构，我们要求 NodeIR 有明确的 `policy` 字段 (类型为 dict 或 dataclass)
    
    if not hasattr(node, "policy"):
        pytest.fail("NodeIR is missing 'policy' field")

    assert node.policy is not None
    assert node.policy.retry.max_attempts == 5
    assert node.policy.retry.delay == 0.5

def test_frontend_preserves_constraints():
    """
    验证 Frontend 将 .with_constraints() 编码进 NodeIR。
    """
    @cs.task
    def heavy_task(): pass

    target = heavy_task().with_constraints(gpu=1)

    result = Frontend.compile(target)
    node: NodeIR = result.ir.nodes[0]

    assert node.policy is not None
    assert node.policy.resources["gpu"] == 1

def test_frontend_detects_inject_marker():
    """
    验证 Frontend 识别 InputBindings 中的 Inject 对象，并不将其视为普通 Literal。
    """
    @cs.task
    def db_task(conn = cs.inject("db_primary")): pass

    # 情况 1: 默认值注入
    target = db_task() 
    result = Frontend.compile(target)
    node = result.ir.nodes[0]

    # Frontend 需要分析函数签名，发现默认值是 Inject，并将其记录
    # 这可能体现在 kwargs 中的特殊结构，或者 input_specs 中。
    # 策略：Frontend 应该将 kwargs 中对应的值设置为一个特殊的 InjectionIR 对象
    # 而不是 Python 的原始 Inject 对象 (为了 IR 的纯粹性)
    
    from cascade.spec.ir.models import InjectionIR # New expectation
    
    # 检查 kwargs['conn'] 是否被转换为了 InjectionIR 类型
    arg_val = node.kwargs.get('conn')
    if not arg_val:
         # 如果不在 kwargs (因为是默认值)，Frontend 应该显式化它吗？
         # 架构决策：是的，Compile 后的 IR 应该是 explicit 的。
         # Frontend 应该解析 default values 并填充到 kwargs 中，使 IR 自包含。
         pytest.fail("Frontend did not explicitize the default injected argument 'conn'")

    assert isinstance(arg_val, InjectionIR) # 期望类型
    assert arg_val.resource_name == "db_primary"
~~~~~

#### Acts 3: 验证 Compiler Backend 的编译能力 (Operand Compilation)

Backend 必须能够消费丰富的 `NodeIR` 并生成包含新操作数和策略的 `Call` 指令。

~~~~~act
write_file
packages/cascade-compiler/tests/unit/test_backend_enrichment.py
~~~~~
~~~~~python
import pytest
from cascade.compiler.backend import Backend
from cascade.spec.ir.models import GraphIR, NodeIR, TaskDef, InjectionIR
from cascade.spec.blueprint import ResourceOperand, Call
from cascade.spec.fingerprint import Fingerprint

class MockPolicy:
    def __init__(self, retry=None, resources=None):
        self.retry = retry
        self.resources = resources or {}

def _create_dummy_task_def(name):
    fp = Fingerprint.from_dict({"current_code_structure_hash": "h"})
    return TaskDef(name=name, args=[], fingerprint=fp)

def test_backend_compiles_injection_to_resource_operand():
    """
    验证 Backend 将 NodeIR 中的 InjectionIR 转换为 Call 指令中的 ResourceOperand。
    """
    # 1. 手动构造包含 InjectionIR 的 GraphIR
    task_def = _create_dummy_task_def("db_task")
    node = NodeIR(
        id="n1", 
        definition=task_def,
        kwargs={
            "conn": InjectionIR(resource_name="postgres_prod") # Expectation
        }
    )
    
    graph = GraphIR(nodes=[node], edges=[])
    plan = [["n1"]]

    # 2. Compile
    blueprint = Backend.compile(graph, plan)
    
    # 3. Assert
    instr = blueprint.instructions[0]
    assert isinstance(instr, Call)
    
    operand = instr.kwargs["conn"]
    assert isinstance(operand, ResourceOperand)
    assert operand.name == "postgres_prod"

def test_backend_transfers_policy_to_instruction():
    """
    验证 Backend 将 NodeIR.policy 转移到 Call.policy。
    """
    task_def = _create_dummy_task_def("retry_task")
    
    # 模拟 IR 携带的策略
    policy_data = MockPolicy(resources={"cpu": 4})
    node = NodeIR(id="n1", definition=task_def, policy=policy_data) # Expectation: policy field on NodeIR
    
    graph = GraphIR(nodes=[node], edges=[])
    plan = [["n1"]]

    blueprint = Backend.compile(graph, plan)
    instr = blueprint.instructions[0]
    
    assert instr.policy is not None
    assert instr.policy.resources["cpu"] == 4
~~~~~

---

### 下一步建议

这些测试在当前代码库下会**全部失败**（ImportError, AttributeError, Assertion Errors）。这是预期的。它们精确地定义了我们需要填补的架构鸿沟。

请确认执行，我将生成这些文件。随后，我们将开始 TDD 的 Green 阶段：修改 Spec 和 Compiler 来满足这些测试。
