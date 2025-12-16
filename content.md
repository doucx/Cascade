## [WIP] fix(core): Repair `GraphBuilder` dependency logic and fix async tests

### 错误分析
1.  **`RuntimeError: asyncio.run() cannot be called from a running event loop`**:
    *   发生在 `tests/test_map.py`。
    *   原因：测试函数被 `@pytest.mark.asyncio` 装饰，运行在事件循环中。`cs.run()` 内部调用 `asyncio.run()`，尝试启动新的循环，这在 Python 中是被禁止的。
    *   修复：在异步测试中，绕过 `cs.run`，直接实例化 `Engine` 并 `await engine.run(...)`。

2.  **`TypeError: can only join an iterable`** (在 `test_shell_map` 中):
    *   发生在 `tests/test_stdlib.py`。
    *   原因：下游任务接收到的是 `MappedLazyResult` 对象本身，而不是其计算结果（列表）。
    *   根源：`src/cascade/graph/build.py` 中的 `_process_dependencies` 方法漏掉了对 `MappedLazyResult` 的检查。它只处理 `LazyResult` 和 `Param` 作为依赖，将 `MappedLazyResult` 误判为字面量（literal），导致没有建立图的依赖边。
    *   修复：更新 `_process_dependencies` 以识别 `MappedLazyResult` 为有效的上游依赖。

### 计划
1.  **修复图构建器**: 修改 `src/cascade/graph/build.py`，使 `_process_dependencies` 能够正确处理 `MappedLazyResult`，为其创建依赖边。
2.  **修复测试代码**: 修改 `tests/test_map.py`，移除 `cs.run`，改用 `Engine().run()` 模式。

### 标签
#intent/fix #flow/ready #priority/critical #comp/core #comp/tests #concept/graph #scope/core #ai/instruct #task/domain/core #task/object/graph-builder #task/action/bugfix #task/state/end

---

### Script

#### Acts 1: 修复 `GraphBuilder` 依赖解析

我们需要在 `_process_dependencies` 中添加对 `MappedLazyResult` 的支持。

~~~~~act
patch_file
src/cascade/graph/build.py
~~~~~
~~~~~python
    def _process_dependencies(self, target_node: Node, inputs: Any, is_kwargs: bool):
        iterator = inputs.items() if is_kwargs else enumerate(inputs)

        for key, value in iterator:
            arg_name = str(key)

            if isinstance(value, (LazyResult, Param)):
                source_node = self._visit(value)
                edge = Edge(source=source_node, target=target_node, arg_name=arg_name)
                self.graph.add_edge(edge)
            elif isinstance(value, Router):
                selector_node = self._visit(value.selector)
~~~~~
~~~~~python
    def _process_dependencies(self, target_node: Node, inputs: Any, is_kwargs: bool):
        iterator = inputs.items() if is_kwargs else enumerate(inputs)

        for key, value in iterator:
            arg_name = str(key)

            if isinstance(value, (LazyResult, MappedLazyResult, Param)):
                source_node = self._visit(value)
                edge = Edge(source=source_node, target=target_node, arg_name=arg_name)
                self.graph.add_edge(edge)
            elif isinstance(value, Router):
                selector_node = self._visit(value.selector)
~~~~~

#### Acts 2: 修复 `tests/test_map.py` 中的 Asyncio 冲突

将 `cs.run` 替换为手动 Engine 调用。

~~~~~act
patch_file
tests/test_map.py
~~~~~
~~~~~python
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
~~~~~python
    # 2. Reduce the results -> 12
    total = sum_all(numbers=mapped_results)
    
    engine = cs.Engine()
    result = await engine.run(total)
    assert result == 12

@pytest.mark.asyncio
async def test_map_empty():
    """Test mapping over an empty list returns an empty list."""
    inputs = []
    
    mapped_results = double.map(x=inputs)
    total = sum_all(numbers=mapped_results)
    
    engine = cs.Engine()
    result = await engine.run(total)
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
    
    engine = cs.Engine()
    result = await engine.run(total)
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
    
    engine = cs.Engine()
    result = await engine.run(total)
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
    
    engine = cs.Engine()
    with pytest.raises(ValueError, match="mismatched lengths"):
        await engine.run(mapped)
~~~~~
