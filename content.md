Excellent. All tests have passed, confirming the success of the decoupling. We are now ready for the final and most impactful step of this "Architecture Hardening" task.

Your analysis is spot on. The `func` field in our `Blueprint` instructions is the last piece of runtime state polluting our otherwise pure, serializable compilation artifact. By removing it and delegating the linking responsibility to the `VirtualMachine`, we make the `Blueprint` a true "binary" that can be cached, sent over a network, and executed in a different process. This is the absolute prerequisite for advanced features.

I will now generate the plan to execute this final refactoring.

## [WIP] refactor(vm): Purify Blueprint and delegate linking to VirtualMachine

### 用户需求
彻底净化 `Blueprint` 数据结构，移除所有运行时对象（`func` 字段），并将函数链接的责任从 `VMExecutionStrategy` 下放至 `VirtualMachine` 核心。

### 评论
这是本次架构硬化任务中最具价值的一步。通过移除 `func` 字段，`Blueprint` 真正蜕变为一个纯粹的、可序列化的数据结构。将链接逻辑内聚到 `VirtualMachine` 内部，不仅简化了 `Engine` 策略层的职责，也使得 `VM` 更加自包含和健壮。这一改变是实现持久化缓存、分布式执行等高级功能的不可或缺的基础。

### 目标
1.  从 `cascade.spec.blueprint` 中的 `Call` 和 `MapCall` 指令定义中彻底移除 `func` 字段。
2.  更新 `cascade.compiler.backend`，移除对 `func=None` 的赋值。
3.  重构 `cascade.runtime.strategies.vm.VMExecutionStrategy`，使其不再执行链接过程，而是将 `symbol_table` 直接传递给 `VirtualMachine`。
4.  重构 `cascade.vm.machine.VirtualMachine`，修改其 `execute` 签名以接收 `symbol_table`，并在指令分发循环中实时通过 `structure_hash` 查找并调用函数。
5.  修复因上述变更而损坏的相关测试，特别是 `test_vm_linking.py`。

### 基本原理
`Blueprint` 的目标是成为一个与运行时无关的编译产物。`func` 字段直接引用内存中的 Python 函数对象，破坏了这一核心原则。

本计划通过以下方式修正架构：
1.  在 `spec` 层移除 `func` 字段，强制 `Blueprint` 的纯粹性。
2.  `Frontend` 在编译时生成 `symbol_table`，这是一个从 `structure_hash` 到 `Callable` 的映射。
3.  `Engine` 的 `VMExecutionStrategy` 仅作为协调者，将 `Blueprint` 和 `symbol_table` 这两个独立的 artifact 一同传递给 `VM`。
4.  `VM` 在执行每条 `Call` 或 `MapCall` 指令时，才使用指令中的 `structure_hash` 作为 key，去 `symbol_table` 中动态查找需要执行的函数。

这个模型将“编译产物”和“运行时上下文”彻底分离，实现了最终的架构净化。

### 标签
#intent/refine #flow/ready #priority/high #comp/spec #comp/compiler #comp/engine #comp/vm #concept/ir #concept/executor #scope/core #ai/instruct #task/domain/architecture #task/object/ir-model #task/action/refactor #task/state/end #task/status/active

---

### Script

#### Acts 1: Purify `Blueprint` Spec

我们首先从 `spec` 中移除 `func` 字段，这是所有变更的起点。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/blueprint.py
~~~~~
~~~~~python.old
@dataclass
class Call(Instruction):
    func: Any
    output: Register
    args: List[Operand] = field(default_factory=list)
    kwargs: Dict[str, Operand] = field(default_factory=dict)

    # Metadata for observability and constraints
    task_name: str = "unknown"
    constraints: Optional[ResourceConstraint] = None
    structure_hash: Optional[str] = None
~~~~~
~~~~~python.new
@dataclass
class Call(Instruction):
    output: Register
    args: List[Operand] = field(default_factory=list)
    kwargs: Dict[str, Operand] = field(default_factory=dict)

    # Metadata for observability and constraints
    task_name: str = "unknown"
    constraints: Optional[ResourceConstraint] = None
    structure_hash: Optional[str] = None
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/blueprint.py
~~~~~
~~~~~python.old
@dataclass
class MapCall(Instruction):
    """Represents a map operation over iterable inputs."""

    func: Any
    output: Register
    args: List[Operand] = field(default_factory=list)
    kwargs: Dict[str, Operand] = field(default_factory=dict)

    # Metadata for observability and constraints
    task_name: str = "unknown"
    constraints: Optional[ResourceConstraint] = None
    structure_hash: Optional[str] = None
~~~~~
~~~~~python.new
@dataclass
class MapCall(Instruction):
    """Represents a map operation over iterable inputs."""

    output: Register
    args: List[Operand] = field(default_factory=list)
    kwargs: Dict[str, Operand] = field(default_factory=dict)

    # Metadata for observability and constraints
    task_name: str = "unknown"
    constraints: Optional[ResourceConstraint] = None
    structure_hash: Optional[str] = None
~~~~~

#### Acts 2: Update `Backend` Compiler

移除 `Backend` 中对 `func=None` 的冗余赋值。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
        if node.meta.get("is_map"):
            instr = MapCall(
                func=None,
                output=output_register,
                args=args,
                kwargs=kwargs,
                task_name=node.definition.name,
                structure_hash=structure_hash,
                # Note: Constraints on Map nodes are not yet propagated to MapCall.
            )
        else:
            instr = Call(
                func=None,  # The VM will need to resolve this later
                output=output_register,
                args=args,
                kwargs=kwargs,
                task_name=node.definition.name,
                structure_hash=structure_hash,
            )
~~~~~
~~~~~python.new
        if node.meta.get("is_map"):
            instr = MapCall(
                output=output_register,
                args=args,
                kwargs=kwargs,
                task_name=node.definition.name,
                structure_hash=structure_hash,
                # Note: Constraints on Map nodes are not yet propagated to MapCall.
            )
        else:
            instr = Call(
                output=output_register,
                args=args,
                kwargs=kwargs,
                task_name=node.definition.name,
                structure_hash=structure_hash,
            )
~~~~~

#### Acts 3: Refactor `VMExecutionStrategy` to Delegate Linking

修改 `VMExecutionStrategy`，移除链接逻辑，并将 `symbol_table` 传递给 `VM`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
        # 4. Linking Phase: Resolve function pointers
        for instr in blueprint.instructions:
            if isinstance(instr, (Call, MapCall)):
                if instr.structure_hash not in symbol_table:
                    raise RuntimeError(
                        f"Linking failed: structure_hash '{instr.structure_hash}' "
                        f"for task '{instr.task_name}' not found in symbol table."
                    )
                instr.func = symbol_table[instr.structure_hash]

        # 5. Runtime: Execute Blueprint on VM
        # Note: The new VM doesn't yet support ResourceManager/ConstraintManager injection
        # directly in the same way. For Phase 5 initial integration, we instantiate the
        # pure VM. Future tasks will reintegrate resource management.
        vm = VirtualMachine()
        
        # Prepare initial arguments
        # The new VM expects 'initial_kwargs' mapping directly to registers if needed,
        # or it relies on the blueprint's structure.
        
        if isinstance(target, MappedLazyResult):
            initial_args = []
            initial_kwargs = dict(target.mapping_kwargs)
        else:
            initial_args = list(target.args)
            initial_kwargs = dict(target.kwargs)
        
        return await vm.execute(blueprint, initial_args=initial_args, initial_kwargs=initial_kwargs)
~~~~~
~~~~~python.new
        # 4. Runtime: Execute Blueprint on VM
        vm = VirtualMachine(
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            wakeup_event=self.wakeup_event,
        )

        if isinstance(target, MappedLazyResult):
            initial_args = []
            initial_kwargs = dict(target.mapping_kwargs)
        else:
            initial_args = list(target.args)
            initial_kwargs = dict(target.kwargs)
        
        return await vm.execute(
            blueprint,
            symbol_table=symbol_table,
            initial_args=initial_args,
            initial_kwargs=initial_kwargs,
        )
~~~~~

#### Acts 4: Refactor `VirtualMachine` to Perform Real-time Linking

修改 `VirtualMachine` 核心，使其在执行时动态查找函数。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python
import inspect
import asyncio
from typing import Any, List, Dict, Optional, Callable
from uuid import uuid4

from cascade.spec.blueprint import (
    Blueprint,
    Instruction,
    Call,
    MapCall,
    Literal,
    Register,
    Operand,
    TailCall,
    Jump,
    JumpIfFalse,
)
from cascade.spec.ir.models import TaskDef
from cascade.spec.fingerprint import Fingerprint
from cascade.graph.model import Node

# Use local protocols to avoid circular dependency with engine
from .protocols import ResourceManager, ConstraintManager


class Frame:
    """Represents the runtime stack frame for a blueprint execution."""

    def __init__(self, size: int):
        self.registers: List[Any] = [None] * size

    def load(self, operand: Operand) -> Any:
        """Loads a value from an operand (either a Literal or a Register)."""
        if isinstance(operand, Literal):
            return operand.value
        elif isinstance(operand, Register):
            if operand.index >= len(self.registers):
                raise IndexError(f"Invalid register index: {operand.index}")
            return self.registers[operand.index]
        else:
            raise TypeError(f"Unknown operand type: {type(operand)}")

    def store(self, register: Register, value: Any):
        """Stores a value into a register."""
        if register.index >= len(self.registers):
            raise IndexError(f"Invalid register index: {register.index}")
        self.registers[register.index] = value


class VirtualMachine:
    def __init__(
        self,
        resource_manager: Optional[ResourceManager] = None,
        constraint_manager: Optional[ConstraintManager] = None,
        wakeup_event: Optional[asyncio.Event] = None,
    ):
        self._blueprints: Dict[str, Blueprint] = {}
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.wakeup_event = wakeup_event

    def register_blueprint(self, bp_id: str, blueprint: Blueprint):
        self._blueprints[bp_id] = blueprint

    async def execute(
        self,
        blueprint: Blueprint,
        symbol_table: Dict[str, Callable],
        initial_args: Optional[List[Any]] = None,
        initial_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Any:
        current_blueprint = blueprint
        current_symbol_table = symbol_table

        frame = Frame(current_blueprint.register_count)
        self._load_inputs(
            frame, current_blueprint, initial_args or [], initial_kwargs or {}
        )

        while True:
            pc = 0
            instructions = current_blueprint.instructions
            last_result = None

            while pc < len(instructions):
                instr = instructions[pc]

                if isinstance(instr, Jump):
                    pc += instr.offset
                    continue

                if isinstance(instr, JumpIfFalse):
                    val = frame.load(instr.condition)
                    if not val:
                        pc += instr.offset
                    else:
                        pc += 1
                    continue

                last_result = await self._dispatch(instr, frame, current_symbol_table)
                pc += 1

            if isinstance(last_result, TailCall):
                if last_result.target_blueprint_id:
                    if last_result.target_blueprint_id not in self._blueprints:
                        raise ValueError(
                            f"Unknown target blueprint ID: {last_result.target_blueprint_id}"
                        )
                    current_blueprint = self._blueprints[
                        last_result.target_blueprint_id
                    ]
                    # NOTE: In a multi-blueprint world, we'd need a way to get the
                    # symbol table for the new blueprint. For now, we assume self-recursion.
                    frame = Frame(current_blueprint.register_count)

                self._load_inputs(
                    frame, current_blueprint, last_result.args, last_result.kwargs
                )
                await asyncio.sleep(0)
                continue

            return last_result

    def _load_inputs(
        self,
        frame: Frame,
        blueprint: Blueprint,
        args: List[Any],
        kwargs: Dict[str, Any],
    ):
        for i, val in enumerate(args):
            if i < len(blueprint.input_args):
                reg_index = blueprint.input_args[i]
                frame.registers[reg_index] = val

        for k, val in kwargs.items():
            if k in blueprint.input_kwargs:
                reg_index = blueprint.input_kwargs[k]
                frame.registers[reg_index] = val

    async def _dispatch(
        self, instr: Instruction, frame: Frame, symbol_table: Dict[str, Callable]
    ) -> Any:
        if isinstance(instr, Call):
            return await self._execute_call(instr, frame, symbol_table)
        elif isinstance(instr, MapCall):
            return await self._execute_map_call(instr, frame, symbol_table)
        else:
            raise NotImplementedError(f"Unknown instruction: {type(instr)}")

    async def _execute_map_call(
        self, instr: MapCall, frame: Frame, symbol_table: Dict[str, Callable]
    ) -> Any:
        func = symbol_table.get(instr.structure_hash)
        if func is None:
            raise RuntimeError(
                f"Linking failed: structure_hash '{instr.structure_hash}' "
                f"for task '{instr.task_name}' not found in symbol table."
            )
            
        loaded_kwargs = {k: frame.load(op) for k, op in instr.kwargs.items()}
        
        iterables = {}
        constants = {}
        iterable_len = -1

        for key, value in loaded_kwargs.items():
            if isinstance(value, list):
                iterables[key] = value
                if iterable_len == -1:
                    iterable_len = len(value)
                elif len(value) != iterable_len:
                    raise ValueError(f"Mismatched lengths in MapCall iterables for task '{instr.task_name}'")
            else:
                constants[key] = value

        if iterable_len == -1:
            iterable_len = 0

        calls_to_make = []
        for i in range(iterable_len):
            call_kwargs = constants.copy()
            for key, values_list in iterables.items():
                call_kwargs[key] = values_list[i]
            
            calls_to_make.append(func(**call_kwargs))

        if not calls_to_make:
            results = []
        elif inspect.iscoroutinefunction(func):
            results = await asyncio.gather(*calls_to_make)
        else:
            results = [res for res in calls_to_make]
            
        frame.store(instr.output, results)
        return results

    async def _execute_call(
        self, instr: Call, frame: Frame, symbol_table: Dict[str, Callable]
    ) -> Any:
        func = symbol_table.get(instr.structure_hash)
        if func is None:
            raise RuntimeError(
                f"Linking failed: structure_hash '{instr.structure_hash}' "
                f"for task '{instr.task_name}' not found in symbol table."
            )

        requirements: Dict[str, Any] = {}
        temp_node = None

        if self.constraint_manager or (
            instr.constraints and not instr.constraints.is_empty()
        ):
            stub_def = TaskDef(
                name=instr.task_name,
                args=[],
                fingerprint=Fingerprint(),
            )
            temp_node = Node(
                structural_id=str(uuid4()),
                definition=stub_def,
                node_type="task",
                constraints=instr.constraints,
            )

        if self.constraint_manager and temp_node:
            while not self.constraint_manager.check_permission(temp_node):
                if self.wakeup_event:
                    await self.wakeup_event.wait()
                    self.wakeup_event.clear()
                else:
                    await asyncio.sleep(0.1)

        if temp_node:
            if instr.constraints:
                requirements.update(instr.constraints.requirements)
            if self.constraint_manager:
                requirements.update(self.constraint_manager.get_extra_requirements(temp_node))

        if self.resource_manager and requirements:
            await self.resource_manager.acquire(requirements)

        try:
            args = [frame.load(op) for op in instr.args]
            kwargs = {k: frame.load(op) for k, op in instr.kwargs.items()}
            
            result = func(*args, **kwargs)
            if inspect.isawaitable(result):
                result = await result

            frame.store(instr.output, result)
            return result
        finally:
            if self.resource_manager and requirements:
                await self.resource_manager.release(requirements)
~~~~~

#### Acts 5: Fix `test_vm_linking`

最后，我们修复 `test_vm_linking.py`，使其验证新的、正确的端到端链接和执行流程。

~~~~~act
write_file
packages/cascade-engine/tests/integration/test_vm_linking.py
~~~~~
~~~~~python
import pytest
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus
import cascade as cs

@pytest.mark.asyncio
async def test_vm_strategy_delegates_linking_to_vm_and_executes():
    """
    End-to-end integration test for the new purified architecture:
    1. Frontend compiles workflow -> CompilationResult(ir, symbol_table).
    2. Backend compiles ir -> Blueprint (with structure_hash, func is gone).
    3. VMExecutionStrategy passes Blueprint + symbol_table to the VM.
    4. VM executes, looking up functions via structure_hash in real-time.
    """
    @cs.task
    def echo(x):
        return x

    workflow = echo("hello_world")
    
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),  # Still needed for GraphStrategy, though not used by VMStrategy
        bus=MessageBus(),
    )
    
    # Run with VM enabled.
    # If linking fails inside the VM, it will raise a RuntimeError.
    # If the `func` field was expected anywhere, it would raise an AttributeError or TypeError.
    result = await engine.run(workflow, use_vm=True)
    
    assert result == "hello_world"
~~~~~

### 下一步建议
我们已经完成了对 `Blueprint` 的净化和 `VirtualMachine` 链接逻辑的重构。这是“架构硬化”任务的最后一步。

现在，我们必须进行一次全面的回归测试，以确保这个重大变更没有破坏任何现有功能。我建议运行整个项目的所有测试：

`pytest`
