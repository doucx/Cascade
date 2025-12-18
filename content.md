你的诊断完全正确，我深表歉意。

我错误地将测试文件放置在了特定包的 `tests` 目录中，而 `bus_and_spy` 这个共享的 fixture 是在项目顶层的 `tests/conftest.py` 中定义的。Pytest 的 fixture 作用域规则导致 `packages/cascade-runtime/tests/` 下的测试无法找到顶层 `tests/` 目录中定义的 fixture。

我将立即纠正这个错误，将测试文件移动到正确的位置。

## [WIP] fix: 移动约束测试文件以解决 fixture 作用域问题

### 错误分析
测试因 `fixture 'bus_and_spy' not found` 错误而失败。根本原因是测试文件 `packages/cascade-runtime/tests/runtime/test_engine_constraints.py` 被放置在了一个无法访问顶层 `tests/conftest.py` 文件所定义 fixture 的目录中。项目结构表明，所有需要共享 fixture 的集成测试都应位于顶层的 `tests/py/` 目录结构下。

### 用户需求
修复因测试文件位置不当导致的 fixture 找不到错误，使测试能够通过。

### 评论
这是一个非常敏锐的观察，直接指出了问题的核心。将测试文件放在正确的、能够继承共享上下文的位置，是维护一个清晰、可扩展的测试套件的关键。感谢你的指正。

### 目标
1.  将 `test_engine_constraints.py` 文件从 `packages/cascade-runtime/tests/runtime/` 移动到 `tests/py/runtime/`。

### 基本原理
通过将测试文件移动到 `tests/py/runtime/` 目录下，它将处于顶层 `tests/conftest.py` 的作用域内。这样，pytest 在执行该测试文件时，将能够正确地发现并注入 `bus_and_spy` fixture，从而解决 "fixture not found" 的错误。

### 标签
#intent/fix #flow/ready #priority/high
#comp/tests #comp/build #scope/dx
#ai/instruct
#task/domain/testing #task/object/test-suite #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 移动测试文件到正确位置

我们将使用 `move_file` 指令来修正测试文件的位置。

~~~~~act
move_file
packages/cascade-runtime/tests/runtime/test_engine_constraints.py
tests/py/runtime/test_engine_constraints.py
~~~~~

### 下一步建议
文件已移动到正确的位置。请重新运行测试。如果测试通过，我们将继续我们之前中断的计划：**扩展 `check_permission` 方法以支持任务级（task-scoped）约束**。
