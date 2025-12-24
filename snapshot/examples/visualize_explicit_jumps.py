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