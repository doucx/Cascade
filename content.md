生成 Quipu 计划以执行 Phase 4.2：修复 Cascade VM 的测试。

## [WIP] fix(vm): 修复 Cascade VM 测试以适配 Dyad 架构

### 用户需求
修复 `cascade-vm` 包下的单元测试和集成测试。由于 Dyad 架构重构，物理层拓扑发生了变化（`.worker` -> `.launch`, `.bleach` -> `.launch`），导致现有的测试代码因为引用了废弃的节点 ID 后缀而失败。

### 评论
这些测试失败是预期的，因为测试代码硬编码了对旧架构（Triad）物理实现的假设。通过更新这些测试，我们验证了 Dyad 架构在端到端执行流程中的正确性，包括 ID 映射、资源连线和可执行代码的链接。

### 目标
1.  **修复 `test_linker.py`**: 更新测试数据，使用 `LauncherNode` (`.launch`) 和 `LanderNode` (`.land`) 替代 `WorkerNode`，并验证其正确链接到标准库实现。
2.  **修复 `test_ref_architecture.py`**: 更新用户代码注册逻辑，从 `.launch` 节点获取哈希。
3.  **修复 `test_source_node_execution.py`**: 同上，更新节点 ID 引用。
4.  **修复 `test_resource_contention.py`**: 更新资源连线断言，验证资源 GNT 连向 `Launcher` 而非 `Bleacher`。

### 基本原理
Dyad 架构中，`Launcher` 取代了 `Worker` 和 `Bleacher` 的角色。
*   `SymbolTable` 现在映射 `.launch` 节点 ID 到代码哈希。
*   Linker 现在基于 ID 后缀（`.launch`, `.land`）进行链接。
*   资源连线现在连接到 `.launch` 节点。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #task/domain/vm #task/object/tests #task/action/fix #task/state/end

---

### Script

#### Acts 1: 修复 Linker 单元测试

更新测试数据以反映 Dyad 架构。

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_linker.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
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
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_linker.py
~~~~~
~~~~~python.old
def test_linker_raises_on_missing_code(assembly, code_registry):
    linker = Linker()

    # Tamper with the assembly to require a hash that doesn't exist
    assembly.symbol_table["worker3.worker"] = "hash_c_missing"

    with pytest.raises(LinkerError) as exc_info:
        linker.link(assembly, code_registry)
~~~~~
~~~~~python.new
def test_linker_raises_on_missing_code(assembly, code_registry):
    linker = Linker()

    # Tamper with the assembly to require a hash that doesn't exist
    assembly.symbol_table["node3.launch"] = "hash_c_missing"

    with pytest.raises(LinkerError) as exc_info:
        linker.link(assembly, code_registry)
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/test_linker.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
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
~~~~~

#### Acts 2: 修复 test_ref_architecture.py

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_ref_architecture.py
~~~~~
~~~~~python.old
    def register_task(task_name, func):
        # Find the NodeIR
        node_ir = next(n for n in graph_ir.nodes if n.name == task_name)
        # Construct the physical worker ID (Convention from PhysicalIdGenerator)
        worker_id = f"{node_ir.current_node_instance_hash}.worker"
        # Lookup canonical hash
        canonical_hash = assembly.symbol_table[worker_id]
        code_registry.register(canonical_hash, func)
~~~~~
~~~~~python.new
    def register_task(task_name, func):
        # Find the NodeIR
        node_ir = next(n for n in graph_ir.nodes if n.name == task_name)
        # Construct the physical launcher ID (Convention from PhysicalIdGenerator)
        launcher_id = f"{node_ir.current_node_instance_hash}.launch"
        # Lookup canonical hash
        canonical_hash = assembly.symbol_table[launcher_id]
        code_registry.register(canonical_hash, func)
~~~~~

#### Acts 3: 修复 test_source_node_execution.py

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_source_node_execution.py
~~~~~
~~~~~python.old
    # 2. Setup Code Registry for the Compute Service
    code_registry = CodeRegistry()
    worker_node_id = f"{node_ir.current_node_instance_hash}.worker"
    canonical_hash = assembly.symbol_table[worker_node_id]
    code_registry.register(canonical_hash, source_task.func)
~~~~~
~~~~~python.new
    # 2. Setup Code Registry for the Compute Service
    code_registry = CodeRegistry()
    launcher_id = f"{node_ir.current_node_instance_hash}.launch"
    canonical_hash = assembly.symbol_table[launcher_id]
    code_registry.register(canonical_hash, source_task.func)
~~~~~

#### Acts 4: 修复 test_resource_contention.py

更新资源连线断言，使用 `.launch` 替代 `.bleach`。

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
    inspector.get_data_node(d_gnt_id)  # Should be a data node

    # Verify D_gnt -> Bleacher
    bleacher_id = PhysicalIdGenerator.bleach_node(
        sample_node_ir.current_node_instance_hash
    )
    inspector.assert_connection(
        d_gnt_id, bleacher_id, target_port=f"res_{RESOURCE_NAME}"
    )

    # --- PART B: EXECUTION ASSERTION ---
~~~~~
~~~~~python.new
    inspector.get_data_node(d_gnt_id)  # Should be a data node

    # Verify D_gnt -> Launcher
    launcher_id = PhysicalIdGenerator.launcher_node(
        sample_node_ir.current_node_instance_hash
    )
    inspector.assert_connection(
        d_gnt_id, launcher_id, target_port=f"res_{RESOURCE_NAME}"
    )

    # --- PART B: EXECUTION ASSERTION ---
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_resource_contention.py
~~~~~
~~~~~python.old
    # Let's assume index 0 is gpu, 1 is cpu (list order preserved)
    gpu_node_id = node_ids[0]

    # Find channels entering GPU Task Bleacher
    gpu_bleacher_id = PhysicalIdGenerator.bleach_node(gpu_node_id)
    in_channels = [
        c for c in physical_graph.channels if c.target_node_id == gpu_bleacher_id
    ]

    # Check sources. One should be from GPU grant chain. None from CPU.
    connected_sources = [c.source_node_id for c in in_channels]
~~~~~
~~~~~python.new
    # Let's assume index 0 is gpu, 1 is cpu (list order preserved)
    gpu_node_id = node_ids[0]

    # Find channels entering GPU Task Launcher
    gpu_launcher_id = PhysicalIdGenerator.launcher_node(gpu_node_id)
    in_channels = [
        c for c in physical_graph.channels if c.target_node_id == gpu_launcher_id
    ]

    # Check sources. One should be from GPU grant chain. None from CPU.
    connected_sources = [c.source_node_id for c in in_channels]
~~~~~

### 下一步建议
测试修复完成后，建议运行全量测试以确保 Dyad 重构没有引入回归。至此，Dyad 架构重构的主要实施阶段已经结束。后续工作可以关注删除旧代码（如 `cascade.std.triad`）和优化文档。
