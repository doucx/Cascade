import pytest
from unittest.mock import MagicMock, call
import asyncio
from typing import Any, List

from cascade.spec.blueprint import Blueprint, Call, Register, Literal, ResourceOperand, ContextOperand, ExecutionPolicy, RetryPolicySpec
from cascade.vm import VirtualMachine, Frame

# 注意：这些类目前还不存在，是本测试驱动的目标
# 我们在测试中假定它们在 cascade.vm.middleware 中定义
# 运行时会导致 ImportError，符合 RED 状态要求
try:
    from cascade.vm.middleware import Middleware, ExecutionContext
except ImportError:
    # 为了让 IDE 和 Linter 不报错，我们在这里定义临时的 Protocol 存根
    # 实际运行测试时，如果源码没实现，依然会挂在 import 上，这是预期的
    from typing import Protocol, Callable, Awaitable
    class ExecutionContext:
        instruction: Any
        frame: Any
        resolved_args: List[Any]
        resolved_kwargs: dict
    
    class Middleware(Protocol):
        async def handle(self, ctx: ExecutionContext, next_handler: Callable[..., Awaitable[Any]]) -> Any: ...


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

        async def handle(self, ctx, next_handler):
            call_log.append(f"{self.name}_pre")
            result = await next_handler()
            call_log.append(f"{self.name}_post")
            return result

    # 1. Setup VM with Middlewares
    vm = VirtualMachine()
    # 假设 VM 暴露了 set_middleware 方法或构造函数参数
    # 这里定义我们期望的 API
    vm.set_middlewares([
        LoggingMiddleware("A"),
        LoggingMiddleware("B")
    ])

    # 2. Execute a simple instruction
    # Mock symbol table
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
async def test_resource_operand_resolution_via_middleware():
    """
    验证 ResourceOperand 不是由 VM 核心解析，而是由 ResourceMiddleware 解析。
    这证明了解耦：VM 核心不需要知道什么是 'Resource'。
    """
    class MockResourceMiddleware:
        def __init__(self, resources):
            self.resources = resources

        async def handle(self, ctx: ExecutionContext, next_handler):
            # 模拟 Middleware 遍历参数并解析 ResourceOperand
            # 这是我们期望 Middleware 实现的逻辑
            new_args = []
            for arg in ctx.resolved_args: # 假设初始 resolved_args 包含未解析的 Operand? 
            # 或者更合理的设计：ctx.args 是原始 Operand, ctx.resolved_args 是值。
            # 为了测试简便，我们假设 BaseResolver 已经把 Literal 转换了，但 ResourceOperand 留给了我们。
            # 这里测试我们要扩充 ctx.resolved_args
                if isinstance(arg, ResourceOperand):
                    if arg.name in self.resources:
                        new_args.append(self.resources[arg.name])
                    else:
                        raise ValueError(f"Resource {arg.name} not found")
                else:
                    new_args.append(arg)
            
            ctx.resolved_args = new_args
            return await next_handler()

    # Setup
    vm = VirtualMachine()
    vm.set_middlewares([MockResourceMiddleware(resources={"db": "postgres_conn"})])

    func_mock = MagicMock(return_value=True)
    
    # Instruction uses ResourceOperand
    instr = Call(
        output=Register(0),
        task_name="db_task",
        structure_hash="hash_db",
        args=[ResourceOperand("db")], # <-- The operand to resolve
        kwargs={}
    )
    bp = Blueprint(instructions=[instr], register_count=1)

    await vm.execute(bp, {"hash_db": func_mock})

    # Assert Core received the RESOLVED value ("postgres_conn"), not the Operand object
    func_mock.assert_called_once_with("postgres_conn")


@pytest.mark.asyncio
async def test_policy_handling_via_middleware():
    """
    验证 Middleware 能够读取 Instruction 上的 Policy 并改变执行流（例如重试）。
    """
    class RetryMiddleware:
        async def handle(self, ctx: ExecutionContext, next_handler):
            policy = ctx.instruction.policy
            # 如果没有策略，直接执行
            if not policy or not policy.retry:
                return await next_handler()
            
            # 简单的重试逻辑模拟
            attempts = policy.retry.max_attempts
            last_err = None
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
    # side_effect: fail, fail, success
    func_mock = MagicMock(side_effect=[ValueError("Fail 1"), ValueError("Fail 2"), "Success"])
    
    # Instruction with Retry Policy
    policy = ExecutionPolicy(retry=RetryPolicySpec(max_attempts=3))
    instr = Call(
        output=Register(0),
        task_name="flaky",
        structure_hash="hash_flaky",
        policy=policy, # Policy is attached here
        args=[], kwargs={}
    )
    bp = Blueprint(instructions=[instr], register_count=1)

    result = await vm.execute(bp, {"hash_flaky": func_mock})

    assert result == "Success"
    assert func_mock.call_count == 3