这是一个非常好的主意。通过一个具体的、可运行的示例，我们可以直观地展示显式控制流在静态图中是如何呈现的，以及它如何帮助开发者理解复杂的循环逻辑。

我将生成一个计划，在 `examples/` 目录下创建一个名为 `visualize_explicit_jumps.py` 的示例脚本。

## [COMMIT] docs: 添加演示显式跳转可视化的示例脚本

### 用户需求
创建一个可运行的演示脚本，展示 `cs.visualize` 如何处理包含显式跳转（自循环和多节点循环）的复杂 Cascade 工作流。

### 评论
这个示例不仅是一个功能演示，更是一份鲜活的“活文档”。它向用户展示了如何使用 `cs.bind`, `cs.select_jump` 和 `cs.Jump` 构建复杂的控制流，并证明了 Cascade 能够将这些逻辑清晰地转化为可视化的拓扑图。对于推广新架构的编程模型具有重要价值。

### 目标
1.  在 `examples/` 目录下创建一个新的 Python 脚本。
2.  在脚本中构建一个模拟“持续集成与修复”过程的复杂工作流：
    *   `checkout` -> `lint` -> `test`。
    *   如果 `test` 失败，跳转到 `fix` 节点。
    *   `fix` 节点跳回 `lint` 节点重新开始流程。
    *   如果 `test` 成功，流程结束。
3.  脚本运行后将输出完整的 DOT 语言字符串，并打印如何将其渲染为图片的说明。

### 基本原理
我们选择了一个具有代表性的“CI/CD”场景，因为它天然包含顺序执行、条件判断和循环（回退修复）。通过 `cs.bind` 在不同深度的节点之间建立连接，我们可以充分展示 `GraphBuilder` 准确捕捉跨节点跳转的能力，以及 `visualize` 渲染器如何用醒目的样式标注这些非线性的控制流路径。

### 标签
#intent/document #flow/ready #priority/medium #comp/docs #concept/ui #scope/dx #ai/instruct #task/domain/documentation #task/object/visualization-demo #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建可视化演示脚本

我们将使用 `write_file` 创建这个新的示例文件。

~~~~~act
write_file
examples/visualize_explicit_jumps.py
~~~~~
~~~~~python
"""
Cascade 显式跳转可视化演示 (v1.4+)

本示例演示了如何构建一个包含多节点循环的复杂工作流，并使用 cs.visualize
将其渲染为拓扑图。

场景：模拟一个 CI/CD 流程
1. 代码签出 (Checkout)
2. 静态检查 (Lint) -> 失败则跳到修复 (Fix)
3. 单元测试 (Test) -> 失败则跳到修复 (Fix)
4. 修复 (Fix) -> 修复后跳回 Lint 重新开始
"""

import cascade as cs

# --- 1. 定义原子任务 ---

@cs.task
def checkout():
    print("--- 正在签出代码...")
    return "source_code_v1"

@cs.task
def lint(code):
    print(f"--- 正在对 {code} 进行 Lint 检查...")
    # 模拟 Lint 失败的情况
    return cs.Jump("needs_fix", data="lint_errors")

@cs.task
def unit_test(code):
    print(f"--- 正在对 {code} 运行测试...")
    # 模拟测试失败的情况
    return cs.Jump("needs_fix", data="test_failures")

@cs.task
def fix_issue(reason):
    print(f"--- 正在修复问题: {reason}...")
    return "fixed_source_code"

# --- 2. 构建包含循环的图 ---

def create_cicd_workflow():
    # A. 定义基本路径
    src = checkout()
    linter_run = lint(src)
    tester_run = unit_test(linter_run)
    fixer_run = fix_issue("some_error") # 这里的输入稍后会被 Jump 数据覆盖

    # B. 定义跳转选择器 (JumpSelectors)
    
    # Lint 失败跳转到 Fix，成功则正常流向 Test
    lint_selector = cs.select_jump({
        "needs_fix": fixer_run,
        None: tester_run
    })
    
    # Test 失败跳转到 Fix，成功则结束
    test_selector = cs.select_jump({
        "needs_fix": fixer_run,
        None: None 
    })
    
    # Fix 之后跳回 Lint 重新开始
    fix_selector = cs.select_jump({
        "retry": linter_run
    })

    # C. 进行显式绑定 (Static Binding)
    cs.bind(linter_run, lint_selector)
    cs.bind(tester_run, test_selector)
    cs.bind(fixer_run, fix_selector)

    return tester_run

# --- 3. 生成可视化结果 ---

if __name__ == "__main__":
    workflow = create_cicd_workflow()
    
    dot_output = cs.visualize(workflow)
    
    print("\n" + "="*40)
    print("      CASCADE 可视化演示 (DOT 输出)")
    print("="*40 + "\n")
    print(dot_output)
    print("\n" + "="*40)
    print("提示：你可以将上面的输出复制到 https://dreampuf.github.io/GraphvizOnline/")
    print("或者在本地运行: python examples/visualize_explicit_jumps.py | dot -Tpng -o workflow.png")
    print("="*40)
~~~~~

### 下一步建议

示例脚本已经准备好。你可以直接运行它：
```bash
python examples/visualize_explicit_jumps.py
```

它会输出一个包含加粗蓝色“跳转”边的 DOT 图。

如果你对可视化效果感到满意，我建议接下来的方向是：
- **探索 `cs.Jump` 的执行路径**：我们可以开始编写针对这种多节点循环的执行测试，确保 `Engine` 能够正确地在这些复杂的静态跳转边上“冲浪”。
- **阶段四：统一身份体系**：既然静态图已经如此准确，我们可以开始引入 `Blueprint Hash`，实现真正的高性能执行计划缓存。
