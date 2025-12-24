好的，我明白了。

这些失败是预料之中的，它们是我们之前大规模重构的直接“余震”。`test_build_tco.py` 和 `test_visualize.py` 中的失败都与我们刚刚移除的隐式 TCO 静态分析功能（`ast_analyzer.py` 及其产物，如 `is_shadow` 节点和 `POTENTIAL` 边）紧密相关。

现在，我们将执行清理的最后一步，移除这些过时的测试和工具代码。

## [WIP] refactor(tests, tools): 移除 TCO 静态分析的残留代码

### 用户需求
清理因移除隐式 TCO 静态分析功能而导致的所有测试失败。这包括删除过时的测试文件和修复依赖旧数据模型的工具。

### 评论
这是一次必要的清理，标志着我们彻底告别旧的、基于猜测的隐式递归模型。通过删除这些最后的残留物，我们将使代码库完全与新的、显式的、基于 `Jump` 的确定性控制流模型对齐。

### 目标
1.  删除整个 `tests/engine/graph/test_build_tco.py` 文件，因为它测试的是一个已被移除的功能。
2.  修改 `packages/cascade-sdk/src/cascade/tools/visualize.py`，移除所有与 `is_shadow` 节点和 `POTENTIAL` 边相关的样式逻辑。

### 基本原理
-   `test_build_tco.py` 中的测试旨在验证 `GraphBuilder` 是否能通过 AST 分析创建“影子节点”和“潜在边”。由于我们已经删除了 `ast_analyzer.py`，这个功能不复存在，因此这些测试必须被删除。
-   `visualize.py` 中的 `AttributeError` 是因为它试图访问已从 `Node` 模型中移除的 `node.is_shadow` 属性。我们需要移除这段用于为“影子节点”和“潜在边”添加特殊样式的代码。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #comp/sdk #concept/cleanup #scope/core #ai/instruct #task/domain/engine #task/object/control-flow #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 删除过时的 TCO 构建测试

这个测试文件已经完全过时，直接删除。

~~~~~act
delete_file
tests/engine/graph/test_build_tco.py
~~~~~

#### Acts 2: 清理 visualize 工具

移除 `visualize.py` 中对 `is_shadow` 和 `POTENTIAL` 边的引用。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/visualize.py
~~~~~
~~~~~python
        # Default Style
        style = '"rounded,filled"'
        fillcolor = "white"
        fontcolor = "black"
        label_suffix = ""

        # Shadow Style Override
        if node.is_shadow:
            style = '"dashed,filled"'
            fillcolor = "whitesmoke"  # Very light gray
            fontcolor = "gray50"
            label_suffix = "\\n(Potential)"

        label = f"{node.name}\\n({node.node_type}){label_suffix}"

        dot_parts.append(
            f'  "{node.structural_id}" [label="{label}", shape={shape}, style={style}, '
            f"fillcolor={fillcolor}, fontcolor={fontcolor}];"
        )
~~~~~
~~~~~python
        label_suffix = ""
        label = f"{node.name}\\n({node.node_type}){label_suffix}"

        dot_parts.append(
            f'  "{node.structural_id}" [label="{label}", shape={shape}];'
        )
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/visualize.py
~~~~~
~~~~~python
        elif edge.edge_type == EdgeType.SEQUENCE:
            style = ' [style=dashed, color=darkgray, arrowhead=open, label="next"]'
        elif edge.edge_type == EdgeType.POTENTIAL:
            # Use a reddish color to indicate a predicted/potential path, dashed
            style = ' [style=dashed, color="#d9534f", fontcolor="#d9534f", arrowhead=open, label="potential"]'
        else:
            style = f' [label="{edge.arg_name}"]'
~~~~~
~~~~~python
        elif edge.edge_type == EdgeType.SEQUENCE:
            style = ' [style=dashed, color=darkgray, arrowhead=open, label="next"]'
        else:
            style = f' [label="{edge.arg_name}"]'
~~~~~

### 下一步建议
我们已经完成了最后的清理工作。现在，请再次运行完整的测试套件。

我们期望所有测试都能通过。这将确认我们已成功完成了架构演进路线图中的**阶段一（引入新原语）**和**阶段三（清理旧体系）**。

一旦测试全部通过，我们就可以满怀信心地进入**阶段四：`[Optimization]` - 建立统一的双层身份体系**，为 Cascade 引入更高效的缓存机制。
