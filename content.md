好的，我们来完成 **Phase 6** 的核心实现，让测试恢复绿色状态。

我们将分三步走：
1.  **Spec**: 在 `blueprint.py` 中正式定义 `MapCall` 指令。
2.  **Compiler**: 修改 `backend.py`，使其在遇到 `is_map` 标记时生成 `MapCall` 指令。
3.  **VM**: 修改 `machine.py`，实现 `MapCall` 的执行逻辑，包括处理并行异步任务。

## [WIP] feat(compiler+vm): Implement MapCall instruction and execution

### 用户需求
1.  在 Spec 中定义 `MapCall` 指令。
2.  更新 Compiler Backend 以生成 `MapCall` 指令。
3.  更新 Virtual Machine 以执行 `MapCall` 指令。

### 评论
这是功能对齐的关键一步。`MapCall` 将 `map` 操作从一个普通的图节点，提升为 VM 的一等公民指令。这使得 VM 能够对数据并行工作流进行专门的优化和调度（例如，使用 `asyncio.gather` 并发执行），从而释放了 Cascade 的核心性能优势。

### 目标
让 `test_backend.py` 和 `test_vm_map.py` 中的所有测试通过，使 `compiler` 和 `vm` 包的测试套件恢复 GREEN 状态。

### 基本原理
我们通过扩展指令集（Spec），让 Compiler (`Backend`) 能够向 VM 传达更高层次的意图（“这是一个 map 操作”）。VM 接收到这个 `MapCall` 指令后，执行一个内置的、优化的循环来处理迭代、并发和结果收集，而不是让用户在图层面手动展开循环。

### 标签
#intent/build #flow/ready #priority/high #comp/spec #comp/compiler #comp/vm #concept/codegen #concept/vm #task/domain/core #task/object/map-execution #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 在 Spec 中定义 `MapCall` 指令

我们在 `blueprint.py` 中添加 `MapCall`，使其与 `Call` 具有相似的结构，因为它同样代表一个可执行的操作。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/blueprint.py
~~~~~
~~~~~python.old
@dataclass
class JumpIfFalse(Instruction):
    """Jumps execution by a relative offset if the condition register is False."""

    condition: Register
    offset: int


@dataclass
class TailCall:
~~~~~
~~~~~python.new
@dataclass
class JumpIfFalse(Instruction):
    """Jumps execution by a relative offset if the condition register is False."""

    condition: Register
    offset: int


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


@dataclass
class TailCall:
~~~~~

#### Acts 2: 更新 Compiler Backend 以生成 `MapCall`

我们修改 `_process_node` 方法，使其根据 `node.meta` 的 `is_map` 标志来决定是生成 `Call` 还是 `MapCall` 指令。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
from typing import List, Dict, Tuple, Any

from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, EdgeKind
from cascade.spec.blueprint import Blueprint, Call, Register, Literal, Operand, JumpIfFalse
from .optimizer import ExecutionPlan
~~~~~
~~~~~python.new
from typing import List, Dict, Tuple, Any

from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, EdgeKind
from cascade.spec.blueprint import Blueprint, Call, MapCall, Register, Literal, Operand, JumpIfFalse
from .optimizer import ExecutionPlan
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
        # We also pass task name for better observability in the VM
        instr = Call(
            func=None,  # The VM will need to resolve this later
            output=output_register,
            args=args,
            kwargs=kwargs,
            task_name=node.definition.name
        )
        self._instructions.append(instr)
~~~~~
~~~~~python.new
        # We also pass task name for better observability in the VM
        if node.meta.get("is_map"):
            instr = MapCall(
                func=None,
                output=output_register,
                args=args,
                kwargs=kwargs,
                task_name=node.definition.name,
                # Note: Constraints on Map nodes are not yet propagated to MapCall.
            )
        else:
            instr = Call(
                func=None,  # The VM will need to resolve this later
                output=output_register,
                args=args,
                kwargs=kwargs,
                task_name=node.definition.name
            )
        self._instructions.append(instr)
~~~~~

#### Acts 3: 更新 VM 以执行 `MapCall`

这是核心实现。我们在 `machine.py` 中添加 `MapCall` 的处理逻辑，包括并发执行异步任务。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
from cascade.spec.blueprint import (
    Blueprint,
    Instruction,
    Call,
    Literal,
    Register,
    Operand,
    TailCall,
    Jump,
    JumpIfFalse,
)
from cascade.spec.ir.models import TaskDef
~~~~~
~~~~~python.new
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
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
    async def _dispatch(self, instr: Instruction, frame: Frame) -> Any:
        if isinstance(instr, Call):
            return await self._execute_call(instr, frame)
        else:
            raise NotImplementedError(f"Unknown instruction: {type(instr)}")

    async def _execute_call(self, instr: Call, frame: Frame) -> Any:
        requirements: Dict[str, Any] = {}
        temp_node = None
~~~~~
~~~~~python.new
    async def _dispatch(self, instr: Instruction, frame: Frame) -> Any:
        if isinstance(instr, Call):
            return await self._execute_call(instr, frame)
        elif isinstance(instr, MapCall):
            return await self._execute_map_call(instr, frame)
        else:
            raise NotImplementedError(f"Unknown instruction: {type(instr)}")

    async def _execute_map_call(self, instr: MapCall, frame: Frame) -> Any:
        # 1. Load all arguments from frame
        loaded_kwargs = {k: frame.load(op) for k, op in instr.kwargs.items()}
        
        # 2. Separate iterables from constants
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

        if iterable_len == -1: # No iterables found, treat as empty map
            iterable_len = 0

        # 3. Prepare individual calls
        calls_to_make = []
        for i in range(iterable_len):
            call_kwargs = constants.copy()
            for key, values_list in iterables.items():
                call_kwargs[key] = values_list[i]
            
            calls_to_make.append(instr.func(**call_kwargs))

        # 4. Execute calls concurrently if async, sequentially otherwise
        if not calls_to_make:
            results = []
        elif inspect.iscoroutinefunction(instr.func):
            results = await asyncio.gather(*calls_to_make)
        else:
            results = [res for res in calls_to_make]
            
        # 5. Store result and return
        frame.store(instr.output, results)
        return results

    async def _execute_call(self, instr: Call, frame: Frame) -> Any:
        requirements: Dict[str, Any] = {}
        temp_node = None
~~~~~

### 下一步建议
我们已经完成了 `map` 和 `run_if` 在新架构中的核心实现和单元测试。现在最大的缺口是 `VMExecutionStrategy` 和 VM 之间的**函数解析**。

`Backend` 生成的 `Blueprint` 中的 `func` 字段是 `None`，而 VM 依赖它。我们需要在 `VMExecutionStrategy` 中实现一个“链接 (Linking)”阶段：在从 `Backend` 拿到 `Blueprint` 之后，遍历 `LazyResult` 图，构建一个 `(task_name -> callable)` 的映射表，然后用它来填充 `Blueprint` 中所有指令的 `func` 字段。

这需要我们修改 `VMExecutionStrategy`，并编写一个新的**集成测试**来验证整个流程。
