import pytest

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
