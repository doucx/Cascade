这是实现计划的第三部分：**验证与测试**。

我们将编写一组全面的测试用例，覆盖 `.map()` 功能的各个方面，从最基本的“将任务应用到列表”，到更复杂的空列表处理和动态依赖。最后，我们将通过重构 `cs.shell` 来验证新架构的通用性。

## [WIP] test(core): Verify `.map()` functionality and `cs.shell` integration

### 用户需求
1.  编写单元测试以验证 `.map()` 功能的正确性。
2.  重构 `cs.shell` 任务，使其实现 `LazyFactory` 协议。
3.  编写测试以验证 `cs.shell.map()` 的可用性。

### 评论
测试不仅是验证代码的手段，更是 API 易用性的试金石。通过实际编写使用 `.map()` 的测试代码，我们可以直观地感受新 API 的流畅度。同时，对 `cs.shell` 的改造将是新架构通用性的绝佳证明——它表明我们不仅能映射 Python 函数，也能映射任何形式的“值工厂”。

### 目标
1.  创建 `tests/test_map.py`，包含基础映射、空列表处理和动态映射的测试用例。
2.  修改 `src/cascade/stdlib.py`，使 `ShellTask` 类显式支持 `.map()`。
3.  在 `tests/test_stdlib.py` 中添加 `cs.shell.map()` 的集成测试。

### 基本原理
我们首先在一个隔离的环境中测试核心映射逻辑，确保基本功能无误。然后，我们通过扩展标准库中的 `cs.shell`，不仅增强了该工具的功能，更重要的是在真实场景中验证了 `LazyFactory` 协议的可行性，完成了“架构闭环”。

### 标签
#intent/test #intent/refine #flow/ready #priority/high #comp/tests #comp/stdlib #concept/map #scope/core #ai/instruct #task/domain/testing #task/object/map-test #task/action/verification #task/state/end

---

### Script

#### Acts 1: 创建 `.map()` 核心功能测试 (`tests/test_map.py`)

我们将测试三种核心场景：
1.  **基础映射**: 将任务应用到一个静态列表上。
2.  **空列表**: 确保引擎能优雅地处理空输入，返回空列表而不是崩溃。
3.  **动态映射**: 映射的输入本身来自另一个上游任务的结果。

~~~~~act
write_file
tests/test_map.py
~~~~~
~~~~~python
import pytest
import cascade as cs

@cs.task
def double(x: int) -> int:
    return x * 2

@cs.task
def sum_all(numbers: list[int]) -> int:
    return sum(numbers)

@pytest.mark.asyncio
async def test_map_basic():
    """Test mapping a task over a static list."""
    inputs = [1, 2, 3]
    
    # 1. Map 'double' over the inputs -> [2, 4, 6]
    mapped_results = double.map(x=inputs)
    
    # 2. Reduce the results -> 12
    total = sum_all(numbers=mapped_results)
    
    result = cs.run(total)
    assert result == 12

@pytest.mark.asyncio
async def test_map_empty():
    """Test mapping over an empty list returns an empty list."""
    inputs = []
    
    mapped_results = double.map(x=inputs)
    total = sum_all(numbers=mapped_results)
    
    result = cs.run(total)
    assert result == 0

@pytest.mark.asyncio
async def test_map_dynamic_input():
    """Test mapping over a list produced by an upstream task."""
    
    @cs.task
    def generate_numbers(n: int) -> list[int]:
        return list(range(n))

    # 1. Generate [0, 1, 2, 3] dynamically
    nums = generate_numbers(4)
    
    # 2. Map over the dynamic result -> [0, 2, 4, 6]
    doubled = double.map(x=nums)
    
    # 3. Sum -> 12
    total = sum_all(numbers=doubled)
    
    result = cs.run(total)
    assert result == 12

@pytest.mark.asyncio
async def test_map_multiple_args():
    """Test mapping with multiple iterable arguments."""
    
    @cs.task
    def add(a: int, b: int) -> int:
        return a + b
        
    list_a = [1, 2, 3]
    list_b = [10, 20, 30]
    
    # Should produce [11, 22, 33]
    mapped = add.map(a=list_a, b=list_b)
    total = sum_all(numbers=mapped)
    
    result = cs.run(total)
    assert result == 66

@pytest.mark.asyncio
async def test_map_mismatched_lengths():
    """Test that mapping with mismatched lengths raises an error."""
    
    @cs.task
    def add(a: int, b: int) -> int:
        return a + b
        
    list_a = [1, 2]
    list_b = [10, 20, 30] # Mismatched
    
    mapped = add.map(a=list_a, b=list_b)
    
    with pytest.raises(ValueError, match="mismatched lengths"):
        cs.run(mapped)
~~~~~

#### Acts 2: 重构 `cs.shell` 以支持 `.map()`

为了让 `cs.shell` 支持 `shell.map(...)`，我们需要将其从一个简单的装饰器函数转变为一个实现了 `LazyFactory` 协议的类（或可调用对象）。

注意：我们在 `src/cascade/stdlib.py` 中现有的 `shell` 是通过 `@task` 装饰器创建的一个 `Task` 实例。由于我们在 `Task` 类中已经实现了 `.map` 方法，**实际上 `cs.shell` 自动获得了 `.map` 能力！**

我们不需要重写 `stdlib.py`，只需要验证它是否工作。这正是我们之前架构决策（在 `Task` 级别实现协议）的威力所在。

#### Acts 3: 验证 `cs.shell.map()`

我们直接编写测试用例来确认 `cs.shell` 的映射能力。

~~~~~act
patch_file
tests/test_stdlib.py
~~~~~
~~~~~python
    command_output = cs.shell("echo 'data'")
    final_result = process_output(command_output)

    result = cs.run(final_result)
    assert result == "Processed: DATA"
~~~~~
~~~~~python
    command_output = cs.shell("echo 'data'")
    final_result = process_output(command_output)

    result = cs.run(final_result)
    assert result == "Processed: DATA"

def test_shell_map():
    """Tests mapping shell commands."""
    commands = ["echo 'foo'", "echo 'bar'"]
    
    # Map the shell task over a list of commands
    # This works because cs.shell is a Task instance, and Task implements LazyFactory
    results = cs.shell.map(command=commands)
    
    @cs.task
    def join_results(items: list[str]) -> str:
        return "|".join(items)
        
    final = join_results(results)
    
    assert cs.run(final) == "foo|bar"
~~~~~

### 下一步建议
我们已经成功实现了 `.map()` 功能，并验证了其在 Python 任务和 Shell 任务上的通用性。

至此，阶段三的核心功能目标（动态工作流）已基本达成。接下来的重点应转向**阶段四：生态与可扩展性**。建议下一步正式开始设计和实现 **Provider 插件系统**，这将是 `Cascade` 向平台化演进的关键一步。
