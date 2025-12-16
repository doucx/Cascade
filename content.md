# [WIP] fix(core): 修复 build.py 中的 NameError 并适配 CLI 测试

## 摘要头
## [WIP] fix(core): 修复 build.py 中的 NameError 并适配 CLI 测试

### 用户需求
修复导致大量测试失败的 `NameError: name 'Param' is not defined`，并解决 SQL 和 CLI 测试中的断言失败。

### 评论
`build.py` 中的 `_process_dependencies` 方法仍然引用了 `Param` 类，但在文件头部该类的导入已被移除，这是导致 `NameError` 的直接原因。由于 `cs.Param()` 现在返回标准的 `LazyResult`，`GraphBuilder` 不再需要对 `Param` 进行特殊类型检查。

### 目标
1.  修改 `src/cascade/graph/build.py`，移除 `_process_dependencies` 中对 `Param` 的引用。
2.  更新 `tests/providers/test_sql.py`，放宽错误消息匹配，以适应可能的异常类型变化。
3.  调试并修复 `tests/tools/test_cli.py`，确保 Context 正确传递。

### 基本原理
-   **GraphBuilder**: `Param` 现在只是一个工厂函数，返回 `LazyResult`。因此，在图构建阶段，它就是一个普通的 `LazyResult`，不需要特殊的 `isinstance` 检查。
-   **SQL Test**: 资源查找失败可能会抛出 `NameError`，但也可能因为异步执行或包装而被捕获为其他形式。

### 标签
#intent/fix #flow/draft #priority/critical #comp/core #comp/cli #scope/core #ai/instruct #task/domain/core #task/object/name-error #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 移除 build.py 中的 Param 引用

~~~~~act
patch_file
src/cascade/graph/build.py
~~~~~
~~~~~old
    def _process_dependencies(self, target_node: Node, inputs: Any, is_kwargs: bool):
        iterator = inputs.items() if is_kwargs else enumerate(inputs)

        for key, value in iterator:
            arg_name = str(key)

            if isinstance(value, (LazyResult, MappedLazyResult, Param)):
                source_node = self._visit(value)
                # Standard DATA edge
                edge = Edge(
                    source=source_node, 
                    target=target_node, 
                    arg_name=arg_name, 
                    edge_type=EdgeType.DATA
                )
                self.graph.add_edge(edge)
~~~~~
~~~~~new
    def _process_dependencies(self, target_node: Node, inputs: Any, is_kwargs: bool):
        iterator = inputs.items() if is_kwargs else enumerate(inputs)

        for key, value in iterator:
            arg_name = str(key)

            if isinstance(value, (LazyResult, MappedLazyResult)):
                source_node = self._visit(value)
                # Standard DATA edge
                edge = Edge(
                    source=source_node, 
                    target=target_node, 
                    arg_name=arg_name, 
                    edge_type=EdgeType.DATA
                )
                self.graph.add_edge(edge)
~~~~~

#### Acts 2: 修复 SQL 测试的错误匹配

`test_sql_missing_resource` 抛出的 `NameError` 消息可能包含单引号或格式差异，导致正则匹配失败。

~~~~~act
patch_file
tests/providers/test_sql.py
~~~~~
~~~~~old
@pytest.mark.asyncio
async def test_sql_missing_resource():
    """Test failure when the specified DB resource is not registered."""

    target = cs.sql("SELECT 1", db="non_existent_db")

    engine = cs.Engine()
    # We don't register anything

    # Should fail during execution when trying to resolve the Inject object
    # Or during setup if we scan correctly?
    # With the new scanning logic, it should fail at setup time!

    with pytest.raises(NameError, match="not registered"):
        await engine.run(target)
~~~~~
~~~~~new
@pytest.mark.asyncio
async def test_sql_missing_resource():
    """Test failure when the specified DB resource is not registered."""

    target = cs.sql("SELECT 1", db="non_existent_db")

    engine = cs.Engine()
    # We don't register anything

    # Should fail during execution when trying to resolve the Inject object
    # Or during setup if we scan correctly?
    # With the new scanning logic, it should fail at setup time!

    # The error message from engine.py is: f"Resource '{name}' is required but not registered."
    with pytest.raises(NameError, match="not registered"):
        await engine.run(target)
~~~~~

#### Acts 3: 诊断 CLI Context 问题

我怀疑 `test_cli.py` 中的 `workflow_def` 在被 `cs.cli` 调用前并没有被执行，或者 `get_current_context` 的上下文在 `CliRunner` 的隔离环境中丢失了。
但仔细看测试代码：
```python
    target = workflow_def() 
    app = cs.cli(target) 
```
`workflow_def` 已经被显式调用了，所以 Context 应该被填充了。
问题可能出在 `cs.cli` 实现中如何获取 Context。
在 `src/cascade/tools/cli.py` 中：
```python
    context = get_current_context()
    all_specs = context.get_all_specs()
```
如果 `cs.Param` 工厂确实工作正常，`all_specs` 应该包含定义的参数。
让我们在 `test_cli.py` 中增加调试信息或者确保 import 正确。
其实 `cs.Param` 依赖 `get_current_context`。
如果 `cs` 模块被重载，可能会有多个 Context 实例？
`from cascade.context import get_current_context` 是单例 ContextVar 包装器。

可能的问题是 `test_cli_generator_from_context` 中使用的 `get_current_context()` 和 `cs.Param` 内部使用的不是同一个对象？不应该。
让我们检查 `cs.cli` 的实现是否过滤太严，或者 Spec 对象类型不对。

我将修改 `tests/tools/test_cli.py`，使其更健壮，并验证 Context 确实被填充。

~~~~~act
patch_file
tests/tools/test_cli.py
~~~~~
~~~~~old
    # 2. 模拟“导入时执行”：先运行一次定义，填充上下文
    target = workflow_def() 
    
    # 3. 生成 CLI
    # 注意：v1.3 cs.cli 可能既支持 LazyResult (为了兼容)，
    # 也支持直接利用 Context。这里我们传 target，验证它能否正确提取 Context 中的 Specs。
    app = cs.cli(target) 
    
    # 4. 验证 Help 信息 (证明 Spec 被正确读取)
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--name" in result.stdout
    assert "--count" in result.stdout
    assert "User name" in result.stdout
~~~~~
~~~~~new
    # 2. 模拟“导入时执行”：先运行一次定义，填充上下文
    target = workflow_def() 
    
    # Debug: Verify context is populated
    from cascade.context import get_current_context
    specs = get_current_context().get_all_specs()
    assert len(specs) == 2, f"Context should have 2 specs, got {len(specs)}"

    # 3. 生成 CLI
    # 注意：v1.3 cs.cli 可能既支持 LazyResult (为了兼容)，
    # 也支持直接利用 Context。这里我们传 target，验证它能否正确提取 Context 中的 Specs。
    app = cs.cli(target) 
    
    # 4. 验证 Help 信息 (证明 Spec 被正确读取)
    result = runner.invoke(app, ["--help"])
    if result.exit_code != 0:
        print(result.stdout)
    assert result.exit_code == 0
    assert "--name" in result.stdout
    assert "--count" in result.stdout
    assert "User name" in result.stdout
~~~~~

### 下一步建议
运行测试，确认 `NameError` 是否消除，并检查 CLI 测试的新断言是否通过。如果有其他失败，将更容易定位。
