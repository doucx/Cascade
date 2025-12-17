import cascade as cs
from cascade.graph.model import EdgeType


def test_visualize_diamond_graph():
    """
    Tests that visualize() produces a correct DOT string for a diamond graph with standard data edges.
    """
    @cs.task
    def t_a(): return 1

    @cs.task
    def t_b(x): return x + 1

    @cs.task
    def t_c(x): return x * 2

    @cs.task
    def t_d(y, z): return y + z

    r_a = t_a()
    r_b = t_b(r_a)
    r_c = t_c(r_a)
    r_d = t_d(r_b, z=r_c)

    dot_string = cs.visualize(r_d)

    # Basic structural checks
    assert dot_string.startswith("digraph CascadeWorkflow {")
    assert dot_string.endswith("}")
    assert 'rankdir="TB"' in dot_string

    # Check node definitions
    assert f'"{r_a._uuid}" [label="t_a\\n(task)", shape=box];' in dot_string
    assert f'"{r_b._uuid}" [label="t_b\\n(task)", shape=box];' in dot_string

    # Check data edge definitions
    assert f'"{r_a._uuid}" -> "{r_b._uuid}" [label="0"];' in dot_string
    assert f'"{r_c._uuid}" -> "{r_d._uuid}" [label="z"];' in dot_string


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
    target = t_main(
        data_in=data_source
    ).run_if(
        cond
    ).with_constraints(
        cpu=constraint_val
    )

    dot_string = cs.visualize(target)

    # 1. Assert Data Edge (standard style)
    assert f'"{data_source._uuid}" -> "{target._uuid}" [label="data_in"];' in dot_string

    # 2. Assert Condition Edge (dashed, gray)
    expected_cond_edge = f'"{cond._uuid}" -> "{target._uuid}" [style=dashed, color=gray, label="run_if"]'
    assert expected_cond_edge in dot_string

    # 3. Assert Constraint Edge (dotted, purple)
    expected_constraint_edge = f'"{constraint_val._uuid}" -> "{target._uuid}" [style=dotted, color=purple, label="constraint: cpu"]'
    assert expected_constraint_edge in dot_string