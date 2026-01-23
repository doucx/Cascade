from cascade.spec.ir.graph import NodeIR
from cascade.spec.physical.nodes import PhysicsDataNode
from ...expander import SubGraph
from cascade.reflection import PhysicalIdGenerator
from ..context import ExpansionContext
from cascade.spec.compiler.interfaces import ExpansionPolicy


class ParameterExpansionPolicy(ExpansionPolicy):
    def expand(
        self, ctx: ExpansionContext, node_ir: NodeIR, subgraph: SubGraph
    ) -> None:
        # Combine args and kwargs for unified processing
        all_inputs = {str(i): val for i, val in enumerate(node_ir.args)}
        all_inputs.update(node_ir.kwargs)

        for input_key, source_ref in all_inputs.items():
            # Resolve port name
            if input_key.isdigit():
                idx = int(input_key)
                port_name = (
                    node_ir.task.args[idx].name
                    if idx < len(node_ir.task.args)
                    else input_key
                )
            else:
                port_name = input_key

            # Case A: Dependency - Create intermediate D_dep node
            if isinstance(source_ref, str) and source_ref in ctx.subgraphs:
                d_dep_id = f"dep.{source_ref}.to.{node_ir.current_node_instance_hash}.{input_key}"
                d_dep = PhysicsDataNode(id=d_dep_id, name=f"Dep({port_name})")

                # Register the new node
                ctx.wire.add_node(d_dep)
                subgraph.nodes[d_dep.id] = d_dep
                subgraph.controls[f"dep_for_{input_key}"] = d_dep

            # Case B: Literal Value - Create D_const node
            else:
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

                # Register the new node
                ctx.wire.add_node(d_const)
                subgraph.nodes[d_const.id] = d_const
                subgraph.constants[input_key] = d_const
