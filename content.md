简要回答：
根据错误日志分析，我们正处于预期的 **RED** 状态。主要问题集中在 Spec 缺失字段、Compiler 未生成符号表以及 Engine 缺少链接逻辑。

我将按照路线图分阶段修复这些问题，使测试变绿。

## [WIP] feat: 实现基于 structure_hash 的安全链接机制 (GREEN 阶段)

### 用户需求
完成 Compiler-Runtime 架构中的“安全链接”环节。确保编译器生成的指令包含结构哈希，并且运行时能利用此哈希将指令正确链接到内存中的函数对象。

### 评论
本次修改涉及三个核心包的协同变更：
1.  **Spec**: 扩展 `Blueprint` 指令集以携带哈希，并定义 `CompilationResult` 契约。
2.  **Compiler**: 前端负责提取符号表（Symbol Table），后端负责将哈希嵌入指令。
3.  **Engine**: 运行时策略负责“链接”过程，即用符号表填充指令中的 `func` 指针。

### 目标
1.  修复 `cascade-spec`，增加 `structure_hash` 字段和 `CompilationResult` 类。
2.  修复 `cascade-compiler`，使其产出符合新契约的编译结果。
3.  修复 `cascade-engine`，实现链接逻辑并修复 `MappedLazyResult` 的初始化参数问题。
4.  通过所有相关测试。

### 基本原理
我们通过将“函数引用”从编译期解耦（仅保留哈希），推迟到运行期绑定（链接），实现了可序列化、可缓存的中间表示（IR）和字节码（Blueprint）。这是实现跨进程/跨语言执行和高级缓存的基础。

### 标签
#intent/build #flow/ready #priority/high #comp/spec #comp/compiler #comp/runtime #task/domain/core #task/object/linking #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: Spec 增强 - 定义数据契约

首先，我们需要修改 `Blueprint` 指令以包含 `structure_hash`，并定义用于传递编译结果的新结构。

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


@dataclass
class Jump(Instruction):
~~~~~
~~~~~python.new
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


@dataclass
class Jump(Instruction):
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


@dataclass
class TailCall:
~~~~~
~~~~~python.new
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


@dataclass
class TailCall:
~~~~~

~~~~~act
write_file
packages/cascade-spec/src/cascade/spec/compiler_result.py
~~~~~
~~~~~python
from dataclasses import dataclass
from typing import Dict, Callable, Any
from cascade.spec.ir.models import GraphIR


@dataclass
class CompilationResult:
    """
    Container for the output of the Compiler Frontend.
    
    Attributes:
        ir: The Intermediate Representation of the compute graph.
        symbol_table: A mapping from structure_hash to the actual callable object.
                      This is used by the runtime to link instructions to code.
    """
    ir: GraphIR
    symbol_table: Dict[str, Callable[..., Any]]
~~~~~

#### Acts 2: Compiler 实现 - 生成链接信息

修改前端以收集符号表，修改后端以填充哈希。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python.old
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, EdgeKind
from cascade.graph.analysis.reflection import ReflectionAnalyzer
from cascade.graph.hashing import HashingService
~~~~~
~~~~~python.new
from typing import Any, Dict, List, cast, Callable
from dataclasses import dataclass

from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, EdgeKind
from cascade.spec.compiler_result import CompilationResult
from cascade.graph.analysis.reflection import ReflectionAnalyzer
from cascade.graph.hashing import HashingService
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python.old
class Frontend:
    """
    Compiler Frontend: Transforms user-facing LazyResults into Intermediate Representation (GraphIR).
    """

    @staticmethod
    def compile(target: Any) -> GraphIR:
        builder = _GraphBuilder()
        return builder.build(target)


class _GraphBuilder:
    def __init__(self):
        self.nodes: Dict[str, NodeIR] = {}  # Map structural_id -> NodeIR
        self.edges: List[EdgeIR] = []
        self._visited_lazy_uuids: Dict[str, str] = {}  # Map LazyResult.uuid -> structural_id

        # Services from cascade-graph (reused for stability)
        self.analyzer = ReflectionAnalyzer()
        self.hashing_service = HashingService()

    def build(self, target: Any) -> GraphIR:
        self._visit(target)
        return GraphIR(nodes=list(self.nodes.values()), edges=self.edges)

    def _visit(self, obj: Any) -> str:
        """
        Visits a LazyResult type, creating NodeIRs and EdgeIRs.
~~~~~
~~~~~python.new
class Frontend:
    """
    Compiler Frontend: Transforms user-facing LazyResults into Intermediate Representation (GraphIR).
    """

    @staticmethod
    def compile(target: Any) -> CompilationResult:
        builder = _GraphBuilder()
        return builder.build(target)


class _GraphBuilder:
    def __init__(self):
        self.nodes: Dict[str, NodeIR] = {}  # Map structural_id -> NodeIR
        self.edges: List[EdgeIR] = []
        self.symbol_table: Dict[str, Callable] = {}
        self._visited_lazy_uuids: Dict[str, str] = {}  # Map LazyResult.uuid -> structural_id

        # Services from cascade-graph (reused for stability)
        self.analyzer = ReflectionAnalyzer()
        self.hashing_service = HashingService()

    def build(self, target: Any) -> CompilationResult:
        self._visit(target)
        graph = GraphIR(nodes=list(self.nodes.values()), edges=self.edges)
        return CompilationResult(ir=graph, symbol_table=self.symbol_table)

    def _visit(self, obj: Any) -> str:
        """
        Visits a LazyResult type, creating NodeIRs and EdgeIRs.
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python.old
        task_def = self.analyzer.analyze(obj.task)
        node_id = self.hashing_service.compute_node_instance_hash(
            task_def, obj, cast(Dict[str, Any], dep_shims)
        )

        if node_id not in self.nodes:
~~~~~
~~~~~python.new
        task_def = self.analyzer.analyze(obj.task)
        
        # Populate Symbol Table
        code_hash = task_def.fingerprint["current_code_structure_hash"]
        self.symbol_table[code_hash] = obj.task.func

        node_id = self.hashing_service.compute_node_instance_hash(
            task_def, obj, cast(Dict[str, Any], dep_shims)
        )

        if node_id not in self.nodes:
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python.old
        task_def = self.analyzer.analyze(obj.factory)
        node_id = self.hashing_service.compute_node_instance_hash(
            task_def, obj, cast(Dict[str, Any], dep_shims)
        )

        if node_id not in self.nodes:
~~~~~
~~~~~python.new
        task_def = self.analyzer.analyze(obj.factory)

        # Populate Symbol Table
        code_hash = task_def.fingerprint["current_code_structure_hash"]
        self.symbol_table[code_hash] = obj.factory

        node_id = self.hashing_service.compute_node_instance_hash(
            task_def, obj, cast(Dict[str, Any], dep_shims)
        )

        if node_id not in self.nodes:
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
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
~~~~~python.new
        # We also pass task name for better observability in the VM
        structure_hash = node.definition.fingerprint["current_code_structure_hash"]

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
        self._instructions.append(instr)
~~~~~

#### Acts 3: Engine 实现 - 执行链接

修改 `VMExecutionStrategy` 以使用新的 `CompilationResult` 并执行链接。同时修复 `MappedLazyResult` 在初始化时的参数提取问题。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
# New Compiler Stack
from cascade.compiler.frontend import Frontend
from cascade.compiler.optimizer import Optimizer
from cascade.compiler.backend import Backend
from cascade.vm import VirtualMachine


class VMExecutionStrategy:
    def __init__(
        self,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
        wakeup_event: asyncio.Event,
    ):
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.wakeup_event = wakeup_event

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        # 1. Frontend: Compile LazyResult to GraphIR
        graph_ir = Frontend.compile(target)

        # 2. Optimizer: Schedule GraphIR to ExecutionPlan
        execution_plan = Optimizer.optimize(graph_ir)

        # 3. Backend: Generate Blueprint from GraphIR + ExecutionPlan
        blueprint = Backend.compile(graph_ir, execution_plan)

        # 4. Runtime: Execute Blueprint on VM
        # Note: The new VM doesn't yet support ResourceManager/ConstraintManager injection
        # directly in the same way. For Phase 5 initial integration, we instantiate the
        # pure VM. Future tasks will reintegrate resource management.
        vm = VirtualMachine()
        
        # Prepare initial arguments
        # The new VM expects 'initial_kwargs' mapping directly to registers if needed,
        # or it relies on the blueprint's structure.
        # For now, we assume the Blueprint structure handles defaults, but we need to pass
        # the runtime parameters if any.
        
        # Extract args/kwargs from target LazyResult for the root call
        initial_args = list(target.args)
        initial_kwargs = dict(target.kwargs)
        
        return await vm.execute(blueprint, initial_args=initial_args, initial_kwargs=initial_kwargs)
~~~~~
~~~~~python.new
# New Compiler Stack
from cascade.compiler.frontend import Frontend
from cascade.compiler.optimizer import Optimizer
from cascade.compiler.backend import Backend
from cascade.vm import VirtualMachine
from cascade.spec.lazy_types import MappedLazyResult
from cascade.spec.blueprint import Call, MapCall


class VMExecutionStrategy:
    def __init__(
        self,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
        wakeup_event: asyncio.Event,
    ):
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.wakeup_event = wakeup_event

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        # 1. Frontend: Compile LazyResult to GraphIR
        # Returns CompilationResult(ir, symbol_table)
        compilation_result = Frontend.compile(target)
        graph_ir = compilation_result.ir
        symbol_table = compilation_result.symbol_table

        # 2. Optimizer: Schedule GraphIR to ExecutionPlan
        execution_plan = Optimizer.optimize(graph_ir)

        # 3. Backend: Generate Blueprint from GraphIR + ExecutionPlan
        blueprint = Backend.compile(graph_ir, execution_plan)

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

### 下一步建议
现在 Spec、Compiler 和 Engine 已经协同工作，支持基于 `structure_hash` 的链接。`VMExecutionStrategy` 会在执行前进行链接检查，确保所有指令都有可调用的函数实现。

接下来，我们将运行测试以验证修复。如果测试通过，我们将进行后续的“Map/Reduce 对齐”和“控制流对齐”工作。
