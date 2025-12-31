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
        current_code_structure_hash="hash_func", 
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
        current_code_structure_hash="hash_db",
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
        current_code_structure_hash="hash_flaky",
        policy=policy,
        args=[], kwargs={}
    )
    bp = Blueprint(instructions=[instr], register_count=1)

    result = await vm.execute(bp, {"hash_flaky": func_mock})

    assert result == "Success"
    assert func_mock.call_count == 3