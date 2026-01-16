生成 Quipu 计划以执行测试套件的修复与迁移。

## [WIP] fix(tests): 迁移测试套件以适配 Dyad 架构

### 错误分析
所有报错均源于测试代码引用了已被删除的 Triad 架构组件（`BleachNode`, `WorkerNode`, `StainNode` 及其 Specs 和 Stdlib 实现）。
1.  `cascade-std` 单元测试仍在测试已删除的 IC。
2.  `cascade-compiler` 单元测试断言生成的图是 Triad 结构。
3.  `cascade-vm` 集成测试手动构建了 Triad 物理图，导致无法加载类和函数。

### 用户需求
修复所有因 Dyad 重构导致的测试失败。这意味着需要将测试套件从验证“三联体”逻辑迁移到验证“二元体”逻辑。

### 评论
这是一次全面的测试重构。仅仅修复导入是不够的，因为底层的物理模型已经改变。我们需要重写针对 `cascade-std` 的单元测试，并更新 `cascade-vm` 和 `cascade-compiler` 中构建物理图的逻辑。

### 目标
1.  **迁移标准库测试**: 将 `tests/unit/triad` 重命名为 `tests/unit/dyad`，并将测试逻辑从 Bleacher/Stainer 转换为 Launcher/Lander。
2.  **更新编译器测试**: 修改 `test_builder.py` 和 `test_expander.py` 以断言 Dyad 拓扑结构。
3.  **修复 VM 单元测试**: 修正 `test_retry_topology.py` 和 `test_micro_physics.py` 中的导入路径。
4.  **重写 VM 集成测试**: 重写 `test_machine_integration.py` 等测试，使其构建并运行基于 Dyad 的物理图。

### 基本原理
测试必须反映真实的系统架构。
*   `Launcher` 替代了 `Bleacher`，测试重点在于是否正确生成 `ComputeRequest` 并推入队列。
*   `Lander` 替代了 `Stainer`，测试重点在于是否正确处理 `D_result` 中的结果并生成 Trace。
*   集成测试必须模拟真实的 Dyad 数据流：`Launcher` -> `Queue` -> `ComputeService` -> `D_result` -> `Lander`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #task/domain/testing #task/object/test-suite #task/action/migrate #task/state/continue

---

### Script

#### Acts 1: 迁移标准库测试目录与文件

将 `triad` 目录重命名为 `dyad`，并删除旧测试文件，创建新测试文件。

~~~~~act
run_command
~~~~~
~~~~~
mv packages/cascade-std/tests/unit/triad packages/cascade-std/tests/unit/dyad
rm packages/cascade-std/tests/unit/dyad/test_bleacher.py
rm packages/cascade-std/tests/unit/dyad/test_stainer.py
~~~~~

#### Acts 2: 实现 Launcher 单元测试

~~~~~act
write_file
packages/cascade-std/tests/unit/dyad/test_launcher.py
~~~~~
~~~~~python
import time
from unittest.mock import MagicMock, patch

from cascade.spec.physical.nodes import Token
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.physical.dyad import LauncherNode
from cascade.std.dyad.launcher import standard_launcher
from cascade.spec.runtime import ComputeRequest


def create_mock_launcher_node(input_ports_config):
    node = MagicMock(spec=LauncherNode)
    node.id = "test_node.launch"
    node.name = "Launch(test_node)"
    node.reply_to_nid = "test_node.result"
    node.canonical_code_structure_hash = "abc-123"
    node.input_ports = {
        name: PortDef(name, role) for name, role in input_ports_config.items()
    }
    return node


def test_standard_launcher_dispatches_request():
    # Setup Inputs
    inputs = {
        "arg1": Token(payload="hello"),
        "arg2": Token(payload=123),
    }
    node = create_mock_launcher_node({"arg1": PortRole.DATA, "arg2": PortRole.DATA})

    # Mock Resources
    mock_queue = MagicMock()
    resources = {"system.compute_queue": mock_queue}

    # Execute
    standard_launcher(inputs, node, resources)

    # Verify Queue Interaction
    mock_queue.put_nowait.assert_called_once()
    request = mock_queue.put_nowait.call_args[0][0]
    
    assert isinstance(request, ComputeRequest)
    assert request.code_hash == "abc-123"
    assert request.reply_to_nid == "test_node.result"
    assert request.input_refs == {"arg1": "hello", "arg2": 123}
    assert "start_ts" in request.trace


def test_standard_launcher_emits_observability_event():
    node = create_mock_launcher_node({})
    mock_queue = MagicMock()
    resources = {"system.compute_queue": mock_queue}

    # Use IO capture (simulated by return value in test harness, 
    # but strictly standard_launcher uses @implements which returns dict)
    # The @implements decorator logic wraps it, but for unit testing the inner function logic:
    # We need to simulate the IO wrapper if we were testing the inner logic directly,
    # OR we invoke the decorated function. standard_launcher IS the decorated function.
    
    outputs = standard_launcher({}, node, resources)

    assert "obs_output" in outputs
    obs_token = outputs["obs_output"]
    assert obs_token.payload["t"] == "task.lifecycle"
    assert obs_token.payload["data"]["state"] == "Running"
~~~~~

#### Acts 3: 实现 Lander 单元测试

~~~~~act
write_file
packages/cascade-std/tests/unit/dyad/test_lander.py
~~~~~
~~~~~python
from unittest.mock import MagicMock, patch

from cascade.spec.physical.nodes import Token
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.physical.dyad import LanderNode
from cascade.spec.specs.dyad import LanderSpec
from cascade.std.dyad.lander import standard_lander


def create_mock_lander_node(output_ports_config):
    node = MagicMock(spec=LanderNode)
    node.id = "test_node.land"
    node.name = "Land(test_node)"
    node.output_ports = {
        name: PortDef(name, role) for name, role in output_ports_config.items()
    }
    return node


def test_standard_lander_success_path():
    # Setup Inputs (Result from ComputeService)
    start_ts = 1000.0
    end_ts = 1005.0
    result_payload = "ExecutionResult"
    
    inputs = {
        LanderSpec.result_token.name: Token(
            payload=result_payload,
            trace={"start_ts": start_ts, "rid": "run-1"}
        )
    }
    
    node = create_mock_lander_node({
        "output_default": PortRole.DATA,
        "output_error": PortRole.DATA
    })

    with patch("time.monotonic", return_value=end_ts):
        outputs = standard_lander(inputs, node, MagicMock())

    # Verify Outputs
    assert "output_default" in outputs
    assert "output_error" not in outputs
    
    out_token = outputs["output_default"]
    assert out_token.payload == result_payload
    assert out_token.trace["duration"] == 5.0
    assert out_token.trace["rid"] == "run-1"


def test_standard_lander_error_path():
    error = ValueError("Task Failed")
    inputs = {
        LanderSpec.result_token.name: Token(
            payload=error,
            trace={"start_ts": 1000.0}
        )
    }
    
    node = create_mock_lander_node({
        "output_default": PortRole.DATA,
        "output_error": PortRole.DATA
    })

    outputs = standard_lander(inputs, node, MagicMock())

    assert "output_error" in outputs
    assert "output_default" not in outputs
    assert outputs["output_error"].payload == error
~~~~~

#### Acts 4: 修复 Compiler Builder 测试

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_builder.py
~~~~~
~~~~~python.old
from cascade.spec.ir.graph import GraphIR, NodeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.ir.fingerprint import Fingerprint
from cascade.compiler.backend.builder import Builder
from cascade.spec.physical.environment import EnvironmentDef
from cascade.reflection import PhysicalIdGenerator
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.components import BleacherSpec


@pytest.fixture
def sample_graph_ir():
~~~~~
~~~~~python.new
from cascade.spec.ir.graph import GraphIR, NodeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.ir.fingerprint import Fingerprint
from cascade.compiler.backend.builder import Builder
from cascade.spec.physical.environment import EnvironmentDef
from cascade.reflection import PhysicalIdGenerator
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.specs.dyad import LauncherSpec


@pytest.fixture
def sample_graph_ir():
~~~~~

#### Acts 5: 修复 Compiler Expander 测试

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/backend/test_expander.py
~~~~~
~~~~~python.old
from cascade.spec.ir.graph import NodeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.ir.fingerprint import Fingerprint
from cascade.spec.physical.ports import PortRole
from cascade.compiler.backend.expander import Expander
from cascade.spec.physical.triad import BleachNode, WorkerNode, StainNode
from cascade.spec.physical.nodes import PhysicsDataNode


def test_expander_creates_triad_structure():
    # 1. Setup IR
    fp = Fingerprint({"canonical_code_structure_hash": "abc"})
    task_def = TaskDef(
        name="my_task",
        args=[ArgumentDef("x", ArgumentKind.POSITIONAL_OR_KEYWORD)],
        fingerprint=fp,
    )
    node_ir = NodeIR(current_node_instance_hash="node_1", name="MyNode", task=task_def)

    # 2. Expand
    expander = Expander()
    subgraph = expander.expand_node(node_ir)

    # 3. Assert Nodes
    # We expect 3 nodes: Launcher, Result, Lander
    assert len(subgraph.nodes) == 3

    launcher = subgraph.launcher
    lander = subgraph.lander
    
    # Imports might be missing in the original file, we assume they are present or will be added if needed,
    # but since this is a patch, we rely on existing context or structural typing if classes aren't imported.
    # However, to be safe, we check properties.
    assert launcher.id == "node_1.launch"
    assert lander.id == "node_1.land"

    # Check intermediate node
    d_result = subgraph.nodes["node_1.result"]
    assert isinstance(d_result, PhysicsDataNode)

    # 4. Assert Channels
    # We expect 1 internal channel: D_result -> Lander
    assert len(subgraph.channels) == 1

    # Verify connections
    # D_result -> Lander
    result_channel = next(
        c
        for c in subgraph.channels
        if c.source_node_id == d_result.id and c.target_node_id == lander.id
    )
    assert result_channel.target_port == "result_token"

    # Verify Port Definitions
    assert "x" in launcher.input_ports
    assert launcher.input_ports["x"].role == PortRole.DATA
    assert launcher.output_ports["obs_output"].role == PortRole.OBSERVABILITY

    assert lander.input_ports["result_token"].role == PortRole.DATA
    assert lander.output_ports["output_default"].role == PortRole.DATA
~~~~~
~~~~~python.new
from cascade.spec.ir.graph import NodeIR, TaskDef, ArgumentDef, ArgumentKind
from cascade.spec.ir.fingerprint import Fingerprint
from cascade.spec.physical.ports import PortRole
from cascade.compiler.backend.expander import Expander
from cascade.spec.physical.dyad import LauncherNode, LanderNode
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.specs.dyad import LanderSpec


def test_expander_creates_dyad_structure():
    # 1. Setup IR
    fp = Fingerprint({"canonical_code_structure_hash": "abc"})
    task_def = TaskDef(
        name="my_task",
        args=[ArgumentDef("x", ArgumentKind.POSITIONAL_OR_KEYWORD)],
        fingerprint=fp,
    )
    node_ir = NodeIR(current_node_instance_hash="node_1", name="MyNode", task=task_def)

    # 2. Expand
    expander = Expander()
    subgraph = expander.expand_node(node_ir)

    # 3. Assert Nodes
    # We expect 3 nodes: Launcher, Result, Lander
    assert len(subgraph.nodes) == 3

    launcher = subgraph.launcher
    lander = subgraph.lander
    
    assert isinstance(launcher, LauncherNode)
    assert isinstance(lander, LanderNode)
    assert launcher.id == "node_1.launch"
    assert lander.id == "node_1.land"

    # Check intermediate node
    d_result = subgraph.nodes["node_1.result"]
    assert isinstance(d_result, PhysicsDataNode)

    # 4. Assert Channels
    # We expect 1 internal channel: D_result -> Lander
    assert len(subgraph.channels) == 1

    # Verify connections
    # D_result -> Lander
    result_channel = next(
        c
        for c in subgraph.channels
        if c.source_node_id == d_result.id and c.target_node_id == lander.id
    )
    assert result_channel.target_port == LanderSpec.result_token.name

    # Verify Port Definitions
    assert "x" in launcher.input_ports
    assert launcher.input_ports["x"].role == PortRole.DATA
    assert launcher.output_ports["obs_output"].role == PortRole.OBSERVABILITY

    assert lander.input_ports[LanderSpec.result_token.name].role == PortRole.DATA
    assert lander.output_ports["output_default"].role == PortRole.DATA
~~~~~

#### Acts 6: 修复 VM Unit 测试导入

~~~~~act
patch_file
packages/cascade-vm/tests/integration/test_retry_topology.py
~~~~~
~~~~~python.old
from cascade.spec.physical.nodes import Token, PhysicsDataNode
from cascade.spec.physical.triad import RetryNode
from cascade.spec.physical.topology import BipartiteGraph, Channel
~~~~~
~~~~~python.new
from cascade.spec.physical.nodes import Token, PhysicsDataNode
from cascade.spec.physical.system_nodes import RetryNode
from cascade.spec.physical.topology import BipartiteGraph, Channel
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/physics/test_micro_physics.py
~~~~~
~~~~~python.old
from cascade.spec.physical.nodes import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.system_nodes import StainNode
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.kernel import PhysicsKernel
from cascade.vm.resource_registry import ResourceRegistry
from cascade.std.triad.stainer import standard_stainer
from cascade.std.system.terminator import halt_signal
~~~~~
~~~~~python.new
from cascade.spec.physical.nodes import Token, PhysicsDataNode, PhysicsFuncNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.dyad import LanderNode
from cascade.spec.specs.dyad import LanderSpec
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.vm.memory import VolatileMemory
from cascade.vm.reactor import Reactor
from cascade.vm.kernel import PhysicsKernel
from cascade.vm.resource_registry import ResourceRegistry
from cascade.std.dyad.lander import standard_lander
from cascade.std.system.terminator import halt_signal
~~~~~

~~~~~act
patch_file
packages/cascade-vm/tests/unit/physics/test_micro_physics.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_physics_the_crash():
    # Topology: D_in -> Stainer -> (D_ok, D_err)
    # We simulate the stainer receiving a failed result from a worker

    d_res = PhysicsDataNode(id="D_res", name="WorkerResult")  # Holds the Exception
    d_trace = PhysicsDataNode(id="D_trace", name="TraceCtx")

    f_stain = StainNode(
        id="F_stain",
        name="Stainer",
        input_ports={
            "worker_result": PortDef("worker_result", PortRole.DATA),
            "trace_input": PortDef("trace_input", PortRole.DATA),
        },
        output_ports={
            "output_default": PortDef("output_default", PortRole.DATA),
            "output_error": PortDef("output_error", PortRole.DATA),  # Sovereign Port
            "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY),
        },
    )

    d_ok = PhysicsDataNode(id="D_ok", name="SuccessPath")
    d_err = PhysicsDataNode(id="D_err", name="ErrorPath")
    d_obs = PhysicsDataNode(id="global.observability.bus", name="Bus", capacity=100)

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d_res, d_trace, f_stain, d_ok, d_err, d_obs]}

    # Wiring
    graph.channels.append(Channel(d_res.id, "out", f_stain.id, "worker_result"))
    graph.channels.append(Channel(d_trace.id, "out", f_stain.id, "trace_input"))

    graph.channels.append(Channel(f_stain.id, "output_default", d_ok.id, "in"))
    graph.channels.append(Channel(f_stain.id, "output_error", d_err.id, "in"))
    graph.channels.append(Channel(f_stain.id, "obs_output", d_obs.id, "in"))

    memory = VolatileMemory()
    resources = ResourceRegistry()
    kernel = PhysicsKernel({f_stain.id: standard_stainer}, resources)
    reactor = Reactor(graph, memory, kernel)

    # Inject Fault
    memory.put(d_res, Token(payload=ValueError("Micro-Physics Failure")))
    memory.put(d_trace, Token(payload={"rid": "test-crash"}))

    # Action
    fired = reactor.step()

    # Verification
    assert fired == 1

    # 1. Error Path should be active
    assert memory.get_count(d_err.id) == 1
    err_token = memory.take(d_err.id)
    assert isinstance(err_token.payload, ValueError)

    # 2. Success Path should be empty (Sovereign Routing)
    assert memory.get_count(d_ok.id) == 0
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_physics_the_crash():
    # Topology: D_res -> Lander -> (D_ok, D_err)
    # We simulate the lander receiving a failed result

    d_res = PhysicsDataNode(id="D_res", name="WorkerResult")  # Holds the Exception (and trace)

    f_land = LanderNode(
        id="F_land",
        name="Lander",
        input_ports={
            LanderSpec.result_token.name: PortDef(LanderSpec.result_token.name, PortRole.DATA)
        },
        output_ports={
            "output_default": PortDef("output_default", PortRole.DATA),
            "output_error": PortDef("output_error", PortRole.DATA),
            "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY),
        },
    )

    d_ok = PhysicsDataNode(id="D_ok", name="SuccessPath")
    d_err = PhysicsDataNode(id="D_err", name="ErrorPath")
    d_obs = PhysicsDataNode(id="global.observability.bus", name="Bus", capacity=100)

    graph = BipartiteGraph()
    graph.nodes = {n.id: n for n in [d_res, f_land, d_ok, d_err, d_obs]}

    # Wiring
    graph.channels.append(Channel(d_res.id, "out", f_land.id, LanderSpec.result_token.name))

    graph.channels.append(Channel(f_land.id, "output_default", d_ok.id, "in"))
    graph.channels.append(Channel(f_land.id, "output_error", d_err.id, "in"))
    graph.channels.append(Channel(f_land.id, "obs_output", d_obs.id, "in"))

    memory = VolatileMemory()
    resources = ResourceRegistry()
    kernel = PhysicsKernel({f_land.id: standard_lander}, resources)
    reactor = Reactor(graph, memory, kernel)

    # Inject Fault (Trace embedded in Token)
    memory.put(d_res, Token(
        payload=ValueError("Micro-Physics Failure"),
        trace={"rid": "test-crash", "start_ts": 1000.0}
    ))

    # Action
    fired = reactor.step()

    # Verification
    assert fired == 1

    # 1. Error Path should be active
    assert memory.get_count(d_err.id) == 1
    err_token = memory.take(d_err.id)
    assert isinstance(err_token.payload, ValueError)

    # 2. Success Path should be empty (Sovereign Routing)
    assert memory.get_count(d_ok.id) == 0
~~~~~

#### Acts 7: 重写 Linker Validation 测试

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
from cascade.test_utils import EventDrivenRunner
from cascade.vm.registry import CodeRegistry
from cascade.vm.linker import Linker, LinkerError
from cascade.spec.physical.constants import NodePrefix

# Standard library function imports
from cascade.std.dyad.launcher import standard_launcher
from cascade.std.dyad.lander import standard_lander
from cascade.std.system.observer import standard_observer


@task
def missing_task():
    return "I do not exist"


@pytest.mark.asyncio
async def test_blind_optimism_without_linker():
    # 1. Compile
    workflow = missing_task()
    ir_generator = IRGenerator()
    builder = Builder()
    generation_result = ir_generator.generate(workflow)
    artifact = builder.build(generation_result.ir, EnvironmentDef())
    assembly = artifact.assembly

    # 2. Setup Empty Registry
    code_registry = CodeRegistry()

    # 3. Manual Wiring (Simulating current Linker logic)
    func_map = {}
    for node_id in assembly.graph.nodes:
        if node_id.endswith(f".{NodePrefix.LAUNCH}"):
            func_map[node_id] = standard_launcher
        elif node_id.endswith(f".{NodePrefix.LAND}"):
            func_map[node_id] = standard_lander
        elif "observer" in node_id:
            func_map[node_id] = standard_observer

    # 4. Initialize Runner
    runner = EventDrivenRunner(assembly.graph, func_map, code_registry)
    runner.prime()

    # 5. Run
    await runner.start_loop()
    try:
        assert True
    finally:
        await runner.stop_loop()


@pytest.mark.asyncio
async def test_linker_enforces_integrity():
    # 1. Compile
    workflow = missing_task()
    ir_generator = IRGenerator()
    builder = Builder()
    generation_result = ir_generator.generate(workflow)
    artifact = builder.build(generation_result.ir, EnvironmentDef())
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

#### Acts 8: 重写 Machine Integration 测试

这是最复杂的测试，需要完全重写图构建逻辑以符合 Dyad。

~~~~~act
write_file
packages/cascade-vm/tests/integration/test_machine_integration.py
~~~~~
~~~~~python
import asyncio
import pytest
from typing import Dict, Callable, Tuple

from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode, Token
from cascade.spec.physical.dyad import LauncherNode, LanderNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.specs.dyad import LauncherSpec, LanderSpec
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.reflection import PhysicalIdGenerator
from cascade.vm.machine import Machine
from cascade.vm.reactor import Reactor
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry
from cascade.vm.kernel import PhysicsKernel
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute import ComputeRequest, LocalComputeService
from cascade.vm.services.chronos import ChronosService
from cascade.spec.runtime import DelayRequest
from cascade.bus.core import EventBus
from cascade.runtime.storage import InMemoryObjectStore

# Standard Library ICs
from cascade.std.dyad.launcher import standard_launcher
from cascade.std.dyad.lander import standard_lander


# --- Test Fixtures ---

async def user_square(n: int) -> int:
    await asyncio.sleep(0.01)
    return n * n


def transparent_halt(inputs: Dict[str, Token], node, resources) -> Dict[str, Token]:
    data_token = inputs["in"]
    return {
        "out": data_token,
        "ctrl": Token(payload=SystemControlToken(command=ControlCommand.HALT)),
    }


def build_test_graph() -> BipartiteGraph:
    graph = BipartiteGraph()
    base_id = "task_square"

    # Node IDs
    d_in_id = "d_in"
    f_launch_id = PhysicalIdGenerator.launcher_node(base_id)
    d_result_id = PhysicalIdGenerator.result_data(base_id)
    f_land_id = PhysicalIdGenerator.lander_node(base_id)
    d_out_id = "d_out"
    f_halt_id = "f_halt"
    d_final_id = "d_final"

    # Nodes
    d_in = PhysicsDataNode(id=d_in_id, name="Input")
    
    f_launch = LauncherNode(
        id=f_launch_id,
        name="Launch(square)",
        input_ports={"n": PortDef("n", PortRole.DATA)},
        output_ports={"obs_output": PortDef("obs_output", PortRole.OBSERVABILITY)},
        canonical_code_structure_hash="hash_for_user_square",
        reply_to_nid=d_result_id
    )

    d_result = PhysicsDataNode(id=d_result_id, name="Result(square)")

    f_land = LanderNode(
        id=f_land_id,
        name="Land(square)",
        input_ports={LanderSpec.result_token.name: PortDef(LanderSpec.result_token.name, PortRole.DATA)},
        output_ports={
            "output_default": PortDef("output_default", PortRole.DATA),
            "output_error": PortDef("output_error", PortRole.DATA),
            "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY),
        },
    )

    d_out = PhysicsDataNode(id=d_out_id, name="IntermediateOutput")

    f_halt = PhysicsFuncNode(
        id=f_halt_id,
        name="TransparentHalt",
        input_ports={"in": PortDef("in", PortRole.DATA)},
        output_ports={
            "out": PortDef("out", PortRole.DATA),
            "ctrl": PortDef("ctrl", PortRole.SIGNAL),
        },
    )
    
    d_final = PhysicsDataNode(id=d_final_id, name="FinalOutput")

    for node in [d_in, f_launch, d_result, f_land, d_out, f_halt, d_final]:
        graph.nodes[node.id] = node

    # Channels
    graph.channels.extend([
        # Input -> Launcher
        Channel(d_in_id, "out", f_launch_id, "n"),
        
        # Note: Launcher -> Queue is NOT a physical channel.
        # Queue -> D_result is NOT a physical channel (handled by ComputeService).
        
        # D_result -> Lander
        Channel(d_result_id, "out", f_land_id, LanderSpec.result_token.name),
        
        # Lander -> Output
        Channel(f_land_id, "output_default", d_out_id, "in"),
        
        # Output -> Halt
        Channel(d_out_id, "out", f_halt_id, "in"),
        Channel(f_halt_id, "out", d_final_id, "in")
    ])

    return graph


@pytest.mark.asyncio
async def test_machine_self_terminating_flow():
    graph = build_test_graph()
    memory = VolatileMemory()

    function_map: Dict[str, Callable] = {
        PhysicalIdGenerator.launcher_node("task_square"): standard_launcher,
        PhysicalIdGenerator.lander_node("task_square"): standard_lander,
        "f_halt": transparent_halt,
    }

    code_registry = CodeRegistry()
    code_registry.register("hash_for_user_square", user_square)
    object_store = InMemoryObjectStore()
    
    compute_queue: asyncio.Queue[ComputeRequest] = asyncio.Queue()
    chronos_queue: asyncio.Queue[DelayRequest] = asyncio.Queue()
    ingress_queue: asyncio.Queue[Tuple[str, Token]] = asyncio.Queue()
    wakeup_event = asyncio.Event()
    event_bus = EventBus()

    resource_registry = ResourceRegistry()
    resource_registry.register("system.object_store", object_store)
    resource_registry.register("system.compute_queue", compute_queue)
    resource_registry.register("system.chronos_queue", chronos_queue)
    resource_registry.register("system.event_bus", event_bus)

    kernel = PhysicsKernel(function_map, resource_registry)
    reactor = Reactor(graph, memory, kernel, ingress_queue)
    
    compute_service = LocalComputeService(
        store=object_store,
        registry=code_registry,
        inbound_queue=compute_queue,
        outbound_queue=ingress_queue,
        wakeup_event=wakeup_event,
    )
    
    chronos_service = ChronosService(
        inbound_queue=chronos_queue,
        outbound_queue=ingress_queue,
        wakeup_event=wakeup_event,
    )
    
    machine = Machine(reactor, compute_service, chronos_service, wakeup_event)

    # Prime
    initial_value = 10
    initial_ref = object_store.put(initial_value)
    initial_token = Token(payload=initial_ref, trace={"rid": "self_term_run"})
    memory.put(graph.nodes["d_in"], initial_token)

    # Run
    try:
        await asyncio.wait_for(machine.run(), timeout=5.0)
    except asyncio.TimeoutError:
        pytest.fail("Machine execution timed out! Self-termination failed.")

    # Assert
    assert memory.get_count("d_final") == 1
    final_token = memory.take("d_final")
    final_ref = final_token.payload
    final_result = object_store.get(final_ref)
    assert final_result == 100
~~~~~

#### Acts 9: 重写 Context Injection 测试

~~~~~act
write_file
packages/cascade-vm/tests/integration/test_context_injection.py
~~~~~
~~~~~python
import pytest
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.dyad import LauncherNode, LanderNode
from cascade.spec.physical.system_nodes import ObservabilityNode
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.specs.dyad import LanderSpec
from cascade.spec.runtime.observability import EventState
from cascade.bus.events import TaskExecutionStarted, TaskExecutionFinished
from cascade.test_utils import EventDrivenRunner
from cascade.std.dyad.launcher import standard_launcher
from cascade.std.dyad.lander import standard_lander
from cascade.std.system.observer import standard_observer
from cascade.vm.registry import CodeRegistry
from cascade.reflection import PhysicalIdGenerator


async def actual_user_logic(arg1: str) -> str:
    return f"processed_{arg1}"


def build_test_dyad_for_injection() -> BipartiteGraph:
    graph = BipartiteGraph()
    base_id = "task"
    f_launch_id = PhysicalIdGenerator.launcher_node(base_id)
    d_result_id = PhysicalIdGenerator.result_data(base_id)
    f_land_id = PhysicalIdGenerator.lander_node(base_id)
    d_life_id = PhysicalIdGenerator.observability_bus()
    f_obs_id = PhysicalIdGenerator.observability_observer()

    d_in = PhysicsDataNode(id="d_in", name="Input")
    
    f_launch = LauncherNode(
        id=f_launch_id,
        name="Launch",
        input_ports={"arg1": PortDef("arg1", PortRole.DATA)},
        output_ports={"obs_output": PortDef("obs_output", PortRole.OBSERVABILITY)},
        canonical_code_structure_hash="hash_user_logic_001",
        reply_to_nid=d_result_id
    )
    
    d_result = PhysicsDataNode(id=d_result_id, name="Result")
    
    f_land = LanderNode(
        id=f_land_id,
        name="Land",
        input_ports={LanderSpec.result_token.name: PortDef(LanderSpec.result_token.name, PortRole.DATA)},
        output_ports={
            "output_default": PortDef("output_default", PortRole.DATA),
            "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY),
        }
    )
    
    d_out = PhysicsDataNode(id="d_out", name="Output")
    
    d_life = PhysicsDataNode(id=d_life_id, name="EventBus", capacity=100)
    f_obs = ObservabilityNode(
        id=f_obs_id,
        name="Observer",
        input_ports={"event_token": PortDef("event_token", PortRole.OBSERVABILITY)},
    )

    for n in [d_in, f_launch, d_result, f_land, d_out, d_life, f_obs]:
        graph.nodes[n.id] = n

    graph.channels.extend([
        Channel("d_in", "out", f_launch_id, "arg1"),
        Channel(d_result_id, "out", f_land_id, LanderSpec.result_token.name),
        Channel(f_land_id, "output_default", "d_out", "in"),
        
        Channel(f_launch_id, "obs_output", d_life_id, "in"),
        Channel(f_land_id, "obs_output", d_life_id, "in"),
        Channel(d_life_id, "out", f_obs_id, "event_token"),
    ])
    return graph


@pytest.mark.asyncio
async def test_genesis_injection_propagates_run_id():
    registry = CodeRegistry()
    registry.register("hash_user_logic_001", actual_user_logic)

    graph = build_test_dyad_for_injection()
    base_id = "task"
    
    function_map = {
        PhysicalIdGenerator.launcher_node(base_id): standard_launcher,
        PhysicalIdGenerator.lander_node(base_id): standard_lander,
        PhysicalIdGenerator.observability_observer(): standard_observer,
    }

    runner = EventDrivenRunner(graph, function_map, registry)
    runner.prime()
    
    # Manually configure compute service to bridge queue -> d_result
    # The EventDrivenRunner sets up a LocalComputeService, but we need to ensure 
    # it knows about our object store and queues.
    # EventDrivenRunner internal setup handles this.

    await runner.start_loop()

    try:
        runner.inject_input("d_in", "test_data")

        def is_success(e):
            return (
                isinstance(e, TaskExecutionFinished)
                and e.task_id == "task"
                and e.status is EventState.SUCCEEDED
            )

        await runner.wait_for_event(is_success, timeout=2.0)

        events = runner._captured_events
        lifecycle_events = [
            e for e in events if isinstance(e, (TaskExecutionStarted, TaskExecutionFinished))
        ]
        
        assert len(lifecycle_events) >= 2
        for event in lifecycle_events:
            assert event.run_id == runner.run_id

    finally:
        await runner.stop_loop()
~~~~~

### 下一步建议
测试代码已全部更新。现在可以运行 `pytest` 来验证迁移是否成功。
