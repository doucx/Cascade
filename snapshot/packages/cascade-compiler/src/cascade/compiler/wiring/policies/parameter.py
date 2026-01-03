from cascade.spec.ir.models import NodeIR
from cascade.spec.physics import PhysicsDataNode, PhysicsFuncNode
from cascade.spec.ports import PortDef, PortRole, PortName
from cascade.compiler.backend.expander import SubGraph
from cascade.compiler.utils.naming import PhysicalIdGenerator
from cascade.compiler.wiring.context import WiringContext
from cascade.compiler.wiring.protocol import WiringPolicy


class ParameterWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:
        pass

    def apply(self, ctx: WiringContext, node_ir: NodeIR, subgraph: SubGraph) -> None:
        assert subgraph.bleacher is not None

        for input_key, source_ref in node_ir.inputs.items():
            # Resolve the actual port name on the Bleacher.
            # NodeIR input keys might be positional indices ("0", "1") or keyword names.
            # We map indices to argument names using the TaskDef.
            if input_key.isdigit():
                idx = int(input_key)
                if idx < len(node_ir.task.args):
                    port_name = node_ir.task.args[idx].name
                else:
                    # Fallback/Error case: index out of range for defined args.
                    # We use the key as is, which will likely fail later at wiring validation if invalid.
                    port_name = input_key
            else:
                port_name = input_key

            # Case A: Reference to another node (Dependency)
            if isinstance(source_ref, str) and source_ref in ctx.subgraphs:
                source_subgraph = ctx.get_subgraph(source_ref)
                assert source_subgraph.stainer is not None

                # Violation Fix: Insert D_dep (Intermediate Data Node)
                # Use input_key for ID uniqueness to avoid collisions if multiple inputs map to same name (unlikely but safe)
                d_dep_id = f"dep.{source_ref}.to.{node_ir.id}.{input_key}"
                d_dep = PhysicsDataNode(id=d_dep_id, name=f"Dep({port_name})")
                ctx.wire.add_node(d_dep)

                # Source Stainer -> D_dep (Connect from output_default)
                ctx.wire.connect(source_subgraph.stainer.id, "output_default", d_dep_id, "in")

                # D_dep -> Target Bleacher
                ctx.wire.connect(d_dep_id, "out", subgraph.bleacher.id, port_name)

            # Case B: Literal Value (Constant) - Use Probe Model
            else:
                # 1. D_const (DataNode holding the literal value)
                d_const_id = PhysicalIdGenerator.constant(node_ir.id, input_key)
                d_const = PhysicsDataNode(
                    id=d_const_id,
                    name=f"Const({port_name})",
                    capacity=1,
                    initial_tokens=1,
                    initial_payload=source_ref,
                )
                ctx.wire.add_node(d_const)

                # 2. F_probe (The probe node for constants)
                f_probe_id = PhysicalIdGenerator.probe_const(node_ir.id, input_key)
                f_probe = PhysicsFuncNode(
                    id=f_probe_id,
                    name=f"Probe({port_name})",
                    input_ports={"value": PortDef("value", PortRole.DATA)},
                    output_ports={"out": PortDef("out", PortRole.DATA)},
                )
                ctx.wire.add_node(f_probe)

                # 3. D_probed (Intermediate data node to connect to Bleacher)
                d_probed_id = f"{f_probe_id}.out"
                d_probed = PhysicsDataNode(id=d_probed_id, name=f"Probed({port_name})")
                ctx.wire.add_node(d_probed)

                # 4. Wiring
                # D_const -> F_probe
                ctx.wire.connect(d_const_id, "out", f_probe_id, "value")
                # F_probe -> D_probed
                ctx.wire.connect(f_probe_id, "out", d_probed_id, "in")
                # D_probed -> Target Bleacher
                ctx.wire.connect(d_probed_id, "out", subgraph.bleacher.id, port_name)