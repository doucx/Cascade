好的，我们将开始执行 **Phase 3.2: 链接器增强**。

此计划的核心是赋予 `Linker` 验证职责，使其成为 VM 启动前的一道“防火墙”。通过在链接时强制进行完整性校验，我们能将潜在的、难以调试的运行时 `KeyError`（因函数未注册）转变为一个清晰的、在启动阶段就发生的 `LinkerError`。

[简要回答]
我将立即实施 Phase 3.2。此计划将修改 `Linker`，使其在生成函数映射前，强制验证 `Assembly` 所需的每一个函数都在 `CodeRegistry` 中存在。如果校验失败，将抛出一个明确的 `LinkerError`。我还将创建新的单元测试来锁定这一关键行为。

## [WIP] feat(vm): 在 Linker 中实现启动前完整性校验

### 用户需求
VM 不应在缺少必要函数实现的情况下启动。`Linker` 需要一个强制性的验证步骤，以确保 `Assembly` 中 `symbol_table` 引用的所有 `canonical_code_structure_hash` 都在 `CodeRegistry` 中有对应的函数实现。

### 评论
这是一个典型的“快速失败”(Fail-Fast)设计模式。通过在系统启动的最早阶段捕获配置错误，我们极大地提高了系统的健壮性和可调试性。这个改动将“代码未找到”的错误从一个不确定的运行时事件，转变为一个确定性的链接时错误。

### 目标
1.  在 `linker.py` 中定义一个新的异常类型 `LinkerError`。
2.  修改 `Linker.link` 方法，增加完整性校验逻辑。
3.  如果发现任何代码哈希缺失，`Linker.link` 必须抛出 `LinkerError`，并在错误消息中列出所有缺失的哈希。
4.  创建一个新的测试文件 `tests/unit/test_linker.py`。
5.  在新测试文件中，添加用例以验证校验成功和失败（抛出异常）两种情况。

### 基本原理
`Linker` 是连接静态编译产物 (`Assembly`) 和动态运行时环境 (`CodeRegistry`) 的唯一桥梁。因此，它是执行这种契约验证最理想、最权威的位置。强制校验将确保 Reactor 在接收到 `function_map` 时，该映射是完全可信且完整的。

### 标签
#intent/build #flow/ready #priority/high
#comp/engine #scope/core
#task/domain/vm #task/object/linker #task/action/validation
#task/state/continue

---

### Script

#### Acts 1: 增强 Linker 并定义 LinkerError

我们首先修改 `linker.py`，加入新的异常类和验证逻辑。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/linker.py
~~~~~
~~~~~python.old
from typing import Dict, Callable, Optional

from cascade.spec.physical.assembly import Assembly
from cascade.spec.physical.nodes import PhysicsFuncNode
from cascade.reflection import PhysicalIdGenerator

from .registry import CodeRegistry

# Standard Library Imports (Micro-Kernel)
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.system.egress import standard_egress


class Linker:
    def link(self, assembly: Assembly, registry: CodeRegistry) -> Dict[str, Callable]:
        function_map: Dict[str, Callable] = {}

        for node_id, node in assembly.graph.nodes.items():
            if not isinstance(node, PhysicsFuncNode):
                continue

            # 1. User Worker Nodes (via Symbol Table)
            # All user workers are now implemented by the standard_dispatcher.
            if node_id in assembly.symbol_table:
                function_map[node_id] = standard_dispatcher
                continue

            # 2. Standard Library Nodes (via ID Heuristics)
            stdlib_func = self._resolve_stdlib(node_id)
            if stdlib_func:
                function_map[node_id] = stdlib_func
                continue

        return function_map
~~~~~
~~~~~python.new
from typing import Dict, Callable, Optional

from cascade.spec.physical.assembly import Assembly
from cascade.spec.physical.nodes import PhysicsFuncNode
from cascade.reflection import PhysicalIdGenerator

from .registry import CodeRegistry

# Standard Library Imports (Micro-Kernel)
from cascade.std.triad.bleacher import standard_bleacher
from cascade.std.triad.stainer import standard_stainer
from cascade.std.triad.observer import standard_observer
from cascade.std.triad.dispatcher import standard_dispatcher
from cascade.std.resource.discrete import discrete_allocator, discrete_reclaimer
from cascade.std.resource.requestor import resource_requestor
from cascade.std.system.egress import standard_egress


class LinkerError(RuntimeError):
    """Raised when linking fails due to missing code implementations."""

    pass


class Linker:
    def link(self, assembly: Assembly, registry: CodeRegistry) -> Dict[str, Callable]:
        # Phase 1: Integrity Validation
        self._verify_integrity(assembly, registry)

        # Phase 2: Function Mapping
        function_map: Dict[str, Callable] = {}

        for node_id, node in assembly.graph.nodes.items():
            if not isinstance(node, PhysicsFuncNode):
                continue

            # 1. User Worker Nodes (via Symbol Table)
            # All user workers are now implemented by the standard_dispatcher.
            if node_id in assembly.symbol_table:
                function_map[node_id] = standard_dispatcher
                continue

            # 2. Standard Library Nodes (via ID Heuristics)
            stdlib_func = self._resolve_stdlib(node_id)
            if stdlib_func:
                function_map[node_id] = stdlib_func
                continue

        return function_map

    def _verify_integrity(self, assembly: Assembly, registry: CodeRegistry) -> None:
        """Ensures all required code hashes in the assembly exist in the registry."""
        missing_hashes = {
            code_hash
            for code_hash in assembly.symbol_table.values()
            if not registry.has(code_hash)
        }

        if missing_hashes:
            missing_list = "\n - ".join(sorted(list(missing_hashes)))
            raise LinkerError(
                f"Linker integrity check failed. The following code hashes "
                f"are required by the assembly but were not found in the CodeRegistry:\n"
                f" - {missing_list}"
            )
~~~~~

#### Acts 2: 创建 Linker 的单元测试

由于 `Linker` 目前没有专门的测试文件，我们将创建一个，并添加验证新行为的用例。

~~~~~act
write_file
packages/cascade-vm/tests/unit/test_linker.py
~~~~~
~~~~~python
import pytest
from typing import Callable, Dict

from cascade.spec.physical.assembly import Assembly, SymbolTable
from cascade.spec.physical.topology import BipartiteGraph
from cascade.spec.physical.triad import WorkerNode
from cascade.vm.registry import CodeRegistry
from cascade.vm.linker import Linker, LinkerError
from cascade.std.triad.dispatcher import standard_dispatcher


def dummy_task_a():
    pass


def dummy_task_b():
    pass


@pytest.fixture
def code_registry() -> CodeRegistry:
    registry = CodeRegistry()
    registry.register("hash_a", dummy_task_a)
    registry.register("hash_b", dummy_task_b)
    return registry


@pytest.fixture
def assembly() -> Assembly:
    graph = BipartiteGraph()
    # We only need worker nodes for this test, as only they populate the symbol table
    graph.nodes["worker1.worker"] = WorkerNode(
        id="worker1.worker", name="Worker1", canonical_code_structure_hash="hash_a"
    )
    graph.nodes["worker2.worker"] = WorkerNode(
        id="worker2.worker", name="Worker2", canonical_code_structure_hash="hash_b"
    )
    symbol_table: SymbolTable = {
        "worker1.worker": "hash_a",
        "worker2.worker": "hash_b",
    }
    return Assembly(graph=graph, symbol_table=symbol_table)


def test_linker_success_with_all_code_present(assembly, code_registry):
    linker = Linker()
    function_map = linker.link(assembly, code_registry)

    # All workers should be mapped to the standard_dispatcher
    assert len(function_map) == 2
    assert function_map["worker1.worker"] is standard_dispatcher
    assert function_map["worker2.worker"] is standard_dispatcher


def test_linker_raises_on_missing_code(assembly, code_registry):
    linker = Linker()

    # Tamper with the assembly to require a hash that doesn't exist
    assembly.symbol_table["worker3.worker"] = "hash_c_missing"

    with pytest.raises(LinkerError) as exc_info:
        linker.link(assembly, code_registry)

    # Verify the error message is informative
    assert "Linker integrity check failed" in str(exc_info.value)
    assert "hash_c_missing" in str(exc_info.value)


def test_linker_raises_on_multiple_missing_codes():
    linker = Linker()
    registry = CodeRegistry()  # Empty registry
    assembly = Assembly(
        graph=BipartiteGraph(),
        symbol_table={
            "w1.worker": "hash_1",
            "w2.worker": "hash_2",
        },
    )

    with pytest.raises(LinkerError) as exc_info:
        linker.link(assembly, registry)

    error_str = str(exc_info.value)
    assert "hash_1" in error_str
    assert "hash_2" in error_str
~~~~~

### 下一步建议
我们已经为 `Linker` 建立了强制性的启动前校验。这为我们进入下一阶段铺平了道路。

下一步，我们将执行 **Phase 3.3: VM 增强**。我们将引入 `SystemControlToken` 和明确的信号，以取代当前基于“空闲检测”的脆弱停止机制，让 `Machine` 的生命周期由信号驱动。
