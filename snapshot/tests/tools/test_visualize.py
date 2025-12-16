import cascade as cs


def test_visualize_diamond_graph():
    """
    Tests that visualize() produces a correct DOT string for a diamond graph.
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

    dot_string = cs.visualize(r_d)

    # Basic structural checks
    assert dot_string.startswith("digraph CascadeWorkflow {")
    assert dot_string.endswith("}")
    assert 'rankdir="TB"' in dot_string

    # Check that all nodes are defined with correct labels and shapes
    assert f'"{r_a._uuid}" [label="t_a\\n(task)", shape=box];' in dot_string
    assert f'"{r_b._uuid}" [label="t_b\\n(task)", shape=box];' in dot_string
    assert f'"{r_c._uuid}" [label="t_c\\n(task)", shape=box];' in dot_string
    assert f'"{r_d._uuid}" [label="t_d\\n(task)", shape=box];' in dot_string

    # Check that all edges are defined with correct labels
    assert f'"{r_a._uuid}" -> "{r_b._uuid}" [label="0"];' in dot_string
    assert f'"{r_a._uuid}" -> "{r_c._uuid}" [label="0"];' in dot_string
    assert f'"{r_b._uuid}" -> "{r_d._uuid}" [label="0"];' in dot_string
    assert f'"{r_c._uuid}" -> "{r_d._uuid}" [label="z"];' in dot_string
