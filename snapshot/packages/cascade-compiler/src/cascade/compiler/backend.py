from typing import List, Dict, Tuple, Any

from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, EdgeKind
from cascade.spec.blueprint import Blueprint, Call, MapCall, Register, Literal, Operand, JumpIfFalse
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
        self._nodes_map: Dict[str, NodeIR] = {n.id: n for n in graph.nodes}
        self._incoming_edges_map: Dict[str, List[EdgeIR]] = {}
        for edge in graph.edges:
            if edge.target_id not in self._incoming_edges_map:
                self._incoming_edges_map[edge.target_id] = []
            self._incoming_edges_map[edge.target_id].append(edge)

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

    def _process_node(self, node_id: str):
        node = self._nodes_map[node_id]

        # 1. Resolve Input Operands & Control Dependencies
        # We use a temporary dictionary to collect all inputs (args and kwargs)
        # and then split them based on keys (digit keys -> args, others -> kwargs)
        all_inputs: Dict[str, Operand] = {}
        control_dependency_reg: Any = None

        # 1a. From Literals
        for key, value in node.inputs.items():
            all_inputs[key] = Literal(value)

        # 1b. From Edges (Dependencies)
        incoming_edges = self._incoming_edges_map.get(node_id, [])
        for edge in incoming_edges:
            # The source node must have been processed in a previous stage,
            # so its output register must be in our map.
            source_register = self._node_output_registers.get(edge.source_id)
            if source_register is None:
                # This indicates a flaw in the ExecutionPlan or this compiler's logic
                raise RuntimeError(
                    f"Compiler Error: Dependency '{edge.source_id}' for node '{node_id}' "
                    "was not assigned a register before being used."
                )
            
            if edge.kind == EdgeKind.CONTROL:
                # We currently support only one control dependency per node for simplicity.
                # If multiple exist, they should ideally be combined (AND logic) in the graph structure.
                control_dependency_reg = source_register
            else:
                all_inputs[edge.target_arg] = source_register

        # 1c. Split into args and kwargs
        # We find keys that are digits "0", "1", ... and map them to the positional list
        args: List[Operand] = []
        kwargs: Dict[str, Operand] = {}
        
        # Determine max positional index
        max_arg_idx = -1
        for k in all_inputs.keys():
            if k.isdigit():
                max_arg_idx = max(max_arg_idx, int(k))
        
        # Pre-fill args list with None (or check for gaps)
        if max_arg_idx >= 0:
            args = [None] * (max_arg_idx + 1) # type: ignore

        for k, v in all_inputs.items():
            if k.isdigit():
                args[int(k)] = v
            else:
                kwargs[k] = v
        
        # Check for gaps in positional args
        if any(a is None for a in args):
             # This might happen if '0' and '2' are provided but '1' is missing.
             # For now, we assume the IR is well-formed or the function has defaults.
             # But Literal(None) would be safer than actual None.
             pass

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
                func=None,
                output=output_register,
                args=args,
                kwargs=kwargs,
                task_name=node.definition.name,
                structure_hash=structure_hash,
                # Note: Constraints on Map nodes are not yet propagated to MapCall.
            )
        else:
            instr = Call(
                func=None,  # The VM will need to resolve this later
                output=output_register,
                args=args,
                kwargs=kwargs,
                task_name=node.definition.name,
                structure_hash=structure_hash,
            )
        self._instructions.append(instr)