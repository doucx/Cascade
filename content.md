## [WIP] fix(tests): Apply targeted patches for `structural_id` rename

### 用户需求
修复上次重构脚本遗漏的、导致测试失败的 `node.id` 引用。

### 评论
自动化脚本未能覆盖所有场景，特别是在测试文件中使用了不同变量名来引用 `Node` 对象。根据您提供的详细错误日志，问题主要集中在 `test_hashing.py` 和 `test_visualize.py` 中。与其尝试另一个可能不完美的脚本，不如使用精确的 `patch_file` 操作来修复这些已知故障点，这样更安全、更可靠。

### 目标
1.  修复 `tests/engine/graph/test_hashing.py` 中的 `AttributeError`。
2.  修复 `tests/sdk/tools/test_visualize.py` 中的所有 `AttributeError`。

### 基本原理
通过对已知错误的具体代码块应用 `patch_file`，我们可以确保只修改必要的部分，避免对其他文件（如 `test_local.py`、`test_csp.py` 等，我们尚未查看其源码）造成意外影响。这是一个增量、安全的修复策略。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/core #task/object/node-identity #task/action/fix-renaming-fallout #task/state/continue

---

### Script

#### Acts 1: 修复测试文件中的属性访问错误

我们将对 `test_hashing.py` 和 `test_visualize.py` 应用精确的补丁来更正属性名称。

~~~~~act
patch_file
tests/engine/graph/test_hashing.py
~~~~~
~~~~~python
    node1 = instance_map1[target1._uuid]
    node2 = instance_map2[target2._uuid]

    assert node1.id != node2.id, (
        "Hasher must distinguish between different nested LazyResult dependencies"
    )
~~~~~
~~~~~python
    node1 = instance_map1[target1._uuid]
    node2 = instance_map2[target2._uuid]

    assert node1.structural_id != node2.structural_id, (
        "Hasher must distinguish between different nested LazyResult dependencies"
    )
~~~~~

~~~~~act
patch_file
tests/sdk/tools/test_visualize.py
~~~~~
~~~~~python
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
    assert f'"{node_a.structural_id}" -> "{node_b.structural_id}" [label="0"];' in dot_string
    assert f'"{node_c.structural_id}" -> "{node_d.structural_id}" [label="z"];' in dot_string
~~~~~

~~~~~act
patch_file
tests/sdk/tools/test_visualize.py
~~~~~
~~~~~python
    # 1. Assert Data Edge (standard style)
    assert f'"{node_ds.id}" -> "{node_target.id}" [label="data_in"];' in dot_string

    # 2. Assert Condition Edge (dashed, gray)
    expected_cond_edge = f'"{node_cond.id}" -> "{node_target.id}" [style=dashed, color=gray, label="run_if"]'
    assert expected_cond_edge in dot_string

    # 3. Assert Constraint Edge (dotted, purple)
    expected_constraint_edge = f'"{node_constraint.id}" -> "{node_target.id}" [style=dotted, color=purple, label="constraint: cpu"]'
    assert expected_constraint_edge in dot_string
~~~~~
~~~~~python
    # 1. Assert Data Edge (standard style)
    assert f'"{node_ds.structural_id}" -> "{node_target.structural_id}" [label="data_in"];' in dot_string

    # 2. Assert Condition Edge (dashed, gray)
    expected_cond_edge = f'"{node_cond.structural_id}" -> "{node_target.structural_id}" [style=dashed, color=gray, label="run_if"]'
    assert expected_cond_edge in dot_string

    # 3. Assert Constraint Edge (dotted, purple)
    expected_constraint_edge = f'"{node_constraint.structural_id}" -> "{node_target.structural_id}" [style=dotted, color=purple, label="constraint: cpu"]'
    assert expected_constraint_edge in dot_string
~~~~~

### 下一步建议
我们已经修复了日志中明确指出的 `AttributeError`。现在应该重新运行测试，看看是否还有其他因为构造函数调用 (`TypeError`) 或其他未被发现的属性访问错误导致的问题。
