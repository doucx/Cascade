from typing import List, Dict, Tuple, Any

from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, EdgeKind, InjectionIR
from cascade.spec.blueprint import (
    Blueprint, Call, MapCall, Register, Literal, Operand, JumpIfFalse, ResourceOperand
)
from .optimizer import ExecutionPlan


class Backend:
    """
    Compiler Backend (Codegen): Transforms a scheduled IR into a linear Blueprint.
    """

    @staticmethod
    def compile(graph: GraphIR, plan: ExecutionPlan) -> Blueprint:
        builder = _BlueprintBuilder(graph, plan)
        return builder.build()


class _BlueprintBuilder:
    def __init__(self, graph: GraphIR, plan: ExecutionPlan):
        self._graph = graph
        self._plan = plan
        self._instructions: List[Call] = []
        self._register_counter = 0

        # The "Symbol Table" for register allocation
        self._node_output_registers: Dict[str, Register] = {}
        
        # Fast lookups
        self._nodes_map: Dict[str, NodeIR] = {n.current_node_instance_hash: n for n in graph.nodes}
        self._incoming_edges_map: Dict[str, List[EdgeIR]] = {}
        for edge in graph.edges:
            if edge.target_node_instance_hash not in self._incoming_edges_map:
                self._incoming_edges_map[edge.target_node_instance_hash] = []
            self._incoming_edges_map[edge.target_node_instance_hash].append(edge)

    def _allocate_register(self) -> Register:
        reg = Register(self._register_counter)
        self._register_counter += 1
        return reg

    def build(self) -> Blueprint:
        for stage in self._plan:
            for node_id in stage:
                self._process_node(node_id)
        
        return Blueprint(
            instructions=self._instructions,
            register_count=self._register_counter
        )

    def _convert_to_operand(self, val: Any) -> Operand:
        if isinstance(val, InjectionIR):
            return ResourceOperand(name=val.resource_name)
        return Literal(val)

    def _process_node(self, node_id: str):
        node = self._nodes_map[node_id]

        # 1. Resolve Input Operands & Control Dependencies
        args: List[Operand] = [self._convert_to_operand(val) for val in node.args]
        kwargs: Dict[str, Operand] = {k: self._convert_to_operand(v) for k, v in node.kwargs.items()}
        control_dependency_reg: Any = None

        # 1a. Overlay dependencies from Edges
        incoming_edges = self._incoming_edges_map.get(node_id, [])
        for edge in incoming_edges:
            source_register = self._node_output_registers.get(edge.source_node_instance_hash)
            if source_register is None:
                raise RuntimeError(
                    f"Compiler Error: Dependency '{edge.source_node_instance_hash}' for node '{node_id}' "
                    "was not assigned a register before being used."
                )

            if edge.kind == EdgeKind.CONTROL:
                control_dependency_reg = source_register
            else:
                # Dependency can be positional or keyword
                if edge.target_arg.isdigit():
                    idx = int(edge.target_arg)
                    # Grow args list if necessary
                    while len(args) <= idx:
                        args.append(None) # type: ignore
                    args[idx] = source_register
                else:
                    kwargs[edge.target_arg] = source_register

        # 2. Emit Control Flow Guard (if needed)
        if control_dependency_reg:
            # JumpIfFalse offset=2 means skip the next instruction (which is length 1)
            # Layout: [JumpIfFalse, Call]
            # If false, PC += 2. From index i, lands on i+2 (after Call).
            jump = JumpIfFalse(condition=control_dependency_reg, offset=2)
            self._instructions.append(jump)

        # 3. Allocate Output Register for this node
        output_register = self._allocate_register()
        self._node_output_registers[node_id] = output_register

        # 3. Create Instruction
        # For now, we assume the IR definition's callable is magically available.
        # A real implementation would need a way to resolve/load the actual function.
        # For testing, the function itself isn't invoked, so we can use a placeholder.
        
        # We also pass task name for better observability in the VM
        structure_hash = node.definition.fingerprint["current_code_structure_hash"]

        if node.meta.get("is_map"):
            instr = MapCall(
                output=output_register,
                args=args,
                kwargs=kwargs,
                task_name=node.definition.name,
                structure_hash=structure_hash,
                policy=node.policy, 
            )
        else:
            instr = Call(
                output=output_register,
                args=args,
                kwargs=kwargs,
                task_name=node.definition.name,
                structure_hash=structure_hash,
                policy=node.policy,
            )
        self._instructions.append(instr)