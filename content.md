您是对的，我的清理工作不够彻底。我移除了 `visualize.py` 中的样式逻辑，但忘记更新依赖这些样式的测试，并且遗漏了一个现在已完全过时的测试。这是一个典型的“只改代码，不改测试”的错误。

我们将立即修复这个问题，使测试套件恢复到 GREEN 状态。

## [WIP] fix(tests): 修正并清理 visualize 工具的测试用例

### 错误分析
测试失败有两个原因，都与上一步的清理不彻底有关：
1.  **`test_visualize_diamond_graph`**: 此测试失败是因为它的断言仍然期望节点定义中包含旧的、复杂的样式属性（`style`, `fillcolor` 等）。而这些属性已在 `visualize.py` 的重构中被正确地移除了。测试需要更新以匹配新的、更简洁的 DOT 输出格式。
2.  **`test_visualize_potential_path`**: 此测试失败是因为它断言了 `POTENTIAL` 边的存在，这是一个由已被删除的 `ast_analyzer.py` 生成的特性。这个测试现在已经完全过时，必须被删除。

### 用户需求
清理与 `visualize` 工具相关的剩余测试失败，确保测试套件能够完全通过，并准确反映在移除隐式 TCO 功能后的代码库状态。

### 评论
这是完成隐式 TCO 清理工作的最后一步。一个干净、全绿的测试套件是确认我们架构重构成功的基础。通过这次修复，我们将确保测试代码与生产代码的行为完全同步。

### 目标
1.  **更新** `test_visualize_diamond_graph`，使其断言新的、不含复杂样式的节点格式。
2.  **删除** `test_visualize_potential_path`，因为它测试的是一个不再存在的功能。

### 基本原理
测试必须与实现保持一致。由于 `visualize` 工具的输出已经被简化，并且静态分析功能已被移除，相应的测试必须被同步更新和删除，以维护一个健康且有意义的测试套件。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #comp/sdk #concept/cleanup #scope/core #ai/instruct #task/domain/testing #task/object/test-suite #task/action/cleanup #task/state/continue

---

### Script

#### Acts 1: 修正并清理 visualize 测试

我们将使用一个 `patch_file` 操作来同时更新 `test_visualize_diamond_graph` 并删除 `test_visualize_potential_path`。

~~~~~act
patch_file
tests/sdk/tools/test_visualize.py
~~~~~
~~~~~python
    # Check node definitions with new default styles
    # style="rounded,filled", fillcolor=white, fontcolor=black
    assert (
        f'"{node_a.structural_id}" [label="t_a\\n(task)", shape=box, style="rounded,filled", fillcolor=white, fontcolor=black];'
        in dot_string
    )
    assert (
        f'"{node_b.structural_id}" [label="t_b\\n(task)", shape=box, style="rounded,filled", fillcolor=white, fontcolor=black];'
        in dot_string
    )

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
~~~~~
~~~~~python
    # Check node definitions with new simplified style
    assert (
        f'"{node_a.structural_id}" [label="t_a\\n(task)", shape=box];' in dot_string
    )
    assert (
        f'"{node_b.structural_id}" [label="t_b\\n(task)", shape=box];' in dot_string
    )

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
~~~~~

### 下一步建议
我们已经完成了最后的清理。现在，整个测试套件应该能够完全通过。

这标志着我们成功地完成了架构演进路线图中的**阶段一（引入新原语）**和**阶段三（清理旧体系）**。我们已经拥有了一个更简单、更健壮、完全基于显式控制流的内核。

下一步，我们将正式进入 **阶段四：`[Optimization]` - 建立统一的双层身份体系**。我将准备一个计划，开始重构 `HashingService` 并引入 `BlueprintHasher`，为 Cascade 带来更智能的执行计划缓存。
