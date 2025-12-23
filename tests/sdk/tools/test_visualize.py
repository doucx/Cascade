import cascade as cs
from cascade.spec.task import task


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

    # Check node definitions with new default styles
    # style="rounded,filled", fillcolor=white, fontcolor=black
    assert (
        f'"{node_a.id}" [label="t_a\\n(task)", shape=box, style="rounded,filled", fillcolor=white, fontcolor=black];'
        in dot_string
    )
    assert (
        f'"{node_b.id}" [label="t_b\\n(task)", shape=box, style="rounded,filled", fillcolor=white, fontcolor=black];'
        in dot_string
    )

    # Check data edge definitions
    assert f'"{node_a.id}" -> "{node_b.id}" [label="0"];' in dot_string
    assert f'"{node_c.id}" -> "{node_d.id}" [label="z"];' in dot_string


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
    assert f'"{node_ds.id}" -> "{node_target.id}" [label="data_in"];' in dot_string

    # 2. Assert Condition Edge (dashed, gray)
    expected_cond_edge = (
        f'"{node_cond.id}" -> "{node_target.id}" [style=dashed, color=gray, label="run_if"]'
    )
    assert expected_cond_edge in dot_string

    # 3. Assert Constraint Edge (dotted, purple)
    expected_constraint_edge = f'"{node_constraint.id}" -> "{node_target.id}" [style=dotted, color=purple, label="constraint: cpu"]'
    assert expected_constraint_edge in dot_string


def test_visualize_potential_path():
    """
    Tests that static analysis (TCO) paths are visualized with distinct styles.
    """

    @task
    def leaf_task():
        return "leaf"

    @task
    def orchestrator(x: int):
        if x > 0:
            return leaf_task()
        return "done"

    workflow = orchestrator(10)
    dot_string = cs.visualize(workflow)

    # 1. Check POTENTIAL Edge Style (Red, Dashed)
    # Since we can't predict the shadow node UUID easily without parsing,
    # we look for the edge definition substring which is unique enough.
    expected_edge_style = '[style=dashed, color="#d9534f", fontcolor="#d9534f", arrowhead=open, label="potential"]'
    assert expected_edge_style in dot_string

    # 2. Check Shadow Node Style (Dashed border, Gray fill, (Potential) label)
    # We expect a node with label containing "(Potential)" and special style
    expected_node_style_part = (
        'style="dashed,filled", fillcolor=whitesmoke, fontcolor=gray50'
    )
    assert expected_node_style_part in dot_string
    assert "(Potential)" in dot_string
