from typing import Any, Dict, List, Set, Optional
import json
from cascade.graph.build import build_graph
from cascade.graph.model import Node, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult


def to_lisp(target: Any, indent: int = 2) -> str:
    """
    Transpiles a Cascade computation graph into a Lisp (S-Expression) representation.
    
    It employs an "Auto-Inlining" strategy:
    - Nodes referenced only once are inlined directly into their parent expression: (f (g x))
    - Nodes referenced multiple times are lifted into a `let*` binding block.
    
    Args:
        target: The LazyResult to visualize.
        indent: Number of spaces for indentation.
    
    Returns:
        A string containing the formatted Lisp code.
    """
    graph, _ = build_graph(target)
    
    # 1. Analyze Topology & Reference Counts
    # We only count DATA edges as references that influence code structure.
    ref_counts: Dict[str, int] = {}
    consumers: Dict[str, List[str]] = {}  # node_id -> list of consumer_ids
    
    for node in graph.nodes:
        ref_counts[node.id] = 0
        consumers[node.id] = []

    for edge in graph.edges:
        if edge.edge_type == EdgeType.DATA:
            ref_counts[edge.source.id] += 1
            consumers[edge.source.id].append(edge.target.id)

    # 2. Identify "Let-Bindings" vs "Inline Expressions"
    # The target node is always the root expression.
    # Nodes with ref_count > 1 must be bound.
    # Nodes with ref_count == 1 are inlined (unless they are the root).
    # Nodes with ref_count == 0 are technically dead code (or side-effects), but we'll bind them if they exist.
    
    target_uuid = target._uuid if hasattr(target, "_uuid") else None
    
    # Determine the topological order for let* bindings
    # We use a simple Kahn's algorithm or similar, but simplified since we have the graph.
    # Actually, we need to visit nodes that are NOT inlined.
    
    # Set of nodes that MUST be explicitly bound (variables in let*)
    bound_nodes: Set[str] = set()
    for node in graph.nodes:
        # If referenced multiple times, OR it's a root (but not THE target root if it's the only thing),
        # OR it has 0 refs (side effect root).
        if ref_counts[node.id] > 1:
            bound_nodes.add(node.id)
    
    # Helper to convert Python primitives to Lisp string
    def py_to_lisp_literal(val: Any) -> str:
        if val is None:
            return "nil"
        if val is True:
            return "#t"
        if val is False:
            return "#f"
        if isinstance(val, str):
            return json.dumps(val) # Use json to handle escaping quotes
        if isinstance(val, (int, float)):
            return str(val)
        if isinstance(val, list):
            return "'(" + " ".join(py_to_lisp_literal(x) for x in val) + ")"
        if isinstance(val, dict):
            # Dict as alist-like or plist? Let's use pseudo-constructor
            items = [f":{k} {py_to_lisp_literal(v)}" for k, v in val.items()]
            return "(dict " + " ".join(items) + ")"
        return str(val)

    # Helper to format function names
    def format_name(name: str) -> str:
        # Convert snake_case to kebab-case
        return name.replace("_", "-")

    # Recursive generator
    memo_expr: Dict[str, str] = {}

    def generate_expr(node: Node) -> str:
        if node.id in memo_expr:
            return memo_expr[node.id]
        
        # 1. Prepare Arguments
        # We need to reconstruct args/kwargs from bindings AND edges
        # This is a simplified reconstruction. Ideally we'd use ArgumentResolver logic,
        # but here we just want a visual representation.
        
        # Merge bindings and edge dependencies
        merged_args = {}
        
        # Load literals
        for k, v in node.input_bindings.items():
            merged_args[k] = py_to_lisp_literal(v)
            
        # Load dependencies
        incoming_edges = [e for e in graph.edges if e.target.id == node.id and e.edge_type == EdgeType.DATA]
        for edge in incoming_edges:
            source_id = edge.source.id
            if source_id in bound_nodes:
                # Reference by variable name
                val_str = f"var-{source_id[:8]}" # Simple var name
            else:
                # Inline recursive call
                val_str = generate_expr(edge.source)
            
            merged_args[edge.arg_name] = val_str

        # Separate positional and keyword args
        pos_args = []
        kw_args = []
        
        indices = [int(k) for k in merged_args.keys() if k.isdigit()]
        indices.sort()
        
        for idx in indices:
            pos_args.append(merged_args[str(idx)])
        
        for k, v in merged_args.items():
            if not k.isdigit():
                kw_args.append(f":{k} {v}")

        # Construct S-Expression
        func_name = format_name(node.name)
        if node.node_type == "map":
            func_name = f"map {format_name(getattr(node.mapping_factory, 'name', 'unknown'))}"
        
        args_str = " ".join(pos_args + kw_args)
        if args_str:
            expr = f"({func_name} {args_str})"
        else:
            expr = f"({func_name})"
            
        memo_expr[node.id] = expr
        return expr

    # 3. Generate Let Bindings
    # We need to sort bound_nodes topologically to ensure dependencies are defined before use.
    # Since graph is a DAG, we can just iterate. But Graph.nodes order isn't strictly topological.
    # We rely on the recursion of generate_expr to build strings, but for let* order matters.
    # Simple topo sort for bound_nodes:
    
    sorted_bound_nodes = []
    visited = set()
    def topo_visit(nid):
        if nid in visited: return
        visited.add(nid)
        # Visit dependencies first
        for edge in graph.edges:
            if edge.target.id == nid and edge.edge_type == EdgeType.DATA:
                topo_visit(edge.source.id)
        if nid in bound_nodes:
            sorted_bound_nodes.append(nid)
            
    for node in graph.nodes:
        topo_visit(node.id)
        
    # 4. Final Assembly
    if not bound_nodes:
        # Pure Tree
        target_node = next(n for n in graph.nodes if n.id == target_uuid)
        return generate_expr(target_node)
    else:
        # DAG with let*
        lines = ["(let* ("]
        for nid in sorted_bound_nodes:
            node = next(n for n in graph.nodes if n.id == nid)
            var_name = f"var-{nid[:8]}"
            # Force generation of the expression (it might use other bound vars or inlined ones)
            # We temporarily remove it from bound_nodes map during generation to avoid self-ref? 
            # No, generate_expr handles dependency lookup.
            expr = generate_expr(node)
            lines.append(f"  ({var_name} {expr})")
        
        lines.append("  )")
        
        # The body is the target expression
        target_node = next(n for n in graph.nodes if n.id == target_uuid)
        if target_node.id in bound_nodes:
             lines.append(f"  var-{target_node.id[:8]}")
        else:
             lines.append(f"  {generate_expr(target_node)}")
             
        lines.append(")")
        return "\n".join(lines)