import cascade as cs


def test_visualize_diamond_graph():
    """
    Tests that visualize() produces a correct DOT string for a diamond graph with standard data edges.
    """

    @cs.task
    def t_a():
        return 1

    @cs.task
    def t_b(x):
        return x + 1

    @cs.task
    def t_c(x):
        return x * 2

    @cs.task
    def t_d(y, z):
        return y + z

    r_a = t_a()
    r_b = t_b(r_a)
    r_c = t_c(r_a)
    r_d = t_d(r_b, z=r_c)

    # Pre-build to get the instance map for stable IDs
    from cascade.graph.build import build_graph

    _, instance_map = build_graph(r_d)

    node_a = instance_map[r_a._uuid]
    node_b = instance_map[r_b._uuid]
    node_c = instance_map[r_c._uuid]
    node_d = instance_map[r_d._uuid]

    dot_string = cs.visualize(r_d)

    # Basic structural checks
    assert dot_string.startswith("digraph CascadeWorkflow {")
    assert dot_string.endswith("}")
    assert 'rankdir="TB"' in dot_string

    # Check node definitions with new simplified style
    assert f'"{node_a.structural_id}" [label="t_a\\n(task)", shape=box];' in dot_string
    assert f'"{node_b.structural_id}" [label="t_b\\n(task)", shape=box];' in dot_string

    # Check data edge definitions
    assert (
        f'"{node_a.structural_id}" -> "{node_b.structural_id}" [label="0"];'
        in dot_string
    )
    assert (
        f'"{node_c.structural_id}" -> "{node_d.structural_id}" [label="z"];'
        in dot_string
    )


def test_visualize_special_edge_types():
    """
    Tests that visualize() correctly styles edges for conditions and constraints.
    """

    @cs.task
    def t_condition():
        return True

    @cs.task
    def t_constraint_source():
        return 2

    @cs.task
    def t_main(data_in):
        return data_in

    # Create a workflow with all edge types
    cond = t_condition()
    constraint_val = t_constraint_source()
    data_source = cs.task(lambda: 1, name="data_source")()

    # Apply run_if and dynamic constraints
    target = (
        t_main(data_in=data_source).run_if(cond).with_constraints(cpu=constraint_val)
    )

    from cascade.graph.build import build_graph

    _, instance_map = build_graph(target)

    node_ds = instance_map[data_source._uuid]
    node_target = instance_map[target._uuid]
    node_cond = instance_map[cond._uuid]
    node_constraint = instance_map[constraint_val._uuid]

    dot_string = cs.visualize(target)

    # 1. Assert Data Edge (standard style)
    assert (
        f'"{node_ds.structural_id}" -> "{node_target.structural_id}" [label="data_in"];'
        in dot_string
    )

    # 2. Assert Condition Edge (dashed, gray)
    expected_cond_edge = f'"{node_cond.structural_id}" -> "{node_target.structural_id}" [style=dashed, color=gray, label="run_if"]'
    assert expected_cond_edge in dot_string

    # 3. Assert Constraint Edge (dotted, purple)
    expected_constraint_edge = f'"{node_constraint.structural_id}" -> "{node_target.structural_id}" [style=dotted, color=purple, label="constraint: cpu"]'
    assert expected_constraint_edge in dot_string


def test_visualize_iterative_jump_edge():
    """
    Tests that visualize() correctly renders an ITERATIVE_JUMP edge created via cs.bind.
    """

    @cs.task
    def state_machine(data: int):
        if data < 3:
            # Signal a jump to the "next" state
            return cs.Jump(target_key="next", data=data + 1)
        # Signal a normal exit
        return "done"

    # The selector maps jump keys to their target LazyResults
    selector = cs.select_jump(
        {
            "next": state_machine,  # A jump to "next" re-invokes the same task
            None: None,  # A normal return value exits the loop
        }
    )

    # Initial call to the task, starting the state machine
    start_node = state_machine(0)

    # Statically bind the task's jump signals to the selector
    cs.bind(start_node, selector)

    # Build the graph to get the stable node ID for assertion
    from cascade.graph.build import build_graph

    _, instance_map = build_graph(start_node)
    node_id = instance_map[start_node._uuid].structural_id

    dot_string = cs.visualize(start_node)

    # Assert that a self-referencing, specially styled "jump" edge exists
    expected_edge = (
        f'"{node_id}" -> "{node_id}" [style=bold, color=blue, label="jump"]'
    )
    assert expected_edge in dot_string
