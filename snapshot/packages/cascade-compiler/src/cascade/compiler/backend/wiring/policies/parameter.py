from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.std.specs import StainerSpec
from cascade.compiler.backend.expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from cascade.compiler.backend.wiring.context import WiringContext
from cascade.compiler.backend.wiring.protocol import WiringPolicy


class ParameterWiringPolicy(WiringPolicy):
    def setup_globals(self, ctx: WiringContext) -> None:  # pragma: no cover
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
                d_dep_id = f"dep.{source_ref}.to.{node_ir.current_node_instance_hash}.{input_key}"
                d_dep = PhysicsDataNode(id=d_dep_id, name=f"Dep({port_name})")
                ctx.wire.add_node(d_dep)

                # Source Stainer -> D_dep (Connect from output_default)
                ctx.wire.connect(
                    source_subgraph.stainer.id,
                    StainerSpec.output_default.name,
                    d_dep_id,
                    "in",
                )

                # D_dep -> Target Bleacher
                ctx.wire.connect(d_dep_id, "out", subgraph.bleacher.id, port_name)

            # Case B: Literal Value (Constant) - Direct Materialization Model
            else:
                # 1. D_const (DataNode holding the literal value)
                d_const_id = PhysicalIdGenerator.constant(
                    node_ir.current_node_instance_hash, input_key
                )
                d_const = PhysicsDataNode(
                    id=d_const_id,
                    name=f"Const({port_name})",
                    capacity=1,
                    initial_tokens=1,
                    initial_payload=source_ref,
                )
                ctx.wire.add_node(d_const)

                # 2. Wiring: D_const -> Bleacher
                # Note: This is a direct D -> F connection, which is valid in Bipartite graphs.
                # The Strategy layer will be responsible for materializing the literal value
                # into a Ref during the loading phase.
                ctx.wire.connect(d_const_id, "out", subgraph.bleacher.id, port_name)
