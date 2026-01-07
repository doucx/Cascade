简要回答
已实现。通过增强 `EventDrivenRunner`，增加了 `from_assembly` 类方法，使其在初始化阶段强制调用 `Linker` 进行完整性校验，从而杜绝了“代码缺失却能启动”的盲目乐观问题。

## [WIP] feat(vm): 强制执行 Linker 校验以防止运行时代码缺失

### 用户需求
实现一个强制性的校验步骤，在 `Machine.run()` 之前确保 `Assembly` 中引用的所有 `canonical_hash` 在 `CodeRegistry` 中都具备可执行的实现。

### 评论
这是一个关键的稳定性增强。之前系统允许在 `CodeRegistry` 缺失实现的情况下启动，直到运行时 `Dispatcher` 尝试分发任务时才崩溃。这种“盲目乐观”导致错误发现延迟。通过在 `EventDrivenRunner` 中集成 `Linker`，我们将检查前移到了启动阶段 (Fail Fast)。

### 目标
1.  创建一个测试用例 `test_linker_validation.py`，复现“盲目乐观”缺陷，并验证新的校验机制。
2.  在 `EventDrivenRunner` 中添加 `from_assembly` 工厂方法，作为推荐的初始化路径，该方法强制调用 `Linker.link()`。
3.  确保 `Linker` 能正确识别所有标准库节点和用户节点，并验证哈希完整性。

### 基本原理
`Machine` 是运行时的核心，不应承担静态链接检查的职责。`EventDrivenRunner` 作为测试和启动 Harness，是执行组装和校验的最佳位置。通过提供 `from_assembly`，我们封装了“Assembly + Registry -> Function Map”的复杂逻辑，并确保了 `Linker` 的校验逻辑不会被绕过。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/linking #scope/core #ai/instruct #task/domain/vm #task/object/linker #task/action/integration #task/state/begin

---

### Script

#### Acts 1: 创建复现“盲目乐观”缺陷的测试

我们将创建一个测试，演示在当前模式下，即使 `CodeRegistry` 缺少代码实现，系统也能启动，直到运行时才崩溃。同时验证 Linker 的有效性。

~~~~~act
write_file
packages/cascade-vm/tests/integration/test_linker_validation.py
~~~~~
~~~~~python
import pytest
from cascade.spec.dsl.task import task
from cascade.compiler.frontend import IRGenerator
from cascade.compiler.backend import Builder
from cascade.spec.physical.environment import EnvironmentDef
from cascade.vm.harness import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
from cascade.vm.linker import Linker, LinkerError

# Standard library function imports for manual wiring (simulating current behavior)
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher


@task
def missing_task():
    return "I do not exist"


@pytest.mark.asyncio
async def test_blind_optimism_without_linker():
    """
    Demonstrates that without the Linker, the VM starts even if code is missing,
    leading to a runtime failure (or "blind optimism").
    """
    # 1. Compile
    workflow = missing_task()
    ir_generator = IRGenerator()
    builder = Builder()
    graph_ir = ir_generator.generate(workflow)
    artifact = builder.build(graph_ir, EnvironmentDef())
    assembly = artifact.assembly

    # 2. Setup Empty Registry (INTENTIONALLY MISSING CODE)
    code_registry = CodeRegistry()
    # We do NOT register missing_task here.

    # 3. Manual Wiring (The "Old Way")
    # This bypasses any integrity checks.
    func_map = {}
    for node_id in assembly.graph.nodes:
        if node_id.endswith(".bleach"):
            func_map[node_id] = standard_bleacher
        elif node_id.endswith(".stain"):
            func_map[node_id] = standard_stainer
        elif node_id.endswith(".worker"):
            func_map[node_id] = standard_dispatcher
        elif "observer" in node_id:
            func_map[node_id] = standard_observer

    # 4. Initialize Runner
    # This should succeed currently, which is the problem.
    runner = EventDrivenRunner(assembly.graph, func_map, code_registry)
    runner.prime()

    # 5. Run
    # It will fail at runtime when Dispatcher tries to find the code hash,
    # or when ComputeService tries to load it.
    await runner.start_loop()
    try:
        # We expect it to timeout or fail, but NOT raise LinkerError at startup.
        # For this test, we just assert that we reached this point without error.
        assert True
    finally:
        await runner.stop_loop()


@pytest.mark.asyncio
async def test_linker_enforces_integrity():
    """
    Demonstrates that the Linker correctly identifies missing code and prevents startup.
    """
    # 1. Compile
    workflow = missing_task()
    ir_generator = IRGenerator()
    builder = Builder()
    graph_ir = ir_generator.generate(workflow)
    artifact = builder.build(graph_ir, EnvironmentDef())
    assembly = artifact.assembly

    # 2. Setup Empty Registry
    code_registry = CodeRegistry()

    # 3. Use Linker
    linker = Linker()

    # 4. Assert LinkerError
    with pytest.raises(LinkerError) as excinfo:
        linker.link(assembly, code_registry)

    assert "integrity check failed" in str(excinfo.value)
~~~~~

#### Acts 2: 增强 EventDrivenRunner 以支持 Assembly 驱动的初始化

我们将修改 `EventDrivenRunner`，添加 `from_assembly` 类方法。这将成为启动 VM 的推荐方式，它会在内部强制调用 `Linker` 进行校验。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
from cascade.vm.compute import ComputeRequest, LocalComputeService
from cascade.vm.registry import CodeRegistry

logger = logging.getLogger(__name__)

T = TypeVar("T")
~~~~~
~~~~~python.new
from cascade.vm.compute import ComputeRequest, LocalComputeService
from cascade.vm.registry import CodeRegistry
from cascade.vm.linker import Linker
from cascade.spec.physical.assembly import Assembly

logger = logging.getLogger(__name__)

T = TypeVar("T")
~~~~~

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/harness.py
~~~~~
~~~~~python.old
class EventDrivenRunner:
    def __init__(
        self,
        graph: BipartiteGraph,
        function_map: Dict[str, Callable],
        code_registry: CodeRegistry,
        reactor_factory: Optional[Callable[..., ReactorProtocol]] = None,
    ):
        self.graph = graph
        self.memory = VolatileMemory()
~~~~~
~~~~~python.new
class EventDrivenRunner:
    @classmethod
    def from_assembly(
        cls,
        assembly: Assembly,
        code_registry: CodeRegistry,
        reactor_factory: Optional[Callable[..., ReactorProtocol]] = None,
    ) -> "EventDrivenRunner":
        """
        Creates an EventDrivenRunner from a compiled Assembly.
        This method automatically runs the Linker to verify integrity and build the function map.
        """
        linker = Linker()
        # This will raise LinkerError if code_registry is missing required hashes
        function_map = linker.link(assembly, code_registry)
        return cls(assembly.graph, function_map, code_registry, reactor_factory)

    def __init__(
        self,
        graph: BipartiteGraph,
        function_map: Dict[str, Callable],
        code_registry: CodeRegistry,
        reactor_factory: Optional[Callable[..., ReactorProtocol]] = None,
    ):
        self.graph = graph
        self.memory = VolatileMemory()
~~~~~

#### Acts 3: 验证新的强制校验机制

现在我们更新 `test_linker_validation.py`，增加一个测试用例来验证 `EventDrivenRunner.from_assembly` 确实阻止了不完整的系统启动。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_linker_validation.py
~~~~~
~~~~~python.old
    # 4. Assert LinkerError
    with pytest.raises(LinkerError) as excinfo:
        linker.link(assembly, code_registry)

    assert "integrity check failed" in str(excinfo.value)
~~~~~
~~~~~python.new
    # 4. Assert LinkerError
    with pytest.raises(LinkerError) as excinfo:
        linker.link(assembly, code_registry)

    assert "integrity check failed" in str(excinfo.value)


@pytest.mark.asyncio
async def test_runner_from_assembly_enforces_linker():
    """
    Demonstrates that using EventDrivenRunner.from_assembly() creates a safe, validated runtime.
    """
    # 1. Compile
    workflow = missing_task()
    ir_generator = IRGenerator()
    builder = Builder()
    graph_ir = ir_generator.generate(workflow)
    artifact = builder.build(graph_ir, EnvironmentDef())
    assembly = artifact.assembly

    # 2. Setup Empty Registry
    code_registry = CodeRegistry()

    # 3. Assert Initialization Failure
    # Attempting to create the runner should fail immediately
    with pytest.raises(LinkerError) as excinfo:
        EventDrivenRunner.from_assembly(assembly, code_registry)

    assert "integrity check failed" in str(excinfo.value)
~~~~~

### 下一步建议

1.  **迁移测试**: 逐步将现有的集成测试（如 `test_ref_architecture.py`）迁移到使用 `EventDrivenRunner.from_assembly`，以消除手动构建 `func_map` 的冗余代码，并享受自动校验的好处。
2.  **VM 增强**: 接下来应着手解决战略分析中的另一个问题：引入 `Error Token` 和 `Halt Signal`，让 Machine 的停止由明确的信号驱动，而非由“空闲”驱动。这将解决“假死”问题。
