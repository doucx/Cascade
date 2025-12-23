简要回答：
`test_visualize.py` 失败是因为我们为节点添加了新的默认样式属性（`style`, `fillcolor`, `fontcolor`），但测试断言仍然在匹配旧的、简单的节点定义字符串。我将更新测试以匹配新的格式，并添加针对影子节点样式的测试用例。

## [WIP] fix(tests): 更新可视化测试以匹配新的样式定义

### 摘要头
`# [WIP] fix(tests): Update visualize tests to match new style definitions`

### 用户需求
1.  修复因 `cs.visualize` 输出格式变更（增加了默认样式属性）而导致的 `test_visualize_diamond_graph` 测试失败。
2.  在 `test_visualize.py` 中增加新的测试用例，专门验证静态分析路径（POTENTIAL 边和 Shadow Nodes）的样式是否符合预期（虚线、灰色、`potential` 标签）。

### 评论
这是一个典型的测试维护任务。当我们改进了输出格式以提升用户体验时，必须同步更新那些对输出字符串进行精确匹配的测试。更好的做法是使用正则表达式或更灵活的断言，但在 DOT 字符串测试中，包含所有属性的精确匹配更能确保生成的图是我们期望的样子。

### 目标
1.  更新 `test_visualize_diamond_graph` 中的断言字符串，使其包含 `style="rounded,filled", fillcolor=white, fontcolor=black` 等新属性。
2.  添加 `test_visualize_potential_path` 测试函数，验证影子节点的特殊样式。

### 基本原理
直接修改测试文件中的预期字符串。

### 标签
#intent/fix #intent/test #flow/ready #priority/medium #comp/sdk #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/visualizer #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 更新并扩展 `test_visualize.py`

我们将修改 `tests/sdk/tools/test_visualize.py`。
1.  **修复**: 更新 `test_visualize_diamond_graph` 中的断言，使其匹配包含默认样式属性的节点定义。
2.  **新增**: 添加 `test_visualize_potential_path`，构建一个包含 TCO 逻辑的工作流，并断言其生成的 DOT 字符串包含预期的样式（虚线、红色边、灰底节点）。

~~~~~act
write_file
tests/sdk/tools/test_visualize.py
~~~~~
~~~~~python
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

    dot_string = cs.visualize(r_d)

    # Basic structural checks
    assert dot_string.startswith("digraph CascadeWorkflow {")
    assert dot_string.endswith("}")
    assert 'rankdir="TB"' in dot_string

    # Check node definitions with new default styles
    # style="rounded,filled", fillcolor=white, fontcolor=black
    assert (
        f'"{r_a._uuid}" [label="t_a\\n(task)", shape=box, style="rounded,filled", fillcolor=white, fontcolor=black];'
        in dot_string
    )
    assert (
        f'"{r_b._uuid}" [label="t_b\\n(task)", shape=box, style="rounded,filled", fillcolor=white, fontcolor=black];'
        in dot_string
    )

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
    target = (
        t_main(data_in=data_source).run_if(cond).with_constraints(cpu=constraint_val)
    )

    dot_string = cs.visualize(target)

    # 1. Assert Data Edge (standard style)
    assert (
        f'"{data_source._uuid}" -> "{target._uuid}" [label="data_in"];' in dot_string
    )

    # 2. Assert Condition Edge (dashed, gray)
    expected_cond_edge = (
        f'"{cond._uuid}" -> "{target._uuid}" [style=dashed, color=gray, label="run_if"]'
    )
    assert expected_cond_edge in dot_string

    # 3. Assert Constraint Edge (dotted, purple)
    expected_constraint_edge = f'"{constraint_val._uuid}" -> "{target._uuid}" [style=dotted, color=purple, label="constraint: cpu"]'
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
    expected_node_style_part = 'style="dashed,filled", fillcolor=whitesmoke, fontcolor=gray50'
    assert expected_node_style_part in dot_string
    assert "(Potential)" in dot_string
~~~~~

### 下一步建议
运行测试。如果通过，提交整个变更（包括 `visualize.py` 的功能增强和测试修复）。这将是一个完整的交付物。
