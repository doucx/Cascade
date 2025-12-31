Excellent strategic insight. You are absolutely correct.

The current IR design, where `NodeIR.inputs` is a single dictionary and `EdgeIR.target_arg` is a simple string, is a remnant of the MVP phase. It forces the `Backend` to perform "magic" by guessing the argument type based on `key.isdigit()`. This is a weak contract and a form of technical debt.

Enriching the IR to be more explicit is the right architectural decision. It shifts the complexity to the `Frontend`—the component that has the most context about the original `LazyResult`—and allows the `Backend` to become a simpler, more robust, and less "clever" consumer of a well-defined structure.

I will now generate a plan to implement this refactoring.

## [WIP] refactor: Enrich IR to simplify Backend argument compilation

### 用户需求
Refactor the Intermediate Representation (`GraphIR`) to explicitly distinguish between positional and keyword arguments for both literals and dependencies. This will simplify the `Backend`'s logic by removing the need for string-based guesswork.

### 评论
This is a significant architectural improvement that strengthens the contract between the compiler's `Frontend` and `Backend`. By making the IR more expressive, we eliminate a "code smell" (`key.isdigit()`) and make the entire compilation pipeline more robust and easier to maintain.

### 目标
1.  **Spec**: Modify `NodeIR` to have separate `literal_args` and `literal_kwargs`.
2.  **Spec**: Modify `EdgeIR` to explicitly state whether a dependency is `POSITIONAL` (with an index) or `KEYWORD` (with a name).
3.  **Compiler**: Update the `Frontend` to generate this new, richer IR structure from `LazyResult`.
4.  **Compiler**: Simplify the `Backend` to consume the new IR without ambiguity.
5.  **Tests**: Update all affected tests to reflect the new IR structure.

### 基本原理
The component responsible for parsing the user-facing API (`Frontend`) should bear the complexity of understanding its structure. The resulting IR should be an unambiguous, machine-readable contract. The component that consumes this IR (`Backend`) should then be as simple as possible, merely translating this explicit structure into another form (`Blueprint`) without needing to infer intent.

### 标签
#intent/refine #flow/ready #priority/high #comp/spec #comp/compiler #scope/core #task/domain/core #task/object/ir-contract #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: Refactor Spec - Enrich `NodeIR` and `EdgeIR`

First, we'll update the data structures in `cascade.spec.ir.models`.

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python.old
class EdgeKind(str, Enum):
    DATA = "DATA"  # Standard data dependency
    CONTROL = "CONTROL"  # Conditional execution (run_if)


class ArgumentKind(str, Enum):
~~~~~
~~~~~python.new
class EdgeKind(str, Enum):
    DATA = "DATA"  # Standard data dependency
    CONTROL = "CONTROL"  # Conditional execution (run_if)


class InputKind(str, Enum):
    """Specifies the kind of input an edge provides to a target node."""
    POSITIONAL = "POSITIONAL"
    KEYWORD = "KEYWORD"


class ArgumentKind(str, Enum):
~~~~~

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/ir/models.py
~~~~~
~~~~~python.old
@dataclass
class NodeIR:
    id: str
    definition: TaskDef
    inputs: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeIR:
    source_id: str
    target_id: str
    target_arg: str
    kind: EdgeKind = EdgeKind.DATA
~~~~~
~~~~~python.new
@dataclass
class NodeIR:
    id: str
    definition: TaskDef
    # Static literal inputs are now separated
    literal_args: List[Any] = field(default_factory=list)
    literal_kwargs: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeIR:
    source_id: str
    target_id: str
    kind: EdgeKind = EdgeKind.DATA
    
    # The target argument is now explicitly defined
    target_arg_kind: Optional[InputKind] = None
    target_arg_name: Optional[str] = None
    target_arg_index: Optional[int] = None
~~~~~

#### Acts 2: Update Compiler `Frontend` to Produce the New IR

Now, we modify the `Frontend` to correctly populate these new, structured fields.

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python.old
        if node_id not in self.nodes:
            literal_inputs = {
                str(i): arg for i, arg in enumerate(obj.args) if not isinstance(arg, (LazyResult, MappedLazyResult))
            }
            literal_inputs.update(
                {k: val for k, val in obj.kwargs.items() if not isinstance(val, (LazyResult, MappedLazyResult))}
            )

            node = NodeIR(id=node_id, definition=task_def, inputs=literal_inputs)
            self.nodes[node_id] = node

        for i, arg in enumerate(obj.args):
            if isinstance(arg, (LazyResult, MappedLazyResult)):
                self.edges.append(EdgeIR(
                    source_id=dep_shims[arg._uuid].structural_id,
                    target_id=node_id,
                    target_arg=str(i)
                ))

        for k, val in obj.kwargs.items():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                self.edges.append(EdgeIR(
                    source_id=dep_shims[val._uuid].structural_id,
                    target_id=node_id,
                    target_arg=k
                ))
~~~~~
~~~~~python.new
        if node_id not in self.nodes:
            literal_args = [
                arg for arg in obj.args if not isinstance(arg, (LazyResult, MappedLazyResult))
            ]
            literal_kwargs = {
                k: val for k, val in obj.kwargs.items() if not isinstance(val, (LazyResult, MappedLazyResult))
            }

            node = NodeIR(
                id=node_id,
                definition=task_def,
                literal_args=literal_args,
                literal_kwargs=literal_kwargs
            )
            self.nodes[node_id] = node

        for i, arg in enumerate(obj.args):
            if isinstance(arg, (LazyResult, MappedLazyResult)):
                self.edges.append(EdgeIR(
                    source_id=dep_shims[arg._uuid].structural_id,
                    target_id=node_id,
                    target_arg_kind=EdgeKind.DATA,
                    target_arg_index=i,
                ))

        for k, val in obj.kwargs.items():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                self.edges.append(EdgeIR(
                    source_id=dep_shims[val._uuid].structural_id,
                    target_id=node_id,
                    target_arg_kind=EdgeKind.DATA,
                    target_arg_name=k,
                ))
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python.old
        if obj._condition:
            self.edges.append(EdgeIR(
                source_id=dep_shims[obj._condition._uuid].structural_id,
                target_id=node_id,
                target_arg="_condition",
                kind=EdgeKind.CONTROL
            ))
~~~~~
~~~~~python.new
        if obj._condition:
            self.edges.append(EdgeIR(
                source_id=dep_shims[obj._condition._uuid].structural_id,
                target_id=node_id,
                kind=EdgeKind.CONTROL
            ))
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/frontend.py
~~~~~
~~~~~python.old
        if node_id not in self.nodes:
            literal_inputs = {
                k: val for k, val in obj.mapping_kwargs.items() if not isinstance(val, (LazyResult, MappedLazyResult))
            }
            node = NodeIR(
                id=node_id,
                definition=task_def,
                inputs=literal_inputs,
                meta={"is_map": True}
            )
            self.nodes[node_id] = node

        for k, val in obj.mapping_kwargs.items():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                self.edges.append(EdgeIR(
                    source_id=dep_shims[val._uuid].structural_id,
                    target_id=node_id,
                    target_arg=k
                ))
~~~~~
~~~~~python.new
        if node_id not in self.nodes:
            # Map nodes only have kwargs
            literal_kwargs = {
                k: val for k, val in obj.mapping_kwargs.items() if not isinstance(val, (LazyResult, MappedLazyResult))
            }
            node = NodeIR(
                id=node_id,
                definition=task_def,
                literal_kwargs=literal_kwargs,
                meta={"is_map": True}
            )
            self.nodes[node_id] = node

        for k, val in obj.mapping_kwargs.items():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                self.edges.append(EdgeIR(
                    source_id=dep_shims[val._uuid].structural_id,
                    target_id=node_id,
                    target_arg_kind=EdgeKind.DATA,
                    target_arg_name=k,
                ))
~~~~~

#### Acts 3: Simplify Compiler `Backend` to Consume the New IR

This is the payoff. The `Backend` logic becomes much cleaner and more robust.

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, EdgeKind
~~~~~
~~~~~python.new
from cascade.spec.ir.models import GraphIR, NodeIR, EdgeIR, EdgeKind, InputKind
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/src/cascade/compiler/backend.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
    def _process_node(self, node_id: str):
        node = self._nodes_map[node_id]

        # 1. Resolve Input Operands & Control Dependencies
        args: List[Optional[Operand]] = [Literal(val) for val in node.literal_args]
        kwargs: Dict[str, Operand] = {k: Literal(v) for k, v in node.literal_kwargs.items()}
        control_dependency_reg: Any = None

        # Process Edges (Dependencies)
        incoming_edges = self._incoming_edges_map.get(node_id, [])
        for edge in incoming_edges:
            source_register = self._node_output_registers.get(edge.source_id)
            if source_register is None:
                raise RuntimeError(
                    f"Compiler Error: Dependency '{edge.source_id}' for node '{node_id}' "
                    "was not assigned a register before being used."
                )
            
            if edge.kind == EdgeKind.CONTROL:
                control_dependency_reg = source_register
            elif edge.target_arg_kind == InputKind.POSITIONAL and edge.target_arg_index is not None:
                idx = edge.target_arg_index
                # Ensure args list is long enough
                while len(args) <= idx:
                    args.append(None)
                args[idx] = source_register
            elif edge.target_arg_kind == InputKind.KEYWORD and edge.target_arg_name is not None:
                kwargs[edge.target_arg_name] = source_register

        # Final cleanup for args list in case of gaps (should be rare)
        final_args: List[Operand] = [op for op in args if op is not None]
~~~~~

#### Acts 4: Update Tests

Finally, we update the tests to assert against the new, richer IR structure.

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_frontend.py
~~~~~
~~~~~python.old
    edge = ir.edges[0]
    
    # Verify edge connectivity
    target_node = next(n for n in ir.nodes if n.definition.name == "consumer")
    source_node = next(n for n in ir.nodes if n.definition.name == "producer")
    
    assert edge.source_id == source_node.id
    assert edge.target_id == target_node.id
    assert edge.target_arg == "val"
~~~~~
~~~~~python.new
    edge = ir.edges[0]
    
    # Verify edge connectivity
    target_node = next(n for n in ir.nodes if n.definition.name == "consumer")
    source_node = next(n for n in ir.nodes if n.definition.name == "producer")
    
    from cascade.spec.ir.models import InputKind
    assert edge.source_id == source_node.id
    assert edge.target_id == target_node.id
    assert edge.target_arg_kind == InputKind.KEYWORD
    assert edge.target_arg_name == "val"
~~~~~

~~~~~act
patch_file
packages/cascade-compiler/tests/unit/test_frontend.py
~~~~~
~~~~~python.old
    # We check for the new EdgeKind
    from cascade.spec.ir.models import EdgeKind
    assert edge.kind == EdgeKind.CONTROL
    assert edge.target_arg == "_condition"  # Internal convention, or explicit field
~~~~~
~~~~~python.new
    # We check for the new EdgeKind
    from cascade.spec.ir.models import EdgeKind
    assert edge.kind == EdgeKind.CONTROL
    assert edge.target_arg_name is None
    assert edge.target_arg_index is None
~~~~~
