import pytest
from unittest.mock import MagicMock

from cascade.spec.blueprint import Blueprint, Call, Register, ContextOperand, ResourceOperand, ExecutionPolicy, RetryPolicySpec
from cascade.vm import VirtualMachine
from cascade.vm.middleware.standard import (
    ArgumentResolutionMiddleware, 
    RetryMiddleware
)

# --- Helpers ---

class InMemoryResourceManager:
    """A minimal resource manager for testing VM integration."""
    def __init__(self, resources):
        self.resources = resources
        self.acquired = []

    async def acquire(self, requirements):
        self.acquired.append(("acquire", requirements))

    async def release(self, requirements):
        self.acquired.append(("release", requirements))
    
    def get_resource(self, name):
        return self.resources.get(name)

# --- Tests ---

@pytest.mark.asyncio
async def test_vm_resolves_context_operands():
    """
    Validation: VM should replace ContextOperand('params', 'x') with current value
    using the ArgumentResolutionMiddleware.
    """
    vm = VirtualMachine()
    
    # Configure Middleware with explicit context
    global_context = {"env": "prod"}
    active_resources = {}
    
    vm.set_middlewares([
        ArgumentResolutionMiddleware(active_resources, global_context)
    ])
    
    def task_fn(env_name):
        return f"Env is {env_name}"

    symbol_table = {"hash_task": task_fn}
    
    instr = Call(
        output=Register(0),
        task_name="read_env",
        current_code_structure_hash="hash_task",
        args=[ContextOperand(scope="params", key="env")],
        kwargs={}
    )
    bp = Blueprint(instructions=[instr], register_count=1)

    result = await vm.execute(bp, symbol_table)
    
    assert result == "Env is prod"


@pytest.mark.asyncio
async def test_vm_resolves_resource_operands():
    """
    Validation: VM should resolve ResourceOperand('db') to an actual object.
    """
    db_obj = MagicMock()
    db_obj.query.return_value = "query_result"
    
    vm = VirtualMachine()
    
    # Configure Middleware for injection
    active_resources = {"db": db_obj}
    vm.set_middlewares([
        ArgumentResolutionMiddleware(active_resources, global_context={})
    ])
    
    def task_fn(db):
        return db.query()

    symbol_table = {"hash_db": task_fn}
    
    instr = Call(
        output=Register(0),
        task_name="use_db",
        current_code_structure_hash="hash_db",
        args=[ResourceOperand(name="db")],
        kwargs={}
    )
    bp = Blueprint(instructions=[instr], register_count=1)

    result = await vm.execute(bp, symbol_table)
    
    assert result == "query_result"


@pytest.mark.asyncio
async def test_vm_enforces_retry_policy():
    """
    Validation: VM should auto-retry on failure if policy is set.
    """
    vm = VirtualMachine()
    vm.set_middlewares([RetryMiddleware()])
    
    # Mock function: fails once, then succeeds
    func_mock = MagicMock(side_effect=[ValueError("Boom"), "Success"])
    
    policy = ExecutionPolicy(retry=RetryPolicySpec(max_attempts=2, delay=0.01))
    
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
    assert func_mock.call_count == 2