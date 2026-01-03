## [WIP] refactor(compiler): 在 Builder 中组装资源协商闭环

### 用户需求
基于“物理层纯粹性”原则，彻底重构编译器的资源处理逻辑。不再生成简单的 `D_res` 节点，而是组装完整的物理协商回路：
1.  实例化 **Broker IC** (Discrete/Continuous) 来管理每种全局资源。
2.  为每个任务的资源约束生成 **Requestor IC** 和 **Const Probe IC**。
3.  通过精确的布线和 Tag 过滤，实现 `Req -> Broker -> Gnt -> Task -> Rel -> Broker` 的闭环。

### 评论
这是 Cascade 3.0 物理模型的关键里程碑。我们正在移除编译器中的“上帝视角”（直接操作资源槽），转而构建一个完全由局部物理定律驱动的自治系统。
在这个系统中，资源不再是静态的“库存”，而是流动的“许可”。Broker 节点充当了物理场中的“银行”，通过严格的记账（Ledger Loop）保证了守恒定律。

### 目标
1.  在 `cascade-std` 中添加 `const_probe`。
2.  更新 `PhysicalIdGenerator` 以支持 Broker, Ledger, Requestor 等新组件。
3.  重写 `Builder.build`：
    *   用 `F_broker` + `D_ledger` 替换简单的 `D_res`。
    *   为每个任务资源约束生成完整的请求链路 ($F_{probe} \to F_{req} \to F_{broker}$)。
    *   配置 Channel Filter 以实现 GNT 的正确路由。

### 基本原理
*   **Broker Loop**: Broker 必须有一个自环的 `D_ledger` 来维持状态，因为函数节点是无状态的。
*   **Tag Routing**: 多路复用的 Broker 通过 Tag 区分不同的申请者。Channel Filter 充当物理层的“地址解码器”。
*   **Purity**: 常量不应直接出现在 `F_req` 的输入中，而应由 `F_probe` 从 `D_const` 中读取。虽然看似冗余，但这统一了“参数获取”的物理模型。

### 标签
#intent/refine #flow/ready #priority/high #comp/compiler #comp/std #concept/resource #scope/core #ai/instruct #task/domain/compiler #task/object/builder #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 添加 Const Probe

~~~~~act
write_file
packages/cascade-std/src/cascade/std/probe/const.py
~~~~~
~~~~~python
from typing import Dict
from cascade.spec.physics import Token, PhysicsNode


async def const_probe(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    """
    A simple Identity Probe.
    It takes a value from a DataNode (which holds a constant payload)
    and passes it forward.
    In a more complex setup, this could wait for a Trigger.
    """
    # Assuming the input port is named 'value'
    val_token = inputs["value"]
    return {"out": Token(payload=val_token.payload, trace=val_token.trace)}
~~~~~

~~~~~act
write_file
packages/cascade-std/src/cascade/std/probe/const.stitcher.yaml
~~~~~
~~~~~yaml
"const_probe": |-
  Identity probe for constant values.
  Connects a pre-filled D_const node to the rest of the graph.
~~~~~

#### Acts 2: 更新命名生成器

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/utils/naming.py
~~~~~
~~~~~python.old
    @staticmethod
    def global_resource(resource_name: str) -> str:
        return f"canonical.resource.{resource_name}"

    @staticmethod
    def constant(target_node_id: str, arg_name: str) -> str:
        return f"const.{target_node_id}.{arg_name}"
~~~~~
~~~~~python.new
    @staticmethod
    def global_resource(resource_name: str) -> str:
        # Legacy: Keeping it for D_res if needed, but we are moving to brokers
        return f"canonical.resource.{resource_name}"

    @staticmethod
    def global_broker(resource_name: str) -> str:
        return f"canonical.resource.broker.{resource_name}"

    @staticmethod
    def global_ledger(resource_name: str) -> str:
        return f"canonical.resource.ledger.{resource_name}"

    @staticmethod
    def requestor(target_node_id: str, resource_name: str) -> str:
        return f"req.{target_node_id}.{resource_name}"

    @staticmethod
    def probe_const(target_node_id: str, arg_name: str) -> str:
        return f"probe.const.{target_node_id}.{arg_name}"

    @staticmethod
    def constant(target_node_id: str, arg_name: str) -> str:
        # The DataNode holding the constant value
        return f"const.{target_node_id}.{arg_name}"
~~~~~

#### Acts 3: 重构 Builder

这是核心修改。我们将替换原有的资源布线逻辑。

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode
from cascade.spec.triad import ObservabilityNode
from cascade.spec.environment import EnvironmentDef
from cascade.spec.ports import PortDef, PortRole
from .expander import Expander, SubGraph
from cascade.compiler.utils.naming import PhysicalIdGenerator


class Builder:
    def __init__(self):
        self._expander = Expander()

    def build(self, graph_ir: GraphIR, environment: EnvironmentDef) -> BipartiteGraph:
        physical_graph = BipartiteGraph()
        env_resources = {res.name: res for res in environment.resources}

        # 1. Create Objective Environment (D_res nodes)
        for res_def in environment.resources:
            res_node_id = PhysicalIdGenerator.global_resource(res_def.name)
            d_res = PhysicsDataNode(
                id=res_node_id,
                name=f"Resource({res_def.name})",
                capacity=res_def.capacity,
                initial_tokens=res_def.capacity,
            )
            physical_graph.nodes[res_node_id] = d_res
~~~~~
~~~~~python.new
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsDataNode, PhysicsFuncNode
from cascade.spec.triad import ObservabilityNode
from cascade.spec.environment import EnvironmentDef
from cascade.spec.ports import PortDef, PortRole, PortName
from cascade.std.resource.discrete import DiscreteLedger
from .expander import Expander, SubGraph
from cascade.compiler.utils.naming import PhysicalIdGenerator


class Builder:
    def __init__(self):
        self._expander = Expander()

    def build(self, graph_ir: GraphIR, environment: EnvironmentDef) -> BipartiteGraph:
        physical_graph = BipartiteGraph()
        env_resources = {res.name: res for res in environment.resources}

        # 1. Create Resource Brokers (F_broker + internal Ledger loop)
        for res_def in environment.resources:
            broker_id = PhysicalIdGenerator.global_broker(res_def.name)
            ledger_id = PhysicalIdGenerator.global_ledger(res_def.name)

            # D_ledger: Holds the state of the resource
            # We initialize it with a DiscreteLedger object.
            # Currently we assume all resources are Discrete.
            # TODO: Support Continuous resources based on definition.
            initial_ledger = DiscreteLedger(
                total=res_def.capacity, available=res_def.capacity
            )

            d_ledger = PhysicsDataNode(
                id=ledger_id,
                name=f"Ledger({res_def.name})",
                capacity=1,
                initial_tokens=1,
                initial_payload=initial_ledger,
            )

            # F_broker: The logic unit
            f_broker = PhysicsFuncNode(
                id=broker_id,
                name=f"Broker({res_def.name})",
                input_ports={
                    PortName.LEDGER_IN: PortDef(PortName.LEDGER_IN, PortRole.DATA),
                    PortName.REQ: PortDef(PortName.REQ, PortRole.DATA),
                    PortName.REL: PortDef(PortName.REL, PortRole.DATA),
                },
                output_ports={
                    PortName.LEDGER_OUT: PortDef(PortName.LEDGER_OUT, PortRole.DATA),
                    PortName.GNT: PortDef(PortName.GNT, PortRole.RESOURCE),
                    PortName.REQ_OUT: PortDef(PortName.REQ_OUT, PortRole.DATA),
                },
            )

            physical_graph.nodes[ledger_id] = d_ledger
            physical_graph.nodes[broker_id] = f_broker

            # Wire the Ledger Loop
            # D_ledger -> F_broker
            physical_graph.channels.append(
                Channel(
                    source_node_id=ledger_id,
                    source_port="out",
                    target_node_id=broker_id,
                    target_port=PortName.LEDGER_IN,
                )
            )
            # F_broker -> D_ledger
            physical_graph.channels.append(
                Channel(
                    source_node_id=broker_id,
                    source_port=PortName.LEDGER_OUT,
                    target_node_id=ledger_id,
                    target_port="in",
                )
            )

            # Self-Loop for Recirculation of rejected requests
            # If a request is rejected, it comes out of REQ_OUT and goes back to REQ_IN.
            # We need a buffer D_retry for this?
            # Or can we wire REQ_OUT -> D_req (which feeds REQ_IN)?
            # Yes, we will create a shared D_req_buffer for the broker later or handle it per request.
            # Actually, standard pattern is:
            # Inputs -> [D_req_buffer] -> F_broker
            # F_broker -> REQ_OUT -> [D_req_buffer]
            # Let's create a shared Request Buffer for this broker.
            d_req_buffer_id = f"buffer.req.{res_def.name}"
            d_req_buffer = PhysicsDataNode(
                id=d_req_buffer_id, name=f"ReqBuffer({res_def.name})", capacity=1000
            )  # High capacity
            physical_graph.nodes[d_req_buffer_id] = d_req_buffer

            # Connect Buffer -> Broker
            physical_graph.channels.append(
                Channel(
                    source_node_id=d_req_buffer_id,
                    source_port="out",
                    target_node_id=broker_id,
                    target_port=PortName.REQ,
                )
            )

            # Connect Recirculation: Broker -> Buffer
            physical_graph.channels.append(
                Channel(
                    source_node_id=broker_id,
                    source_port=PortName.REQ_OUT,
                    target_node_id=d_req_buffer_id,
                    target_port="in",
                )
            )
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~
~~~~~python.old
        # 5. Wire Global Resources (The Loop)
        for node_ir in graph_ir.nodes:
            subgraph = subgraphs[node_ir.id]

            # Help static analysis
            assert subgraph.bleacher is not None
            assert subgraph.stainer is not None

            for res_name in node_ir.constraints:
                res_node_id = PhysicalIdGenerator.global_resource(res_name)
                port_name = f"res_{res_name}"

                # Acquire: D_res -> F_bleach
                physical_graph.channels.append(
                    Channel(
                        source_node_id=res_node_id,
                        source_port="out",
                        target_node_id=subgraph.bleacher.id,
                        target_port=port_name,
                    )
                )

                # Release: F_stain -> D_res
                physical_graph.channels.append(
                    Channel(
                        source_node_id=subgraph.stainer.id,
                        source_port=port_name,
                        target_node_id=res_node_id,
                        target_port="in",
                    )
                )
~~~~~
~~~~~python.new
        # 5. Wire Global Resources (The Loop)
        for node_ir in graph_ir.nodes:
            subgraph = subgraphs[node_ir.id]

            # Help static analysis
            assert subgraph.bleacher is not None
            assert subgraph.stainer is not None

            for res_name, amount in node_ir.constraints.items():
                broker_id = PhysicalIdGenerator.global_broker(res_name)
                req_buffer_id = f"buffer.req.{res_name}"

                # --- A. Request Chain ---
                # 1. D_const (Amount)
                d_amt_id = PhysicalIdGenerator.constant(node_ir.id, f"req_amt_{res_name}")
                d_amt = PhysicsDataNode(
                    id=d_amt_id,
                    name=f"Amt({res_name})",
                    capacity=1,
                    initial_tokens=1,
                    initial_payload=amount,
                )
                physical_graph.nodes[d_amt_id] = d_amt

                # 2. F_probe (ConstProbe)
                f_probe_id = PhysicalIdGenerator.probe_const(node_ir.id, res_name)
                f_probe = PhysicsFuncNode(
                    id=f_probe_id,
                    name=f"Probe({res_name})",
                    input_ports={"value": PortDef("value", PortRole.DATA)},
                    output_ports={"out": PortDef("out", PortRole.DATA)},
                )
                physical_graph.nodes[f_probe_id] = f_probe

                # 3. F_req (Requestor)
                f_req_id = PhysicalIdGenerator.requestor(node_ir.id, res_name)
                f_req = PhysicsFuncNode(
                    id=f_req_id,
                    name=f"Req({res_name})",
                    input_ports={"amount": PortDef("amount", PortRole.DATA)},
                    output_ports={PortName.REQ_OUT: PortDef(PortName.REQ_OUT, PortRole.DATA)},
                )
                physical_graph.nodes[f_req_id] = f_req

                # 4. Wiring: D_amt -> F_probe -> D_temp -> F_req -> D_req_buffer
                # We need intermediate data nodes because of Bipartite rule (F->D->F)
                
                # D_amt -> F_probe
                physical_graph.channels.append(
                    Channel(d_amt_id, "out", f_probe_id, "value")
                )

                # F_probe -> D_probed
                d_probed_id = f"{f_probe_id}.out"
                d_probed = PhysicsDataNode(id=d_probed_id, name="ProbedVal")
                physical_graph.nodes[d_probed_id] = d_probed

                physical_graph.channels.append(
                    Channel(f_probe_id, "out", d_probed_id, "in")
                )
                
                # D_probed -> F_req
                physical_graph.channels.append(
                    Channel(d_probed_id, "out", f_req_id, "amount")
                )

                # F_req -> D_req_buffer (Global Buffer for the Broker)
                physical_graph.channels.append(
                    Channel(f_req_id, PortName.REQ_OUT, req_buffer_id, "in")
                )

                # --- B. Grant Wiring ---
                # Broker (GNT) -> Bleacher (res_{name})
                # FILTER: Must match the Requestor's tag.
                # The Requestor sets tag = f_req.id (based on std implementation).
                # Wait, Requestor code: "tag=node.id". So tag is f_req_id.
                target_tag = f_req_id
                
                port_name = f"res_{res_name}"
                physical_graph.channels.append(
                    Channel(
                        source_node_id=broker_id,
                        source_port=PortName.GNT,
                        target_node_id=subgraph.bleacher.id,
                        target_port=port_name,
                        tag_filter=target_tag,
                    )
                )

                # --- C. Release Wiring ---
                # Stainer (res_{name}) -> Broker (REL)
                # We need a D_rel_buffer or connect directly to a D_rel?
                # The broker needs a REL input buffer.
                # Let's create a shared REL buffer for the broker too.
                rel_buffer_id = f"buffer.rel.{res_name}"
                if rel_buffer_id not in physical_graph.nodes:
                    d_rel_buffer = PhysicsDataNode(
                        id=rel_buffer_id, name=f"RelBuffer({res_name})", capacity=1000
                    )
                    physical_graph.nodes[rel_buffer_id] = d_rel_buffer
                    
                    # Buffer -> Broker
                    physical_graph.channels.append(
                        Channel(rel_buffer_id, "out", broker_id, PortName.REL)
                    )

                # Stainer -> RelBuffer
                physical_graph.channels.append(
                    Channel(
                        source_node_id=subgraph.stainer.id,
                        source_port=port_name,
                        target_node_id=rel_buffer_id,
                        target_port="in",
                    )
                )
~~~~~

### 下一步建议
我们已经完成了编译器的重构。现在的图结构中包含了大量的 `F_broker`, `F_req`, `F_probe` 节点。
为了验证这一切是否工作正常，我们需要更新集成测试 `test_resource_backpressure.py`。
因为图结构变了，我们需要手动为这些新节点配置 `function_map`，否则 Reactor 会因为找不到函数而报错。
我们需要在测试中导入 `discrete_broker`, `resource_requestor`, `const_probe` 并映射它们。
