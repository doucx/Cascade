import pytest
import asyncio
from unittest.mock import MagicMock

from cascade.spec.blueprint import Blueprint, Call, Register, Literal, ContextOperand, ResourceOperand, ExecutionPolicy, RetryPolicySpec
from cascade.vm import VirtualMachine, ResourceManager
from cascade.vm.middleware import ExecutionContext

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
    Validation: VM should replace ContextOperand('params', 'x') with current value.
    Current State: VM (raw pipeline) will pass ContextOperand object to function -> TypeError.
    """
    vm = VirtualMachine()
    
    # Needs: ContextMiddleware
    # But ContextMiddleware needs access to 'params'. WHERE do params live?
    # In VM architecture, params are usually passed via initial_kwargs or similar?
    # Or VM needs a 'context' registry?
    # Let's assume for now params are passed in via 'execution_context' dict or initial_kwargs to execute?
    # Spec definition: ContextOperand(scope='params', key='x')
    
    # We pass params to execute() as a contract
    # But wait, vm.execute() signature is: execute(blueprint, symbol_table, initial_args, initial_kwargs)
    # It doesn't have a generic 'context' bag yet.
    # HARDENING REQUIREMENT: VM.execute needs a way to separate 'stack inputs' from 'global context'.
    # We will pass params inside `initial_kwargs`? No, that messes up stack mapping.
    
    # RED FLAG: The VM interface needs upgrade to support Context.
    # For this test, we assume we will add `context_data` to vm.execute or similar mechanism.
    # Let's hypothesize specific kwargs usage or a new argument.
    
    context_data = {"params": {"env": "prod"}}
    
    def task_fn(env_name):
        return f"Env is {env_name}"

    symbol_table = {"hash_task": task_fn}
    
    instr = Call(
        output=Register(0),
        task_name="read_env",
        structure_hash="hash_task",
        args=[ContextOperand(scope="params", key="env")],
        kwargs={}
    )
    bp = Blueprint(instructions=[instr], register_count=1)

    # We expect `vm.execute` to accept context data eventually.
    # Currently it doesn't. This test failure will drive API change.
    # We pass it via a theoretical `context_data` arg.
    try:
        result = await vm.execute(bp, symbol_table, context_data=context_data)
    except TypeError:
        pytest.fail("VM.execute does not accept context data, cannot resolve params.")
    
    assert result == "Env is prod"


@pytest.mark.asyncio
async def test_vm_resolves_resource_operands():
    """
    Validation: VM should resolve ResourceOperand('db') to an actual object.
    Current State: VM passes ResourceOperand object -> Function fails.
    """
    db_obj = MagicMock()
    rm = InMemoryResourceManager(resources={"db": db_obj})
    
    # VM needs to know about the resource manager.
    # It is passed in __init__.
    vm = VirtualMachine(resource_manager=rm)
    
    def task_fn(db):
        return db.query()

    symbol_table = {"hash_db": task_fn}
    
    instr = Call(
        output=Register(0),
        task_name="use_db",
        structure_hash="hash_db",
        args=[ResourceOperand(name="db")],
        kwargs={}
    )
    bp = Blueprint([instr], 1)

    result = await vm.execute(bp, symbol_table)
    
    assert result == db_obj.query.return_value


@pytest.mark.asyncio
async def test_vm_enforces_retry_policy():
    """
    Validation: VM should auto-retry on failure if policy is set.
    """
    vm = VirtualMachine()
    
    func_mock = MagicMock(side_effect=[ValueError("Boom"), "Success"])
    
    policy = ExecutionPolicy(retry=RetryPolicySpec(max_attempts=2))
    
    instr = Call(
        output=Register(0),
        task_name="flaky",
        structure_hash="hash_flaky",
        policy=policy,
        args=[], kwargs={}
    )
    bp = Blueprint([instr], 1)
    
    result = await vm.execute(bp, {"hash_flaky": func_mock})
    
    assert result == "Success"
    assert func_mock.call_count == 2