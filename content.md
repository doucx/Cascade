简要回答
是的，你的分析非常精准。我们正面临一个由于“强制身份标识”这一正确架构决策而暴露出的系统性一致性问题。我将执行一个 D2 计划，通过在编译器后端、运行时规范和测试套件中显式传递 `canonical_code_structure_hash`，并在前端消除潜在的变量作用域风险，来从根本上解决这些链接和类型错误。

## [WIP] fix: 强制传递 canonical_hash 以修复编译器与VM的链接断裂

### 错误分析
当前测试失败的核心原因是 **身份丢失**。

1.  **编译器后端 (Backend)**: 在生成合成节点（Lifecycle Emitters）时，未符合 `PhysicsFuncNode` 的新契约，遗漏了 `canonical_code_structure_hash`。这导致了 `TypeError`，阻塞了 TCO 和拓扑构建的测试。
2.  **VM 运行时 (Executor)**: `PhysicsExecutor` 依赖 `canonical_code_structure_hash` 在符号表中查找函数。由于测试用例构造的 `FuncNode` 默认为空哈希，导致查找 `_symbol_table.get("")` 失败 (RuntimeError)，进而导致无法产生 Output Token (KeyError)。
3.  **VM 测试套件**: `test_physics.py` 和 `test_funcnode.py` 中的 Mock 对象构造落后于架构变更，使用了旧的签名。

### 用户需求
1.  **修复 Backend**: 确保所有 `PhysicsFuncNode`（包括合成的）都拥有合法的 `canonical_code_structure_hash`。
2.  **强化 Spec**: 修改 `cascade.spec.physics.FuncNode`，移除 `canonical_code_structure_hash` 的默认值，强制使用者提供。
3.  **修复 Tests**: 更新 VM 相关测试，提供明确的哈希值，确保链接成功。
4.  **防御性修复 Frontend**: 确保 `frontend.py` 中 `MappedLazyResult` 处理逻辑的变量作用域安全。

### 评论
这是一个架构一致性修复。虽然看似只是为了让测试通过，但实际上是在“编译器 IR”和“运行时 Physics”之间建立了一条不可断裂的身份由于链。这对于系统的确定性和可调试性至关重要。

### 目标
1.  消除所有 `TypeError: PhysicsFuncNode.__init__`。
2.  消除所有 `RuntimeError: Linking failed`。
3.  确保 `cascade-compiler` 和 `cascade-vm` 的所有单元测试通过。

### 基本原理
我们将遵循“显式优于隐式”的原则：
*   **Synthetic Nodes**: 为编译器生成的内部节点分配符合命名公理的不仅是实例哈希，还有固定的规范哈希（如 `canonical_system_resultemitter_hash`）。
*   **Spec**: 通过移除 `__init__` 中的默认值，利用 Python 的 Type Checker 和 Runtime Failure 来强制所有下游代码（包括未被发现的测试）遵守新契约。

### 标签
#intent/fix #flow/ready #priority/high
#comp/runtime #comp/compiler #comp/tests #concept/state
#task/domain/architecture #task/object/identity-hash #task/action/enforce
#task/state/continue

---

### Script

#### Acts 1: 强化 Physics 规范 (Spec)

首先，修改 `cascade.spec.physics.FuncNode`，移除 `canonical_code_structure_hash` 的默认值。这将显式地通过 `TypeError` 捕获所有未更新的调用点。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/physics.py
~~~~~
~~~~~python.old
    def __init__(
        self,
        name: str,
        canonical_code_structure_hash: str = "",
        resource_requirements: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.canonical_code_structure_hash = canonical_code_structure_hash
        self.resource_requirements = resource_requirements or {}
~~~~~
~~~~~python.new
    def __init__(
        self,
        name: str,
        canonical_code_structure_hash: str,
        resource_requirements: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.canonical_code_structure_hash = canonical_code_structure_hash
        self.resource_requirements = resource_requirements or {}
~~~~~

#### Acts 2: 修复编译器后端 (Backend)

在生成 `result_emitter` 和 `term_emitter` 时，显式赋予它们符合公理的规范哈希。即便它们不是用户代码，它们在系统中也需要一个稳定的身份。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
        # 1. Create Result Emitter Node
        current_result_emitter_hash = self._compute_synthetic_hash("result_emitter")
        result_emitter_node = PhysicsFuncNode(
            current_node_instance_hash=current_result_emitter_hash,
            name="result_emitter",
            inputs={"result": current_root_output_hash},
            sink_id="main_output",
        )
        self._func_nodes[current_result_emitter_hash] = result_emitter_node

        # 2. Create Termination Emitter Node and its input DataNode
        current_term_emitter_hash = self._compute_synthetic_hash("term_emitter")
        # The signal comes FROM the result emitter
        current_signal_slot_hash = self._compute_data_slot_hash(current_result_emitter_hash, "signal")

        signal_data_node = PhysicsDataNode(
            current_data_slot_hash=current_signal_slot_hash,
            name="term_emitter.signal",
            producer_node_instance_hash=current_result_emitter_hash,
        )
        self._data_nodes[current_signal_slot_hash] = signal_data_node

        term_emitter_node = PhysicsFuncNode(
            current_node_instance_hash=current_term_emitter_hash,
            name="term_emitter",
            inputs={"signal": current_signal_slot_hash},
            sink_id="__system_lifecycle_signal",
        )
~~~~~
~~~~~python.new
        # 1. Create Result Emitter Node
        current_result_emitter_hash = self._compute_synthetic_hash("result_emitter")
        result_emitter_node = PhysicsFuncNode(
            current_node_instance_hash=current_result_emitter_hash,
            canonical_code_structure_hash="canonical_system_resultemitter_hash",
            name="result_emitter",
            inputs={"result": current_root_output_hash},
            sink_id="main_output",
        )
        self._func_nodes[current_result_emitter_hash] = result_emitter_node

        # 2. Create Termination Emitter Node and its input DataNode
        current_term_emitter_hash = self._compute_synthetic_hash("term_emitter")
        # The signal comes FROM the result emitter
        current_signal_slot_hash = self._compute_data_slot_hash(current_result_emitter_hash, "signal")

        signal_data_node = PhysicsDataNode(
            current_data_slot_hash=current_signal_slot_hash,
            name="term_emitter.signal",
            producer_node_instance_hash=current_result_emitter_hash,
        )
        self._data_nodes[current_signal_slot_hash] = signal_data_node

        term_emitter_node = PhysicsFuncNode(
            current_node_instance_hash=current_term_emitter_hash,
            canonical_code_structure_hash="canonical_system_termemitter_hash",
            name="term_emitter",
            inputs={"signal": current_signal_slot_hash},
            sink_id="__system_lifecycle_signal",
        )
~~~~~

#### Acts 3: 修复 VM 执行器测试 (Test Physics Executor)

更新 `test_physics.py`，在构造 `FuncNode` 时必须传入与 Symbol Table 匹配的哈希键。这是修复 Link Error 的关键。

~~~~~act
patch_file
packages/cascade-vm/tests/unit/executors/test_physics.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_physics_executor_submit_sync_task(mock_reactor, mock_symbol_table):
    """
    Tests that the executor can correctly find and execute a synchronous task,
    unpacking token payloads and pushing a successful ExecutionFinished event.
    """
    # 1. Setup
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)

    node = FuncNode(name="sync_add_hash")  # Using name as hash for simplicity in test
    inputs = {"a": Token(payload=10), "b": Token(payload=20)}

    # 2. Action
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_physics_executor_submit_sync_task(mock_reactor, mock_symbol_table):
    """
    Tests that the executor can correctly find and execute a synchronous task,
    unpacking token payloads and pushing a successful ExecutionFinished event.
    """
    # 1. Setup
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)

    node = FuncNode(
        name="sync_add", canonical_code_structure_hash="sync_add_hash"
    )  # Explicit linkage
    inputs = {"a": Token(payload=10), "b": Token(payload=20)}

    # 2. Action
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/executors/test_physics.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_physics_executor_submit_async_task(mock_reactor, mock_symbol_table):
    """
    Tests that the executor can correctly execute an asynchronous task.
    """
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)

    node = FuncNode(name="async_add_hash")
    inputs = {"a": Token(5), "b": Token(5)}

    await executor.submit(node, inputs)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_physics_executor_submit_async_task(mock_reactor, mock_symbol_table):
    """
    Tests that the executor can correctly execute an asynchronous task.
    """
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)

    node = FuncNode(name="async_add", canonical_code_structure_hash="async_add_hash")
    inputs = {"a": Token(5), "b": Token(5)}

    await executor.submit(node, inputs)
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/executors/test_physics.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_physics_executor_handles_sync_failure(mock_reactor, mock_symbol_table):
    """
    Tests that if a synchronous task fails, an ExecutionFinished event with an
    error is pushed to the reactor.
    """
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)

    node = FuncNode(name="sync_fail_hash")
    inputs = {"a": Token(1), "b": Token(1)}

    await executor.submit(node, inputs)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_physics_executor_handles_sync_failure(mock_reactor, mock_symbol_table):
    """
    Tests that if a synchronous task fails, an ExecutionFinished event with an
    error is pushed to the reactor.
    """
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)

    node = FuncNode(name="sync_fail", canonical_code_structure_hash="sync_fail_hash")
    inputs = {"a": Token(1), "b": Token(1)}

    await executor.submit(node, inputs)
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/executors/test_physics.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_physics_executor_handles_async_failure(mock_reactor, mock_symbol_table):
    """
    Tests failure handling for asynchronous tasks.
    """
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)

    node = FuncNode(name="async_fail_hash")
    inputs = {"a": Token(1), "b": Token(1)}

    await executor.submit(node, inputs)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_physics_executor_handles_async_failure(mock_reactor, mock_symbol_table):
    """
    Tests failure handling for asynchronous tasks.
    """
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)

    node = FuncNode(name="async_fail", canonical_code_structure_hash="async_fail_hash")
    inputs = {"a": Token(1), "b": Token(1)}

    await executor.submit(node, inputs)
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/executors/test_physics.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_physics_executor_handles_missing_function(
    mock_reactor, mock_symbol_table
):
    """
    Tests that a linking error (function not in symbol table) is reported.
    """
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)

    node = FuncNode(name="missing_hash")
    inputs = {}

    await executor.submit(node, inputs)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_physics_executor_handles_missing_function(
    mock_reactor, mock_symbol_table
):
    """
    Tests that a linking error (function not in symbol table) is reported.
    """
    executor = PhysicsExecutor(reactor=mock_reactor, symbol_table=mock_symbol_table)

    node = FuncNode(
        name="missing", canonical_code_structure_hash="missing_hash"
    )  # This hash is NOT in symbol table
    inputs = {}

    await executor.submit(node, inputs)
~~~~~

#### Acts 4: 修复 VM 物理节点测试 (Test Logic Nodes)

更新 `test_funcnode.py` 以适应新的构造函数签名。

~~~~~act
patch_file
packages/cascade-spec/tests/physics/test_funcnode.py
~~~~~
~~~~~python.old
def test_funcnode_wiring():
    """验证 FuncNode 可以正确注册输入和输出端口"""
    f_node = FuncNode(name="f1")
    d_in = DataNode(name="in")
    d_out = DataNode(name="out")
~~~~~
~~~~~python.new
def test_funcnode_wiring():
    """验证 FuncNode 可以正确注册输入和输出端口"""
    f_node = FuncNode(name="f1", canonical_code_structure_hash="hash_f1")
    d_in = DataNode(name="in")
    d_out = DataNode(name="out")
~~~~~

~~~~~act
patch_file
packages/cascade-spec/tests/physics/test_funcnode.py
~~~~~
~~~~~python.old
def test_funcnode_activation_logic():
    """验证 FuncNode 的势能检查逻辑 (is_ready)"""
    f_node = FuncNode(name="f2")
    d_in = DataNode(name="in")
    f_node.add_input(Port(name="arg1", source=d_in))
~~~~~
~~~~~python.new
def test_funcnode_activation_logic():
    """验证 FuncNode 的势能检查逻辑 (is_ready)"""
    f_node = FuncNode(name="f2", canonical_code_structure_hash="hash_f2")
    d_in = DataNode(name="in")
    f_node.add_input(Port(name="arg1", source=d_in))
~~~~~

~~~~~act
patch_file
packages/cascade-spec/tests/physics/test_funcnode.py
~~~~~
~~~~~python.old
def test_funcnode_firing_dynamics():
    """验证激发过程：消耗输入，产生输出"""
    f_node = FuncNode(name="f3")
    d_in = DataNode(name="in")
    d_out = DataNode(name="out")

    f_node.add_input(Port(name="arg1", source=d_in))
~~~~~
~~~~~python.new
def test_funcnode_firing_dynamics():
    """验证激发过程：消耗输入，产生输出"""
    f_node = FuncNode(name="f3", canonical_code_structure_hash="hash_f3")
    d_in = DataNode(name="in")
    d_out = DataNode(name="out")

    f_node.add_input(Port(name="arg1", source=d_in))
~~~~~

#### Acts 5: 修复 Reactor 资源测试 (Test Reactor Resource Awareness)

更新 `test_reactor_resource_awareness.py` 中的 helper 函数。

~~~~~act
patch_file
packages/cascade-vm/tests/reactor/test_reactor_resource_awareness.py
~~~~~
~~~~~python.old
def create_topology(n_nodes: int):
    nodes = []
    inputs = []
    for i in range(n_nodes):
        f_node = FuncNode(name=f"task_{i}", resource_requirements={"slots": 1})
        d_in = DataNode(name=f"in_{i}")
        f_node.add_input(Port(name="arg", source=d_in))
        nodes.append(f_node)
        inputs.append(d_in)
    return nodes, inputs
~~~~~
~~~~~python.new
def create_topology(n_nodes: int):
    nodes = []
    inputs = []
    for i in range(n_nodes):
        f_node = FuncNode(
            name=f"task_{i}",
            canonical_code_structure_hash=f"hash_task_{i}",
            resource_requirements={"slots": 1},
        )
        d_in = DataNode(name=f"in_{i}")
        f_node.add_input(Port(name="arg", source=d_in))
        nodes.append(f_node)
        inputs.append(d_in)
    return nodes, inputs
~~~~~

#### Acts 6: 修复 Reactor Wakeup 测试 (Test Reactor Wakeup)

更新 `test_reactor_wakeup_mechanism.py` 中的 helper 函数。

~~~~~act
patch_file
packages/cascade-vm/tests/reactor/test_reactor_wakeup_mechanism.py
~~~~~
~~~~~python.old
def create_topology(n_nodes: int):
    nodes, inputs = [], []
    for i in range(n_nodes):
        f_node = FuncNode(name=f"task_{i}", resource_requirements={"slots": 1})
        d_in = DataNode(name=f"in_{i}")
        f_node.add_input(Port(name="arg", source=d_in))
        nodes.append(f_node)
        inputs.append(d_in)
    return nodes, inputs
~~~~~
~~~~~python.new
def create_topology(n_nodes: int):
    nodes, inputs = [], []
    for i in range(n_nodes):
        f_node = FuncNode(
            name=f"task_{i}",
            canonical_code_structure_hash=f"hash_task_{i}",
            resource_requirements={"slots": 1},
        )
        d_in = DataNode(name=f"in_{i}")
        f_node.add_input(Port(name="arg", source=d_in))
        nodes.append(f_node)
        inputs.append(d_in)
    return nodes, inputs
~~~~~

#### Acts 7: 修复其他 Reactor 测试

修正散落在其他 Reactor 测试文件中的 `FuncNode` 构造。

~~~~~act
patch_file
packages/cascade-vm/tests/reactor/test_polarized_channels.py
~~~~~
~~~~~python.old
    # 1. Setup Topology
    f_node = FuncNode(name="process")
    d_data = DataNode(name="data_in")
    d_signal = DataNode(name="signal_in")
~~~~~
~~~~~python.new
    # 1. Setup Topology
    f_node = FuncNode(name="process", canonical_code_structure_hash="hash_process")
    d_data = DataNode(name="data_in")
    d_signal = DataNode(name="signal_in")
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/reactor/test_polarized_channels.py
~~~~~
~~~~~python.old
    # 1. Setup Topology
    f_source = FuncNode(name="source")
    d_target_data = DataNode(name="data_dest")
    d_target_signal = DataNode(name="signal_dest")
~~~~~
~~~~~python.new
    # 1. Setup Topology
    f_source = FuncNode(name="source", canonical_code_structure_hash="hash_source")
    d_target_data = DataNode(name="data_dest")
    d_target_signal = DataNode(name="signal_dest")
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/reactor/test_reactor_loop.py
~~~~~
~~~~~python.old
    # 1. Setup Physics Topology
    d_node = DataNode(name="d1")
    f_node = FuncNode(name="f1")
    # NOTE: We DO NOT wire d_node to f_node.
~~~~~
~~~~~python.new
    # 1. Setup Physics Topology
    d_node = DataNode(name="d1")
    f_node = FuncNode(name="f1", canonical_code_structure_hash="hash_f1")
    # NOTE: We DO NOT wire d_node to f_node.
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/reactor/test_reactor_loop.py
~~~~~
~~~~~python.old
    # 1. Topology
    d_in = DataNode(name="in")
    d_out = DataNode(name="out")
    f_node = FuncNode(name="process")

    f_node.add_input(Port(name="arg", source=d_in))
~~~~~
~~~~~python.new
    # 1. Topology
    d_in = DataNode(name="in")
    d_out = DataNode(name="out")
    f_node = FuncNode(name="process", canonical_code_structure_hash="hash_process")

    f_node.add_input(Port(name="arg", source=d_in))
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/reactor/test_reactor_loop.py
~~~~~
~~~~~python.old
    # 1. Topology
    d_out = DataNode(name="out")
    f_node = FuncNode(name="process")
    f_node.add_output(Port(name="res", target=d_out))

    reactor = Reactor(executor=AsyncMock())
~~~~~
~~~~~python.new
    # 1. Topology
    d_out = DataNode(name="out")
    f_node = FuncNode(name="process", canonical_code_structure_hash="hash_process")
    f_node.add_output(Port(name="res", target=d_out))

    reactor = Reactor(executor=AsyncMock())
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/reactor/test_routing_vm.py
~~~~~
~~~~~python.old
    # 1. Topology
    f_node = FuncNode(name="decision")
    d_next = DataNode(name="next")
    d_loop = DataNode(name="loop")
~~~~~
~~~~~python.new
    # 1. Topology
    f_node = FuncNode(name="decision", canonical_code_structure_hash="hash_decision")
    d_next = DataNode(name="next")
    d_loop = DataNode(name="loop")
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/reactor/test_routing_vm.py
~~~~~
~~~~~python.old
    Case 2: Broadcasting
    验证同一个 Tag 可以被多个 Channel 接收 (Fan-out)。
    """
    f_node = FuncNode(name="broadcast")
    d_1 = DataNode(name="d1")
    d_2 = DataNode(name="d2")
~~~~~
~~~~~python.new
    Test Case: Broadcasting
    验证同一个 Tag 可以被多个 Channel 接收 (Fan-out)。
    """
    f_node = FuncNode(name="broadcast", canonical_code_structure_hash="hash_broadcast")
    d_1 = DataNode(name="d1")
    d_2 = DataNode(name="d2")
~~~~~

#### Acts 8: 防御性修复 Compiler Frontend

确保 `MappedLazyResult` 处理中的 `func` 变量定义万无一失。我们将显式地将 unwrapping 逻辑放在赋值之后。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python.old
        task_def = self.analyzer.analyze(obj.factory)

        # Ensure we store the raw function, not the Task wrapper
        func = obj.factory
        if hasattr(func, "func"):  # Unwrap Task objects
            func = func.func

        # Populate Symbol Table
~~~~~
~~~~~python.new
        task_def = self.analyzer.analyze(obj.factory)

        # Ensure we store the raw function, not the Task wrapper
        raw_func = obj.factory
        if hasattr(raw_func, "func"):  # Unwrap Task objects
            raw_func = raw_func.func

        # Populate Symbol Table
        self.symbol_table[task_def.canonical_code_structure_hash] = raw_func
~~~~~

### 下一步建议
实施完此计划后，所有的单元测试（包括 VM 和 Compiler 层的）都应该能通过。下一步可以开始集成测试，验证这种通过哈希链接的运行时是否在真实的 `LazyResult` -> `GraphIR` -> `BipartiteGraph` -> `Execution` 流程中工作正常。
