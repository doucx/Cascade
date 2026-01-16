你指出的问题非常典型：在实施了严格的依赖注入（DI）之后，所有之前依赖 `Engine` 默认构造行为的代码都“现形”了。这包括了大量的集成测试，以及 `cascade-library` 中的生产代码（如 `subflow` 任务）。

这种“阵痛”是值得的，因为它清晰地勾勒出了系统中哪些地方在进行“非法的”重型组件组装。

我将按照以下计划进行全面修复：

1.  **修复 `cascade-library` 生产代码**: 修复 `subflow.py`，确保它能够正确组装一个子引擎。
2.  **更新所有受影响的集成测试**: 将 `cascade-library` 中所有手动实例化 `Engine` 的测试改为使用我们新定义的 `engine` 或 `engine_factory` fixture。

## [WIP] fix: Align cascade-library and its tests with new Engine DI architecture

### 错误分析

核心问题是 `Engine` 的构造函数现在是严格的 DI 模式，不再提供默认的执行策略和约束管理器。`cascade-library` 中的集成测试和 `subflow` 任务仍然沿用旧的调用方式 `cs.Engine(...)`，导致 `TypeError`。

### 用户需求

修复 `cascade-library` 包中所有的集成测试失败，并确保生产代码中的子引擎实例化也能正常工作。

### 评论

这是一个在大规模重构中常见的清理阶段。通过将测试中的手动组装替换为统一的 `engine` fixture，我们不仅修复了错误，还显著简化了测试代码，使其更易于维护。对于生产代码中的子引擎，我们将引入一套标准的组装逻辑，确保其功能完整。

### 目标

1.  定位并修改 `packages/cascade-library/src/cascade/providers/subflow.py`（如果存在），确保其子引擎实例化符合新协议。
2.  批量更新 `packages/cascade-library/tests/integration/` 下的所有测试文件：
    *   移除 `cs.Engine(...)` 的手动创建。
    *   引入并使用 `engine` fixture。
    *   移除不再需要的 `NativeSolver` 和 `LocalExecutor` 导入。

### 基本原理

在测试环境中，我们将全面拥抱 Pytest fixture。由于 `engine` fixture 已经在根目录的 `conftest.py` 中定义，且 `cascade-library` 处于同一个 monorepo 中，这些 fixture 是全局可用的。通过在测试函数参数中声明 `engine`，Pytest 会自动注入一个预先配置好的、架构正确的引擎实例。

### 标签

#intent/fix #flow/ready #priority/critical #comp/library #comp/tests #scope/core #dx #ai/instruct #task/domain/library #task/object/integration-tests #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 批量更新集成测试文件

我将对你提供的所有失败测试文件进行修正。

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_config.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_load_yaml_provider(dummy_config_file):
    loaded_data = cs.load_yaml(dummy_config_file)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    result = await engine.run(loaded_data)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_load_yaml_provider(engine, dummy_config_file):
    loaded_data = cs.load_yaml(dummy_config_file)

    result = await engine.run(loaded_data)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_config.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_lookup_provider_basic(dummy_config_file):
    # 1. Explicitly load the config
    config_source = cs.load_yaml(dummy_config_file)

    # 2. Explicitly look up the value
    version = cs.lookup(source=config_source, key="project.version")

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    result = await engine.run(version)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_lookup_provider_basic(engine, dummy_config_file):
    # 1. Explicitly load the config
    config_source = cs.load_yaml(dummy_config_file)

    # 2. Explicitly look up the value
    version = cs.lookup(source=config_source, key="project.version")

    result = await engine.run(version)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_config.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_lookup_on_static_dict():
    @cs.task
    def provide_dict():
        return {"a": {"b": 10}}

    source = provide_dict()
    value = cs.lookup(source=source, key="a.b")

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    result = await engine.run(value)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_lookup_on_static_dict(engine):
    @cs.task
    def provide_dict():
        return {"a": {"b": 10}}

    source = provide_dict()
    value = cs.lookup(source=source, key="a.b")

    result = await engine.run(value)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_config.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_lookup_missing_key_raises_error():
    @cs.task
    def provide_dict():
        return {"a": 1}

    source = provide_dict()
    # "b" does not exist in the root dict, should raise KeyError
    missing_value = cs.lookup(source=source, key="b")

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    with pytest.raises(KeyError):
        await engine.run(missing_value)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_lookup_missing_key_raises_error(engine):
    @cs.task
    def provide_dict():
        return {"a": 1}

    source = provide_dict()
    # "b" does not exist in the root dict, should raise KeyError
    missing_value = cs.lookup(source=source, key="b")

    with pytest.raises(KeyError):
        await engine.run(missing_value)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_config.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_lookup_invalid_path_raises_type_error():
    @cs.task
    def provide_dict():
        return {"a": 1}

    source = provide_dict()
    # "a" resolves to 1 (int), which is not a container.
    # Attempting to look up "nonexistent" on it should raise TypeError.
    invalid_lookup = cs.lookup(source=source, key="a.nonexistent")

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    with pytest.raises(TypeError, match="Cannot access segment"):
        await engine.run(invalid_lookup)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_lookup_invalid_path_raises_type_error(engine):
    @cs.task
    def provide_dict():
        return {"a": 1}

    source = provide_dict()
    # "a" resolves to 1 (int), which is not a container.
    # Attempting to look up "nonexistent" on it should raise TypeError.
    invalid_lookup = cs.lookup(source=source, key="a.nonexistent")

    with pytest.raises(TypeError, match="Cannot access segment"):
        await engine.run(invalid_lookup)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_file.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_file_read_text_success(dummy_file):
    read_result = cs.read.text(dummy_file)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    result = await engine.run(read_result)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_file_read_text_success(engine, dummy_file):
    read_result = cs.read.text(dummy_file)

    result = await engine.run(read_result)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_file.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_file_read_bytes_success(binary_file):
    read_result = cs.read.bytes(binary_file)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    result = await engine.run(read_result)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_file_read_bytes_success(engine, binary_file):
    read_result = cs.read.bytes(binary_file)

    result = await engine.run(read_result)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_file.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_file_exists_true(dummy_file):
    exist_result = cs.fs.exists(dummy_file)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    result = await engine.run(exist_result)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_file_exists_true(engine, dummy_file):
    exist_result = cs.fs.exists(dummy_file)

    result = await engine.run(exist_result)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_file.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_file_exists_false(tmp_path):
    path = str(tmp_path / "non_existent.txt")
    exist_result = cs.fs.exists(path)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    result = await engine.run(exist_result)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_file_exists_false(engine, tmp_path):
    path = str(tmp_path / "non_existent.txt")
    exist_result = cs.fs.exists(path)

    result = await engine.run(exist_result)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_file.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_file_json_parsing_composition(dummy_file):
    @cs.task
    def parse_json(text: str):
        return json.loads(text)

    # Chain the new atomic providers
    text_content = cs.read.text(dummy_file)
    json_result = parse_json(text_content)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    result = await engine.run(json_result)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_file_json_parsing_composition(engine, dummy_file):
    @cs.task
    def parse_json(text: str):
        return json.loads(text)

    # Chain the new atomic providers
    text_content = cs.read.text(dummy_file)
    json_result = parse_json(text_content)

    result = await engine.run(json_result)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_file.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_file_dynamic_path_dependency(tmp_path):
    @cs.task
    def generate_path() -> str:
        p = tmp_path / "dynamic.txt"
        p.write_text("dynamic content")
        return str(p)

    path_result = generate_path()
    read_result = cs.read.text(path_result)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    result = await engine.run(read_result)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_file_dynamic_path_dependency(engine, tmp_path):
    @cs.task
    def generate_path() -> str:
        p = tmp_path / "dynamic.txt"
        p.write_text("dynamic content")
        return str(p)

    path_result = generate_path()
    read_result = cs.read.text(path_result)

    result = await engine.run(read_result)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_helpers.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_dict_provider():
    @cs.task
    def get_val():
        return "dynamic_value"

    workflow = cs.dict(static_key="static", dynamic_key=get_val())

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=EventBus())
    result = await engine.run(workflow)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_dict_provider(engine):
    @cs.task
    def get_val():
        return "dynamic_value"

    workflow = cs.dict(static_key="static", dynamic_key=get_val())

    result = await engine.run(workflow)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_helpers.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_format_provider():
    @cs.task
    def get_name():
        return "World"

    workflow = cs.format("Hello, {name}!", name=get_name())

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=EventBus())
    result = await engine.run(workflow)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_format_provider(engine):
    @cs.task
    def get_name():
        return "World"

    workflow = cs.format("Hello, {name}!", name=get_name())

    result = await engine.run(workflow)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_helpers.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_format_provider_with_positional_args():
    @cs.task
    def get_first():
        return "first"

    @cs.task
    def get_second():
        return "second"

    workflow = cs.format("Positional: {}, {}", get_first(), get_second())

    engine = Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=EventBus())
    result = await engine.run(workflow)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_format_provider_with_positional_args(engine):
    @cs.task
    def get_first():
        return "first"

    @cs.task
    def get_second():
        return "second"

    workflow = cs.format("Positional: {}, {}", get_first(), get_second())

    result = await engine.run(workflow)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_http.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_http_get_success(aiohttp_client):
    async def handler(request):
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_http_get_success(engine, aiohttp_client):
    async def handler(request):
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_http.py
~~~~~
~~~~~python.old
    final_result = process_user(api_response)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    result = await engine.run(final_result)
    assert result == "cascade"
~~~~~
~~~~~python.new
    final_result = process_user(api_response)

    result = await engine.run(final_result)
    assert result == "cascade"
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_http.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_http_post_success(aiohttp_client):
    async def handler(request):
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_http_post_success(engine, aiohttp_client):
    async def handler(request):
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_http.py
~~~~~
~~~~~python.old
    final_result = check_response(api_response)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    result = await engine.run(final_result)
    assert result["received"] == 42
~~~~~
~~~~~python.new
    final_result = check_response(api_response)

    result = await engine.run(final_result)
    assert result["received"] == 42
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_http.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_http_with_template(aiohttp_client):
    async def user_handler(request):
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_http_with_template(engine, aiohttp_client):
    async def user_handler(request):
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_http.py
~~~~~
~~~~~python.old
    final_status = get_status(api_response)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    result = await engine.run(final_status, params={"username": "dynamic_user"})
    assert result == "ok"
~~~~~
~~~~~python.new
    final_status = get_status(api_response)

    result = await engine.run(final_status, params={"username": "dynamic_user"})
    assert result == "ok"
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_io.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_read_text_provider(test_file):
    test_file.write_text("hello cascade")

    # cs.read.text matches "read.text" provider
    lazy = cs.read.text(str(test_file))

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    result = await engine.run(lazy)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_read_text_provider(engine, test_file):
    test_file.write_text("hello cascade")

    # cs.read.text matches "read.text" provider
    lazy = cs.read.text(str(test_file))

    result = await engine.run(lazy)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_io.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_write_text_provider(test_file):
    # cs.write.text matches "write.text" provider
    lazy = cs.write.text(str(test_file), "written by cascade")

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    await engine.run(lazy)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_write_text_provider(engine, test_file):
    # cs.write.text matches "write.text" provider
    lazy = cs.write.text(str(test_file), "written by cascade")

    await engine.run(lazy)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_io.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_fs_exists_provider(test_file):
    # cs.fs.exists matches "fs.exists" provider
    lazy_true = cs.fs.exists(str(test_file))
    lazy_false = cs.fs.exists(str(test_file) + ".missing")

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )

    test_file.touch()
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_fs_exists_provider(engine, test_file):
    # cs.fs.exists matches "fs.exists" provider
    lazy_true = cs.fs.exists(str(test_file))
    lazy_false = cs.fs.exists(str(test_file) + ".missing")

    test_file.touch()
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_s3.py
~~~~~
~~~~~python.old
    write_op = cs.io.s3.write_text(bucket=bucket_name, key=key, content=content)
    read_op = cs.io.s3.read_text(bucket=bucket_name, key=key)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )

    # 3. Execute Write
    await engine.run(write_op)
~~~~~
~~~~~python.new
    write_op = cs.io.s3.write_text(bucket=bucket_name, key=key, content=content)
    read_op = cs.io.s3.read_text(bucket=bucket_name, key=key)

    # 3. Execute Write
    await engine.run(write_op)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_s3.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_s3_write_read_text(s3_mock):
    import aiobotocore.session
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_s3_write_read_text(engine, s3_mock):
    import aiobotocore.session
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_s3.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_s3_write_read_bytes(s3_mock):
    import aiobotocore.session
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_s3_write_read_bytes(engine, s3_mock):
    import aiobotocore.session
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_s3.py
~~~~~
~~~~~python.old
    write_op = cs.io.s3.write_bytes(bucket=bucket_name, key=key, content=content)
    read_op = cs.io.s3.read_bytes(bucket=bucket_name, key=key)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )

    # 2. Execute Write
    await engine.run(write_op)
~~~~~
~~~~~python.new
    write_op = cs.io.s3.write_bytes(bucket=bucket_name, key=key, content=content)
    read_op = cs.io.s3.read_bytes(bucket=bucket_name, key=key)

    # 2. Execute Write
    await engine.run(write_op)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_sql.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_sql_missing_resource():
    target = cs.sql("SELECT 1", conn=cs.inject("non_existent_db"))

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )
    # We don't register anything

    # With the new scanning logic, it should fail at setup time!
    with pytest.raises(NameError, match="not registered"):
        await engine.run(target)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_sql_missing_resource(engine):
    target = cs.sql("SELECT 1", conn=cs.inject("non_existent_db"))

    # We don't register anything

    # With the new scanning logic, it should fail at setup time!
    with pytest.raises(NameError, match="not registered"):
        await engine.run(target)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_subflow.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_subflow_execution(subflow_file):
    # Define a parent workflow that calls the subflow
    # subflow is loaded via provider registry
    sub_result = cs.subflow(
        path=subflow_file, target="result_node", params={"multiplier": 5}
    )

    @cs.task
    def finalize(val):
        return f"Final: {val}"

    workflow = finalize(sub_result)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )

    # 10 * 5 = 50 -> "Final: 50"
    result = await engine.run(workflow)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_subflow_execution(engine, subflow_file):
    # Define a parent workflow that calls the subflow
    # subflow is loaded via provider registry
    sub_result = cs.subflow(
        path=subflow_file, target="result_node", params={"multiplier": 5}
    )

    @cs.task
    def finalize(val):
        return f"Final: {val}"

    workflow = finalize(sub_result)

    # 10 * 5 = 50 -> "Final: 50"
    result = await engine.run(workflow)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_subflow.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_subflow_file_not_found():
    workflow = cs.subflow(path="non_existent.py", target="foo")

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )

    with pytest.raises(FileNotFoundError):
        await engine.run(workflow)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_subflow_file_not_found(engine):
    workflow = cs.subflow(path="non_existent.py", target="foo")

    with pytest.raises(FileNotFoundError):
        await engine.run(workflow)
~~~~~

~~~~~act
patch_file
packages/cascade-library/tests/integration/test_subflow.py
~~~~~
~~~~~python.old
@pytest.mark.asyncio
async def test_subflow_target_not_found(subflow_file):
    workflow = cs.subflow(path=subflow_file, target="missing_var")

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.EventBus()
    )

    with pytest.raises(ValueError, match="Target 'missing_var' not found"):
        await engine.run(workflow)
~~~~~
~~~~~python.new
@pytest.mark.asyncio
async def test_subflow_target_not_found(engine, subflow_file):
    workflow = cs.subflow(path=subflow_file, target="missing_var")

    with pytest.raises(ValueError, match="Target 'missing_var' not found"):
        await engine.run(workflow)
~~~~~

### 下一步建议

我们已经完成了对 `cascade-library` 集成测试和 `subflow` 生产代码的修正。现在，请再次运行测试套件。所有的 `TypeError` 应该都已经消失。如果还有遗漏的直接调用 `Engine()` 的地方，它们会被报错暴露出来，我将继续跟进修复。
