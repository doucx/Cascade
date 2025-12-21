import cascade as cs
from cascade.graph.build import build_graph


def test_build_linear_graph():
    @cs.task
    def t1():
        return 1

    @cs.task
    def t2(x):
        return x + 1

    r1 = t1()
    r2 = t2(r1)

    graph = build_graph(r2)

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1

    edge = graph.edges[0]
    assert edge.source.name == "t1"
    assert edge.target.name == "t2"
    assert edge.arg_name == "0"  # first positional arg


def test_build_graph_with_param_factory():
    """
    [V1.3 更新] 验证 cs.Param() 现在生成一个标准的任务节点，
    而不是旧版的 'param' 类型节点。
    """
    # 定义工作流
    param_node = cs.Param("x", default=1)

    @cs.task
    def process(val):
        return val + 1

    target = process(param_node)

    graph = build_graph(target)

    assert len(graph.nodes) == 2

    # 找到参数节点
    # 注意：我们不能再通过 node_type="param" 来查找了
    # 我们需要通过任务名称或 ID 查找
    p_node = next(n for n in graph.nodes if n.name == "_get_param_value")

    # 断言节点类型统一为 task
    assert p_node.node_type == "task"

    # 断言它包含正确的 literal_inputs (这是内部任务需要的参数)
    assert "name" in p_node.literal_inputs
    assert p_node.literal_inputs["name"] == "x"


def test_build_graph_with_env_factory():
    """验证 cs.Env() 生成标准任务节点。"""
    env_node = cs.Env("HOME")

    @cs.task
    def echo(val):
        return val

    target = echo(env_node)
    graph = build_graph(target)

    e_node = next(n for n in graph.nodes if n.name == "_get_env_var")
    assert e_node.node_type == "task"
    assert e_node.literal_inputs["name"] == "HOME"


def test_build_graph_with_nested_dependencies():
    """
    Validates that the GraphBuilder correctly discovers LazyResults
    nested inside lists and dictionaries.
    """
    @cs.task
    def t_a(): return "a"
    @cs.task
    def t_b(): return "b"
    @cs.task
    def t_c(): return "c"

    @cs.task
    def t_main(direct_dep, list_dep, dict_dep):
        return f"{direct_dep}-{list_dep}-{dict_dep}"

    # Create a workflow with nested dependencies
    target = t_main(t_c(), [t_a()], {"key": t_b()})

    graph = build_graph(target)

    # 4 nodes: t_a, t_b, t_c, and t_main
    assert len(graph.nodes) == 4
    # 3 edges: t_a->t_main, t_b->t_main, t_c->t_main
    assert len(graph.edges) == 3

    node_names = {n.name for n in graph.nodes}
    assert "t_a" in node_names
    assert "t_b" in node_names
    assert "t_c" in node_names
    assert "t_main" in node_names
