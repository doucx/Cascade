好的，我们已经成功地将“Dogfooding”原则应用到了两个核心的运行时测试文件中。现在是时候将这个重要的改进作为一个逻辑单元提交了。

我将生成一个 `[COMMIT]` 计划。

## [COMMIT] refactor(tests): 采用事件驱动的'Dogfooding'模式重构运行时测试

### 用户需求
将针对 `test_retry.py` 和 `test_control_flow.py` 的重构工作合并到一个单一的、逻辑完整的 Git 提交中。

### 评论
这次提交标志着 Cascade 测试策略的一次重要演进。我们用一种统一的、基于事件总线的“Dogfooding”模式，取代了脆弱的、依赖内部实现的测试方法。通过断言 `Engine` 发出的事件流，我们的测试现在验证的是其公开的行为契约，而非实现细节。这大大增强了测试的健壮性、可读性和长期可维护性。`SpySubscriber` 辅助类的标准化也消除了重复代码，提升了开发者体验。

### 目标
创建一个 Git 提交，该提交包含对 `tests/runtime/test_retry.py` 和 `tests/runtime/test_control_flow.py` 的重构，并附有一个清晰的提交信息来阐述这一测试理念的转变。

### 基本原理
这两项重构服务于同一个战略目标：将《自我测试》的愿景付诸实践。将它们合并到一次提交中，可以在版本历史中清晰地记录下我们从传统的实现测试到现代的行为测试的转变，这是一个单一、完整的架构决策。

### 标签
#intent/refine #flow/ready #priority/medium #comp/tests #comp/runtime #scope/dx #ai/brainstorm #task/domain/testing #task/object/dogfooding #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 暂存重构后的测试文件

我们将 `test_retry.py` 和 `test_control_flow.py` 的新版本添加到 Git 暂存区。

~~~~~act
git_add
tests/runtime/test_retry.py
tests/runtime/test_control_flow.py
~~~~~

#### Acts 2: 创建 Git 提交

现在，我们执行 `git commit`，附上详细的提交信息，记录下这次重要的测试策略升级。

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(tests): Adopt event-driven 'Dogfooding' pattern for runtime tests

Refactors key runtime tests (`test_retry.py` and `test_control_flow.py`) to align with the "Dogfooding" and "test intent over implementation" principles.

Key Changes:

1.  **Event-Based Assertions:** Tests no longer inspect internal state (e.g., `nonlocal` counters). Instead, they subscribe to the `MessageBus` and assert that the `Engine` emits the correct sequence of events (`TaskRetrying`, `TaskSkipped`, etc.). This validates the public, observable behavior of the engine, making tests more robust against internal refactoring.

2.  **Unified SpySubscriber:** A standard `SpySubscriber` helper class is now used in both modules, eliminating code duplication and providing a consistent API for event collection and inspection.

This change significantly improves the quality and expressiveness of our test suite, ensuring that we are testing the behavior our users will actually experience.
~~~~~

### 下一步建议
我们已经完成了对测试策略的重大升级，代码库的健康状况也得到了提升。现在，我们的基础异常坚实。

是时候将注意力转向下一个高价值的核心功能了。我建议我们正式开始 **`cs.visualize(target)`** 的实现工作。这个工具将允许我们将任何工作流的依赖图可视化，这将是调试和理解复杂流程的无价之宝。如果你同意，我将开始制定实现 `cs.visualize` 的计划。
