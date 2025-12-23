好的，你的诊断完全正确。这是一个典型的、由核心 API 变更引起的连锁反应。由于 `build_graph` 的签名变更，所有直接调用它并期望返回单个 `Graph` 对象的测试都失败了。

使用 `sed` 进行批量修复是最高效的策略。我将生成一个计划来执行此操作。

## [WIP] chore(tests): 批量适配测试套件到新 GraphBuilder 签名

### 用户需求
使用命令行工具（如 `sed`）批量修复所有因 `build_graph` 返回值变更而失败的测试文件。

### 评论
这是一个非常好的实践，通过一次性的、自动化的脚本来处理机械性的代码重构，可以最大程度地减少手动操作引入的错误，并极大提高效率。

### 目标
执行一个 `sed` 命令，该命令会查找所有 `variable = build_graph(...)` 形式的赋值语句，并将其替换为 `variable, _ = build_graph(...)`，从而正确地解包 `build_graph` 返回的元组。

### 基本原理
我们将使用带有扩展正则表达式（`-E`）的 `sed` 命令来执行就地替换（`-i`）。正则表达式 `^(\s*[a-zA-Z0-9_]+) = build_graph\(` 会精确地匹配并捕获以变量赋值开头的 `build_graph` 调用行。然后，我们使用捕获的变量名（`\1`）来重写该行，添加 `, _` 以解包元组，从而修复错误。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-suite #task/action/refactor #task-state/continue

---

### Script

#### Acts 1: 批量修复测试文件

此命令将对搜索结果中所有受影响的文件执行替换操作。

~~~~~act
run_command
~~~~~
~~~~~bash
sed -i -E 's/^(\s*[a-zA-Z0-9_]+) = build_graph\(/\1, _ = build_graph\(/g' \
    tests/engine/adapters/solvers/test_csp.py \
    tests/engine/adapters/solvers/test_native.py \
    tests/engine/graph/test_serialize.py \
    tests/engine/graph/test_build.py \
    tests/engine/graph/test_build_tco.py \
    tests/spec/spec/test_constraint.py \
    packages/cascade-sdk/src/cascade/tools/visualize.py \
    packages/cascade-sdk/src/cascade/tools/preview.py
~~~~~

### 下一步建议
执行此命令后，所有因 `AttributeError: 'tuple' object has no attribute 'nodes'` 引起的测试失败都应得到解决。请再次运行 `pytest`。现在我们可以更清楚地看到本次重构是否引入了其他更深层次的逻辑问题。
