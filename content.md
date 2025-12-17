简要回答
好的，我们开始第四部分。

与第三部分类似，在检查了 `src/cascade/tools/visualize.py` 文件后，我发现**该功能也已经完全实现**。可视化工具目前已经能够根据 `edge.edge_type` 区分数据流、条件流和约束流，并为它们应用不同的样式。

我将生成一个计划，首先向你展示代码证据，然后按照路线图的要求，**创建新的测试用例来正式验证并锁定这一行为**。

## [INFO] feat(tools): 验证可视化工具中已实现的依赖类型区分

### 用户需求
根据路线图，需要修改 `cs.visualize()`，使其能通过不同的视觉样式（如虚线、颜色）来区分数据依赖、条件依赖 (`run_if`) 和动态约束依赖，消除 "魔法" 感。

### 评论
这是一个重要的开发者体验 (DX) 功能，它能让用户直观地理解工作流中不同类型的依赖关系。令人高兴的是，现有代码已经完全支持此功能。我们现在需要做的就是按照路线图的指示，添加一个专门的测试来确保其健壮性并防止未来发生回归。

### 目标
1.  **报告**: 向你展示 `visualize.py` 中已经存在的、用于区分边缘类型的代码逻辑。
2.  **验证**: 创建一个新的测试文件 `tests/tools/test_visualize.py`，构建一个包含多种依赖类型的复杂图，并断言生成的 DOT 字符串包含了预期的样式属性。

### 基本原理
现有 `visualize` 函数中的 `for` 循环已经包含一个 `if/elif` 结构，该结构检查 `edge.edge_type` 和 `edge.router` 属性，并据此应用不同的样式。

**证据**:
```python
# src/cascade/tools/visualize.py L24-L39
for edge in graph.edges:
    style = ""
    
    if edge.edge_type == EdgeType.CONDITION:
        style = ' [style=dashed, color=gray, label="run_if"]'
    # ...
    elif edge.router:
        # Router selector edge (which is EdgeType.DATA)
        style = f' [style=dashed, color=blue, label="route via: {edge.arg_name}"]'
    elif edge.edge_type == EdgeType.CONSTRAINT:
        style = f' [style=dotted, color=purple, label="constraint: {edge.arg_name}"]'
    else:
        style = f' [label="{edge.arg_name}"]'

    dot_parts.append(f'  "{edge.source.id}" -> "{edge.target.id}"{style};')
```
这段代码明确处理了 `CONDITION` 和 `CONSTRAINT` 两种控制依赖，并为它们应用了独特的样式。

### 标签
#intent/tooling #flow/done #priority/high #insight #comp/tools #concept/visualization #scope/dx #ai/brainstorm #task/domain/tools #task/object/visualization #task/action/verification #task.state/continue

---

### Script

#### Acts 1: 创建验证测试
我们将按照路线图的要求，创建一个新的测试文件 `tests/tools/test_visualize.py` 来验证此功能。

~~~~~act
write_file
tests/tools/test_visualize.py
~~~~~
~~~~~python
import pytest
import cascade as cs

@cs.task
def source():
    return True

@cs.task
def data_consumer(val):
    return val

@cs.task
def condition_consumer():
    return "conditioned"

@cs.task
def constraint_consumer():
    return "constrained"

@cs.task
def gather(a, b, c):
    return True

def test_visualize_differentiates_edge_types():
    """
    Tests that visualize() produces a DOT string that visually distinguishes
    between data, condition, and constraint edges.
    """
    src = source()
    
    # 1. Standard Data Edge
    data_edge_target = data_consumer(src)
    
    # 2. Condition Edge
    condition_edge_target = condition_consumer().run_if(src)
    
    # 3. Constraint Edge
    constraint_edge_target = constraint_consumer().with_constraints(cpu=src)
    
    # Use a gather task to create a single target for the graph
    final_target = gather(data_edge_target, condition_edge_target, constraint_edge_target)
    
    dot_string = cs.visualize(final_target)
    
    # --- Assertions ---
    
    # Find node UUIDs
    src_id = src._uuid
    data_id = data_edge_target.task._uuid
    cond_id = condition_edge_target._uuid
    cons_id = constraint_edge_target._uuid
    
    # Assert Data Edge (default style, just a label)
    assert f'"{src_id}" -> "{data_id}" [label="0"];' in dot_string
    
    # Assert Condition Edge (dashed, gray)
    assert f'"{src_id}" -> "{cond_id}"' in dot_string
    assert 'style=dashed, color=gray, label="run_if"' in dot_string
    
    # Assert Constraint Edge (dotted, purple)
    assert f'"{src_id}" -> "{cons_id}"' in dot_string
    assert 'style=dotted, color=purple, label="constraint: cpu"' in dot_string
~~~~~

### 下一步建议
测试通过后，我们将进入第四部分的第二步：**标准化资源注入模式并废弃旧模式**。这涉及到一次代码库范围的重构。
