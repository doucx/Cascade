好的，我们现在处于 "RED" 状态，目标是转向 "GREEN"。

我将生成一个计划来修改 `visualize.py` 的实现，使其能够正确识别和渲染新的 `ITERATIVE_JUMP` 边，从而让我们刚刚创建的 TDD 测试通过。

## [WIP] feat: 增强 visualize 以渲染显式跳转边

### 用户需求
修改 `cascade.tools.visualize.visualize` 函数，使其能够为 `EdgeType.ITERATIVE_JUMP` 类型的边生成一个独特的、自引用的可视化表示，从而让 TDD 测试通过。

### 评论
这是 TDD 流程中的 "GREEN" 阶段。通过实现这个可视化功能，我们不仅修复了测试，更重要的是，我们为用户提供了一个强大的工具来理解和调试基于新架构的、包含循环的工作流。这是一个高价值的开发者体验 (DX) 改进。

### 目标
1.  定位 `visualize.py` 中处理边渲染的循环。
2.  添加一个新的条件分支来专门处理 `EdgeType.ITERATIVE_JUMP`。
3.  在该分支中，生成一个自引用（`source -> source`）的、样式为 `bold`、颜色为 `blue`、标签为 `jump` 的 DOT 语言边。
4.  确保此修改能让 `test_visualize_iterative_jump_edge` 测试成功通过。

### 基本原理
我们将直接在 `visualize.py` 的边处理循环中添加一个 `elif` 子句。由于 `ITERATIVE_JUMP` 边的渲染逻辑（自引用）与标准 `source -> target` 边的逻辑不同，我们将在该子句内部直接构建并添加完整的 DOT 字符串到 `dot_parts` 列表中，然后使用 `continue` 跳过循环末尾的通用边渲染代码。这种方法确保了特殊逻辑的隔离和代码的清晰性。

### 标签
#intent/build #flow/ready #priority/high #comp/sdk #concept/ui #scope/dx #ai/instruct #task/domain/visualization #task/object/explicit-jumps #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 修改 `visualize.py` 以支持 `ITERATIVE_JUMP`

我们将 `patch` `visualize.py` 文件，在边的渲染逻辑中插入一个专门处理 `ITERATIVE_JUMP` 的新分支。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/visualize.py
~~~~~
~~~~~python
        elif edge.edge_type == EdgeType.SEQUENCE:
            style = ' [style=dashed, color=darkgray, arrowhead=open, label="next"]'
        else:
            style = f' [label="{edge.arg_name}"]'

        dot_parts.append(
            f'  "{edge.source.structural_id}" -> "{edge.target.structural_id}"{style};'
        )
~~~~~
~~~~~python
        elif edge.edge_type == EdgeType.SEQUENCE:
            style = ' [style=dashed, color=darkgray, arrowhead=open, label="next"]'
        elif edge.edge_type == EdgeType.ITERATIVE_JUMP:
            # Special case for self-referencing jump edges
            style = ' [style=bold, color=blue, label="jump"]'
            dot_parts.append(
                f'  "{edge.source.structural_id}" -> "{edge.source.structural_id}"{style};'
            )
            # Continue to the next edge to avoid double-printing
            continue
        else:
            style = f' [label="{edge.arg_name}"]'

        dot_parts.append(
            f'  "{edge.source.structural_id}" -> "{edge.target.structural_id}"{style};'
        )
~~~~~

### 下一步建议
我们已经完成了代码的修复，测试现在应该会通过了。这是一个逻辑上完整的工作单元，非常适合进行一次 Git 提交。

我建议我们现在创建一个 `[COMMIT]` 计划，将 `test_visualize.py` 的修改和 `visualize.py` 的修复作为一个原子提交进行暂存和提交。这将正式结束这个微型任务，并为我们留下清晰的变更历史。如果你同意，请告诉我。
