from cascade.spec.ir.graph import NodeIR, ArgumentKind
from cascade.spec.physical.nodes import PhysicsDataNode
from cascade.spec.physical.dyad import LauncherNode, LanderNode
from cascade.spec.physical.topology import Channel
from cascade.spec.physical.ports import PortDef, PortRole
from cascade.spec.compiler.model import SubGraph
from cascade.spec.specs.dyad import LauncherSpec, LanderSpec
from cascade.reflection import PhysicalIdGenerator


class Expander:
    def expand_node(self, node_ir: NodeIR) -> SubGraph:
        subgraph = SubGraph()

        # 1. Generate IDs for all physical entities
        base_id = node_ir.current_node_instance_hash

        f_launch_id = PhysicalIdGenerator.launcher_node(base_id)
        d_result_id = PhysicalIdGenerator.result_data(base_id)
        f_land_id = PhysicalIdGenerator.lander_node(base_id)

        # 2. Create Launcher Node
        # Inputs = Task Args + Resource Constraints + Signals
        launcher_inputs = {}

        # 2.1 Static Args from Task Def
        for arg in node_ir.task.args:
            if arg.kind == ArgumentKind.VAR_POSITIONAL:
                continue
            launcher_inputs[arg.name] = PortDef(arg.name, PortRole.DATA, "Any")

        # 2.2 Dynamic Args from Inputs
        # Positional args are represented by their index as a string
        for i in range(len(node_ir.args)):
            input_key = str(i)
            if input_key not in launcher_inputs:
                launcher_inputs[input_key] = PortDef(input_key, PortRole.DATA, "Any")

        # Keyword args
        for input_key in node_ir.kwargs.keys():
            if input_key not in launcher_inputs:
                launcher_inputs[input_key] = PortDef(input_key, PortRole.DATA, "Any")

        # 2.3 Resource Grants (RESOURCE_REQUEST role)
        # Note: The Launcher receives the grant token as DATA/RESOURCE to hold it.
        # In StdLib, we use PortRole.RESOURCE to identify held resources.
        for res_name in node_ir.constraints.keys():
            port_name = f"res_{res_name}"
            launcher_inputs[port_name] = PortDef(
                port_name, PortRole.RESOURCE, "ResourceSlot"
            )

        # 2.4 Dependency Signals
        for dep_id in node_ir.dependencies:
            port_name = f"wait_for_{dep_id}"
            launcher_inputs[port_name] = PortDef(port_name, PortRole.SIGNAL, "Token")

        # 2.5 Condition
        if node_ir.condition:
            port_name = "condition"
            launcher_inputs[port_name] = PortDef(port_name, PortRole.SIGNAL, "Bool")

        # 2.6 Pulse (Always Available)
        # We always expose the pulse port. If this is an intermediate node, this port
        # might remain unwired. The Reactor will decide which ports to wait for based
        # on actual connections.
        pulse_name = LauncherSpec.pulse.name
        if pulse_name not in launcher_inputs:
            launcher_inputs[pulse_name] = PortDef(pulse_name, PortRole.SIGNAL)

        canonical_hash = node_ir.task.fingerprint["canonical_code_structure_hash"]

        f_launcher = LauncherNode(
            id=f_launch_id,
            name=f"Launch({node_ir.name})",
            input_ports=launcher_inputs,
            # Launcher only has observability output locally.
            # Data output is evaporated to the Queue.
            output_ports={
                "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY, "Event")
            },
            canonical_code_structure_hash=canonical_hash,
            reply_to_nid=d_result_id,
            arg_port_names=[str(i) for i in range(len(node_ir.args))],
            kwarg_port_names=set(node_ir.kwargs.keys()),
        )

        # 3. Create Result Data Node (The Landing Pad)
        d_result = PhysicsDataNode(id=d_result_id, name=f"Result({node_ir.name})")

        # 4. Create Lander Node
        # Outputs = Default + Error + Resource Returns + Obs
        lander_outputs = {
            "output_default": PortDef("output_default", PortRole.DATA, "Token"),
            "output_error": PortDef("output_error", PortRole.DATA, "Token"),
            "obs_output": PortDef("obs_output", PortRole.OBSERVABILITY, "Event"),
        }

        # 4.1 Resource Returns
        for res_name in node_ir.constraints.keys():
            port_name = f"res_{res_name}"
            # Role RESOURCE indicates this is a return path
            lander_outputs[port_name] = PortDef(
                port_name, PortRole.RESOURCE, "ResourceSlot"
            )

        f_lander = LanderNode(
            id=f_land_id,
            name=f"Land({node_ir.name})",
            input_ports={
                # Lander receives the raw result token
                LanderSpec.result_token.name: PortDef(
                    LanderSpec.result_token.name, PortRole.DATA, "Any"
                )
            },
            output_ports=lander_outputs,
        )

        # 5. Register Nodes
        subgraph.nodes = {
            f_launch_id: f_launcher,
            d_result_id: d_result,
            f_land_id: f_lander,
        }
        subgraph.launcher = f_launcher
        subgraph.lander = f_lander

        # 6. Internal Wiring
        # Only one physical connection inside the Dyad: D_result -> Lander
        subgraph.channels = [
            Channel(
                source_node_id=d_result_id,
                source_port="out",
                target_node_id=f_land_id,
                target_port=LanderSpec.result_token.name,
            )
        ]

        return subgraph
