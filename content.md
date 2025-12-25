好的，我已仔细审查了你提供的文件。现在我将遵循 TDD（测试驱动开发）原则，首先创建一个新的测试文件。这个测试用例将直接调用 `cs.run([task_a, task_b])`，它在当前的代码库中必然会失败，从而将我们的开发流程置于一个明确的 "RED" 状态。

这是实现自动汇合功能的第一步。

## [WIP] test: 为自动汇合语法糖添加 TDD 测试

### 用户需求
根据提案 CP-011，`cs.run()` 函数应支持接收 `LazyResult` 对象的列表或元组作为其 `target` 参数，并自动将它们并行执行，最后返回一个包含所有结果的列表。

### 评论
这是一个高价值的开发者体验（DX）改进。它消除了为并行任务编写样板“收集器”函数的需要，使 API 更符合 Python 开发者使用 `asyncio.gather` 等工具的直觉。

### 目标
1.  创建一个新的测试文件 `tests/sdk/integration/test_auto_gathering.py`。
2.  在该文件中定义一个测试用例，它直接调用 `cs.run()` 并传入一个 `LazyResult` 列表。
3.  确保此测试在当前的代码实现下会失败（例如，抛出 `AttributeError` 或 `TypeError`），从而为后续的 GREEN 阶段建立一个明确的、可验证的目标。

### 基本原理
我们严格遵循 TDD 流程。通过首先创建一个失败的测试，我们精确地定义了新功能必须满足的行为契约。这不仅确保了最终实现的正确性，也验证了我们对问题的理解是准确的。

### 标签
#intent/tooling #flow/ready #priority/high #comp/sdk #concept/ui #scope/dx #ai/instruct #task/domain/sdk #task/object/auto-gathering #task/action/tdd-setup #task/state/begin

---

### Script

#### Acts 1: 创建新的 TDD 测试文件

我将创建一个新的测试文件，用于验证 `cs.run` 的自动汇合功能。

~~~~~act
write_file
tests/sdk/integration/test_auto_gathering.py
~~~~~
~~~~~python
import pytest
import cascade as cs


@cs.task(pure=True)
def task_one():
    return 1


@cs.task(pure=True)
def task_two():
    return "two"


@cs.task(pure=True)
def identity(val: any) -> any:
    return val


def test_run_with_list_of_lazy_results():
    """
    Verifies that cs.run can accept a list of LazyResults,
    execute them in parallel, and return a list of their results.
    """
    lr1 = task_one()
    lr2 = task_two()

    # This is the proposed intuitive usage
    results = cs.run([lr1, lr2])

    assert results == [1, "two"]


def test_run_with_tuple_of_lazy_results():
    """
    Verifies that cs.run also works with tuples.
    """
    lr1 = task_one()
    lr2 = task_two()

    results = cs.run((lr1, lr2))

    # Per the proposal, the return type is unified to a list
    assert results == [1, "two"]


def test_run_with_mixed_list_of_lazy_results_and_literals():
    """
    Verifies that literals mixed in with LazyResults are passed through correctly.
    """
    lr1 = task_one()
    literal_str = "I am a literal"
    lr2 = task_two()

    # The graph should effectively be gather(lr1, identity("..."), lr2)
    results = cs.run([lr1, literal_str, lr2])

    assert results == [1, "I am a literal", "two"]


def test_run_with_empty_list():
    """
    Verifies that passing an empty list is a valid operation and returns an empty list.
    """
    results = cs.run([])
    assert results == []

~~~~~

### 下一步建议

我们已经创建了定义新功能的测试用例。下一步是执行这个测试并确认它会失败。一旦我们处于 RED 状态，我将生成下一个计划来修改 `cascade-sdk/src/cascade/__init__.py` 和 `cascade-sdk/src/cascade/internal/inputs.py` 以实现自动汇合逻辑，从而使这个测试通过 (GREEN)。
