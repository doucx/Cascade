import json
from typing import Any, Dict, List, Set
from cascade.runtime.graph.model import Graph, Node, Edge, EdgeType
from cascade.runtime.graph.build import build_graph
from cascade.spec.dsl.fluent import LazyResult


class LispTranspiler:
    def __init__(self, graph: Graph, instance_map: Dict[str, Node]):
        self.graph = graph
        self.instance_map = instance_map
        self.ref_counts: Dict[str, int] = {}
        self.shared_nodes: Set[str] = set()
        self.node_var_names: Dict[str, str] = {}
        # Tracks nodes that have been emitted in the let* block
        self.generated_bindings: Set[str] = set()

        self._analyze()

    def _analyze(self):
        # 1. Initialize counts
        for node in self.graph.nodes:
            self.ref_counts[node.current_node_instance_hash] = 0

        # 2. Count references (Source is dependency, Target is consumer)
        for edge in self.graph.edges:
            if edge.edge_type not in (EdgeType.IMPLICIT, EdgeType.POTENTIAL):
                self.ref_counts[edge.source.current_node_instance_hash] += 1

        # 3. Identify shared nodes and assign names
        name_counts = {}
        # Sort nodes by ID for deterministic naming
        sorted_nodes = sorted(
            self.graph.nodes, key=lambda n: n.current_node_instance_hash
        )

        for node in sorted_nodes:
            # Nodes referenced more than once OR nodes that are used as Router selectors
            # (Router selectors are tricky to inline cleanly inside a case statement header)
            is_router_selector = any(
                e.router
                and e.router.selector._uuid in self.instance_map
                and self.instance_map[
                    e.router.selector._uuid
                ].current_node_instance_hash
                == node.current_node_instance_hash
                for e in self.graph.edges
            )

            if (
                self.ref_counts[node.current_node_instance_hash] > 1
                or is_router_selector
            ):
                self.shared_nodes.add(node.current_node_instance_hash)
                base_name = self._sanitize_name(node.name)
                count = name_counts.get(base_name, 0) + 1
                name_counts[base_name] = count

                if count == 1:
                    self.node_var_names[node.current_node_instance_hash] = base_name
                else:
                    self.node_var_names[node.current_node_instance_hash] = (
                        f"{base_name}-{count}"
                    )

    def _sanitize_name(self, name: str) -> str:
        if not name:
            return "anon"
        return name.lower().replace("_", "-").replace(" ", "-")

    def transpile(self, target_node: Node) -> str:
        # 1. Identify relevant shared nodes (transitive dependencies of target)
        deps = self._get_transitive_deps(target_node)
        shared_in_scope = [
            n for n in deps if n.current_node_instance_hash in self.shared_nodes
        ]

        # 2. Topological Sort for let* order
        sorted_shared = self._topo_sort(shared_in_scope)

        if not sorted_shared:
            return self._render_expr(target_node)

        # 3. Generate let* block
        lines = ["(let* ("]
        for node in sorted_shared:
            var_name = self.node_var_names[node.current_node_instance_hash]
            # Mark as generated so subsequent references use the var name
            self.generated_bindings.add(node.current_node_instance_hash)
            expr = self._render_expr(node)
            lines.append(f"  ({var_name} {expr})")

        lines.append(")")
        lines.append(f"  {self._render_expr(target_node)})")

        return "\n".join(lines)

    def _render_expr(self, node: Node) -> str:
        parts = []

        from cascade.runtime.graph.model import MapNode

        # Function Name
        if isinstance(node, MapNode):
            func_name = self._sanitize_name(node.definition.name)
            parts.append(f"map {func_name}")
        elif node.name == "_get_param_value":
            # Correctly identify Param nodes by their callable's name, not their class.
            # The parameter name is reliably stored in input_bindings.
            p_name = node.input_bindings.get("name", "unknown")
            return f'(param "{p_name}")'
        else:
            func_name = self._sanitize_name(node.name)
            parts.append(func_name)

        # Merge Bindings and Edges
        # We need to reconstruct the argument list.
        # Strategy: Iterate through known bindings and incoming edges.

        # 1. Positional Arguments
        max_pos = -1
        # Check bindings
        for k in node.input_bindings:
            if k.isdigit():
                max_pos = max(max_pos, int(k))

        # Check edges
        incoming_edges = [
            e
            for e in self.graph.edges
            if e.target.current_node_instance_hash == node.current_node_instance_hash
            and e.edge_type == EdgeType.DATA
        ]
        edge_map = {e.arg_name: e for e in incoming_edges}

        for k in edge_map:
            if k.isdigit():
                max_pos = max(max_pos, int(k))

        for i in range(max_pos + 1):
            s_i = str(i)
            if s_i in edge_map:
                parts.append(self._render_edge_ref(edge_map[s_i]))
            elif s_i in node.input_bindings:
                parts.append(self._to_lisp_literal(node.input_bindings[s_i]))
            else:
                parts.append("nil")

        # 2. Keyword Arguments
        kw_keys = set()
        for k in node.input_bindings:
            if not k.isdigit():
                kw_keys.add(k)
        for k in edge_map:
            if not k.isdigit() and not k.startswith("_"):
                kw_keys.add(k)

        for k in sorted(kw_keys):
            parts.append(f":{self._sanitize_name(k)}")
            if k in edge_map:
                parts.append(self._render_edge_ref(edge_map[k]))
            elif k in node.input_bindings:
                parts.append(self._to_lisp_literal(node.input_bindings[k]))
            else:
                parts.append("nil")

        # 3. Conditions (run_if)
        cond_edges = [
            e
            for e in self.graph.edges
            if e.target.current_node_instance_hash == node.current_node_instance_hash
            and e.edge_type == EdgeType.CONDITION
        ]
        if cond_edges:
            parts.append(":run-if")
            parts.append(self._render_edge_ref(cond_edges[0]))

        return f"({' '.join(parts)})"

    def _render_edge_ref(self, edge: Edge) -> str:
        if edge.router:
            # Generate (case selector (val expr) ...)
            selector_node = edge.source
            selector_expr = self._resolve_node_ref(selector_node)

            branches = []
            # Sort routes by key for deterministic output
            # Convert keys to string for sorting if necessary
            sorted_routes = sorted(
                edge.router.routes.items(), key=lambda item: str(item[0])
            )

            for key, route_lr in sorted_routes:
                route_uuid = route_lr._uuid
                if route_uuid in self.instance_map:
                    route_node = self.instance_map[route_uuid]
                    branch_expr = self._resolve_node_ref(route_node)
                else:
                    branch_expr = "<unknown-node>"

                key_lit = self._to_lisp_literal(key)
                branches.append(f"(({key_lit}) {branch_expr})")

            return f"(case {selector_expr} {' '.join(branches)})"
        else:
            return self._resolve_node_ref(edge.source)

    def _resolve_node_ref(self, node: Node) -> str:
        # If this node is shared AND we have already generated a binding for it
        # (or are about to in the let* block), use the variable name.
        if node.current_node_instance_hash in self.shared_nodes:
            return self.node_var_names[node.current_node_instance_hash]
        else:
            # Inline it
            return self._render_expr(node)

    def _to_lisp_literal(self, val: Any) -> str:
        if val is None:
            return "nil"
        if val is True:
            return "#t"
        if val is False:
            return "#f"
        if isinstance(val, str):
            return json.dumps(val)
        if isinstance(val, (int, float)):
            return str(val)
        if isinstance(val, list):
            return "'(" + " ".join(self._to_lisp_literal(x) for x in val) + ")"
        if isinstance(val, dict):
            # Alist ((k . v) ...)
            items = [
                f"({self._to_lisp_literal(k)} . {self._to_lisp_literal(v)})"
                for k, v in val.items()
            ]
            return "'(" + " ".join(items) + ")"
        return str(val)

    def _get_transitive_deps(self, root: Node) -> Set[Node]:
        visited = set()
        queue = [root]
        visited.add(root)

        relevant_nodes = set()
        relevant_nodes.add(root)

        while queue:
            n = queue.pop(0)
            # Find incoming edges
            incoming = [
                e.source
                for e in self.graph.edges
                if e.target.current_node_instance_hash == n.current_node_instance_hash
            ]
            for source in incoming:
                if source not in visited:
                    visited.add(source)
                    relevant_nodes.add(source)
                    queue.append(source)
        return relevant_nodes

    def _topo_sort(self, nodes: List[Node]) -> List[Node]:
        node_set = {n.current_node_instance_hash for n in nodes}
        adj = {n.current_node_instance_hash: set() for n in nodes}

        # Build graph restricted to 'nodes'
        for edge in self.graph.edges:
            if (
                edge.target.current_node_instance_hash in node_set
                and edge.source.current_node_instance_hash in node_set
            ):
                # Target depends on Source
                adj[edge.target.current_node_instance_hash].add(
                    edge.source.current_node_instance_hash
                )

        result = []
        visited = set()
        temp_mark = set()

        def visit(n_id):
            if n_id in temp_mark:
                return  # Cycle detected, ignore
            if n_id in visited:
                return

            temp_mark.add(n_id)
            for dep_id in sorted(adj[n_id]):  # Sort for deterministic output
                visit(dep_id)
            temp_mark.remove(n_id)
            visited.add(n_id)
            result.append(n_id)

        # Sort input nodes for deterministic start order
        for n in sorted(nodes, key=lambda x: x.current_node_instance_hash):
            visit(n.current_node_instance_hash)

        # result is [Deepest Dep, ..., Root]
        id_map = {n.current_node_instance_hash: n for n in nodes}
        return [id_map[nid] for nid in result]


def to_lisp(target: Any) -> str:
    if not isinstance(target, LazyResult):
        raise TypeError(f"Target must be a LazyResult, got {type(target)}")

    graph, instance_map, _ = build_graph(target)
    transpiler = LispTranspiler(graph, instance_map)

    # Locate the root node corresponding to the target instance
    if target._uuid not in instance_map:
        raise RuntimeError("Target node not found in built graph")

    root = instance_map[target._uuid]
    return transpiler.transpile(root)
