import pytest

from cascade.spec.physical.assembly import Assembly, SymbolTable
from cascade.spec.physical.topology import BipartiteGraph
from cascade.spec.physical.dyad import LauncherNode
from cascade.vm.registry import CodeRegistry
from cascade.vm.linker import Linker, LinkerError
from cascade.std.dyad.launcher import standard_launcher


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
    # In Dyad, Launcher nodes populate the symbol table and map to standard_launcher
    graph.nodes["node1.launch"] = LauncherNode(
        id="node1.launch", name="Launch1", canonical_code_structure_hash="hash_a"
    )
    graph.nodes["node2.launch"] = LauncherNode(
        id="node2.launch", name="Launch2", canonical_code_structure_hash="hash_b"
    )
    symbol_table: SymbolTable = {
        "node1.launch": "hash_a",
        "node2.launch": "hash_b",
    }
    return Assembly(graph=graph, symbol_table=symbol_table)


def test_linker_success_with_all_code_present(assembly, code_registry):
    linker = Linker()
    function_map = linker.link(assembly, code_registry)

    # All launchers should be mapped to the standard_launcher
    assert len(function_map) == 2
    assert function_map["node1.launch"] is standard_launcher
    assert function_map["node2.launch"] is standard_launcher


def test_linker_raises_on_missing_code(assembly, code_registry):
    linker = Linker()

    # Tamper with the assembly to require a hash that doesn't exist
    assembly.symbol_table["node3.launch"] = "hash_c_missing"

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
            "n1.launch": "hash_1",
            "n2.launch": "hash_2",
        },
    )

    with pytest.raises(LinkerError) as exc_info:
        linker.link(assembly, registry)

    error_str = str(exc_info.value)
    assert "hash_1" in error_str
    assert "hash_2" in error_str
