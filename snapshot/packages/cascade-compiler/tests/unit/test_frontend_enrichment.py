import pytest
import cascade as cs
from cascade.compiler.frontend import Frontend
from cascade.spec.ir.models import NodeIR


def test_frontend_preserves_retry_policy():
    """
    验证 Frontend 将 LazyResult.with_retry() 的信息编码进 NodeIR。
    """

    @cs.task
    def flaky_task():
        pass

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
    def heavy_task():
        pass

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
    def db_task(conn=cs.inject("db_primary")):
        pass

    # 情况 1: 默认值注入
    target = db_task()
    result = Frontend.compile(target)
    node = result.ir.nodes[0]

    # Frontend 需要分析函数签名，发现默认值是 Inject，并将其记录
    # 这可能体现在 kwargs 中的特殊结构，或者 input_specs 中。
    # 策略：Frontend 应该将 kwargs 中对应的值设置为一个特殊的 InjectionIR 对象
    # 而不是 Python 的原始 Inject 对象 (为了 IR 的纯粹性)

    from cascade.spec.ir.models import InjectionIR  # New expectation

    # 检查 kwargs['conn'] 是否被转换为了 InjectionIR 类型
    arg_val = node.kwargs.get("conn")
    if not arg_val:
        # 如果不在 kwargs (因为是默认值)，Frontend 应该显式化它吗？
        # 架构决策：是的，Compile 后的 IR 应该是 explicit 的。
        # Frontend 应该解析 default values 并填充到 kwargs 中，使 IR 自包含。
        pytest.fail("Frontend did not explicitize the default injected argument 'conn'")

    assert isinstance(arg_val, InjectionIR)  # 期望类型
    assert arg_val.resource_name == "db_primary"
