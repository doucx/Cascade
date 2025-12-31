简要回答：
当前位置：我们已经成功完成了 **[阶段 2：VM 管道化改造]** 的核心实施工作。`VirtualMachine` 现在已经是一个支持中间件的智能引擎，并且通过了集成测试 (`test_vm_capabilities.py`)，证明了其处理资源、上下文和重试策略的能力。

下一个逻辑任务：**[偿还 TDD 技术债与测试一致性]**。在 TDD 的 RED 阶段，我们在 `test_middleware_pipeline.py` 中使用了临时的类型存根（Stubs）来模拟不存在的 `Middleware` 接口。现在真实代码已就位，我们必须重构该测试以引用真实的 `cascade.vm.middleware` 定义。这不仅是清理代码，更是验证我们的实现是否真正符合原本的设计契约。

## [WIP] refactor(tests): Align middleware unit tests with implementation

### 用户需求
移除 `test_middleware_pipeline.py` 中的临时类型定义和 `try...except ImportError` 块，使其直接使用 `cascade-vm` 包中实际实现的 `Middleware` 和 `ExecutionContext` 类。

### 评论
这是 TDD 周期中至关重要的“重构”步骤。保留测试存根会导致测试与实际代码脱节，产生“虚假的绿色”安全感。通过链接到真实代码，我们确保了测试套件的长期有效性和类型安全性。

### 目标
1.  重构 `packages/cascade-vm/tests/unit/test_middleware_pipeline.py`。
2.  验证重构后的测试能否通过。

### 基本原理
消除代码库中的临时脚手架，执行“代码清理”原则。

### 标签
#intent/refine #flow/ready #priority/medium #comp/tests #comp/vm #scope/core #ai/instruct #task/domain/testing #task/object/unit-test #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 重构单元测试

我们将移除文件头部的 `try...except` 块，改用标准的 import 语句。同时，由于 `ResourceOperand` 的解析逻辑在之前的 Acts 中已经作为 `ResourceLifecycleMiddleware` 的一部分被讨论，或者在 `ArgumentResolutionMiddleware` 中实现，我们需要确认测试逻辑与标准实现的一致性，或者保持测试作为独立的 Mock 实现来验证管道机制本身（这是单元测试的本意）。

这里我们保留测试中的 `MockResourceMiddleware` 类，因为它用于验证管道机制，但我们会让它继承真实的 `Middleware` 协议（虽然 Protocol 是隐式的，但显式引用有助于 IDE）。最重要的是 `ExecutionContext` 必须是真实的，因为它是数据载体。

~~~~~act
write_file
packages/cascade-vm/tests/unit/test_middleware_pipeline.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
import asyncio
from typing import Any

from cascade.spec.blueprint import Blueprint, Call, Register, Literal, ResourceOperand, ExecutionPolicy, RetryPolicySpec
from cascade.vm import VirtualMachine
from cascade.vm.middleware import Middleware, ExecutionContext, NextHandler


@pytest.mark.asyncio
async def test_pipeline_execution_order():
    """
    验证 Middleware 按照 洋葱模型 (Onion Model) 执行：
    Middleware A (Pre) -> Middleware B (Pre) -> Core -> Middleware B (Post) -> Middleware A (Post)
    """
    call_log = []

    class LoggingMiddleware:
        def __init__(self, name):
            self.name = name

        async def handle(self, ctx: ExecutionContext, next_handler: NextHandler):
            call_log.append(f"{self.name}_pre")
            result = await next_handler()
            call_log.append(f"{self.name}_post")
            return result

    # 1. Setup VM with Middlewares
    vm = VirtualMachine()
    vm.set_middlewares([
        LoggingMiddleware("A"),
        LoggingMiddleware("B")
    ])

    # 2. Execute a simple instruction
    func_mock = MagicMock(return_value="core_result")
    symbol_table = {"hash_func": func_mock}
    
    instr = Call(
        output=Register(0),
        task_name="test_task",
        structure_hash="hash_func", 
        args=[], 
        kwargs={}
    )
    bp = Blueprint(instructions=[instr], register_count=1)

    await vm.execute(bp, symbol_table)

    # 3. Assert Order
    assert call_log == ["A_pre", "B_pre", "B_post", "A_post"]
    assert func_mock.called


@pytest.mark.asyncio
async def test_resource_operand_pass_through_frame():
    """
    验证 VM 和 Frame 能够传递原始的 ResourceOperand 给 Middleware，而不是报错。
    核心逻辑不在 Frame 中解析，而是留给 Middleware。
    """
    class MockResolverMiddleware:
        async def handle(self, ctx: ExecutionContext, next_handler: NextHandler):
            # 模拟解析：将 ResourceOperand 替换为字符串
            new_args = []
            for arg in ctx.resolved_args:
                if isinstance(arg, ResourceOperand):
                    new_args.append(f"resolved_{arg.name}")
                else:
                    new_args.append(arg)
            ctx.resolved_args = new_args
            return await next_handler()

    # Setup
    vm = VirtualMachine()
    vm.set_middlewares([MockResolverMiddleware()])

    func_mock = MagicMock(return_value=True)
    
    # Instruction uses ResourceOperand
    instr = Call(
        output=Register(0),
        task_name="db_task",
        structure_hash="hash_db",
        args=[ResourceOperand("db")], 
        kwargs={}
    )
    bp = Blueprint(instructions=[instr], register_count=1)

    await vm.execute(bp, {"hash_db": func_mock})

    # Assert Core received the RESOLVED value
    func_mock.assert_called_once_with("resolved_db")


@pytest.mark.asyncio
async def test_policy_handling_via_middleware():
    """
    验证 Middleware 能够读取 Instruction 上的 Policy 并改变执行流（例如重试）。
    """
    class RetryMiddleware:
        async def handle(self, ctx: ExecutionContext, next_handler: NextHandler):
            policy = ctx.instruction.policy
            if not policy or not policy.retry:
                return await next_handler()
            
            # Simple retry simulation
            attempts = policy.retry.max_attempts
            last_err = None
            # range(attempts + 1) means initial + retries
            for _ in range(attempts + 1):
                try:
                    return await next_handler()
                except Exception as e:
                    last_err = e
                    continue
            raise last_err

    vm = VirtualMachine()
    vm.set_middlewares([RetryMiddleware()])

    # Mock function that fails twice then succeeds
    func_mock = MagicMock(side_effect=[ValueError("Fail 1"), ValueError("Fail 2"), "Success"])
    
    policy = ExecutionPolicy(retry=RetryPolicySpec(max_attempts=3))
    instr = Call(
        output=Register(0),
        task_name="flaky",
        structure_hash="hash_flaky",
        policy=policy,
        args=[], kwargs={}
    )
    bp = Blueprint(instructions=[instr], register_count=1)

    result = await vm.execute(bp, {"hash_flaky": func_mock})

    assert result == "Success"
    assert func_mock.call_count == 3
~~~~~

### 下一步建议
现在测试代码已经干净且一致。我们已经完成了 VM 的硬化工作。
接下来的主要任务是 **[阶段 3: 移除胶水层 (The Purge)]**。这涉及将 `cascade-engine` 的重心转移到我们构建的新 Compiler-VM 管道上。
考虑到稳定性，建议在全面移除之前，先启用一个**“并行测试阶段”**：运行所有现有的 `cascade-engine` 测试，但强制开启 `use_vm=True` 选项（可以通过临时修改代码或环境变量实现），看看新架构在旧测试套件下的表现如何。这将是真正的“验收测试”。
