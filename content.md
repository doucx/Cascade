你的分析非常到位，错误追踪信息非常清晰地指出了问题所在。

## [WIP] fix: 修正 S3 测试中异步 fixture 的使用方式

### 错误分析
测试失败的根本原因是 `pytest-asyncio` 处理 `async def` fixture 的机制与我们的使用方式不匹配。

1.  **Fixture 类型**: 当一个 `async def` 的 pytest fixture 使用 `yield` 时，它返回的不是 `yield` 的值本身，而是一个**异步生成器 (async_generator)** 对象。
2.  **参数传递**: 在我们的测试函数 `test_s3_write_read_text(s3_bucket)` 中，参数 `s3_bucket` 接收到的就是这个 `async_generator` 对象，而不是我们期望的字符串 `test-cascade-bucket`。
3.  **根本错误**: `Cascade` 工作流将这个生成器对象作为 `bucket` 参数一路传递给了底层的 `aiobotocore` 库。`botocore` 的验证层在尝试对桶名执行正则表达式搜索时 (`VALID_BUCKET.search(bucket)`)，收到了一个生成器对象而不是预期的字符串，因此抛出了 `TypeError: expected string or bytes-like object, got 'async_generator'`。

### 用户需求
修复 `tests/providers/test_s3.py` 中因异步 fixture 使用不当而导致的两个测试用例失败。

### 评论
这是一个微妙但很常见的 `asyncio` 与 `pytest` 集成时的陷阱。修复方案是直接且正确的：在测试用例中显式地、异步地从生成器中提取出我们需要的单个值。这确保了传递给业务逻辑的是正确类型的数据。

### 目标
1.  在 `tests/providers/test_s3.py` 中导入 `anext`（或 `asyncio.anext` for Python 3.10+）。
2.  在两个失败的测试用例中，使用 `await anext(s3_bucket)` 来正确地从异步生成器 fixture 中提取出桶名字符串。
3.  使用提取出的字符串变量作为 `cs.io.s3.*` 调用的 `bucket` 参数。

### 基本原理
`anext()` 是用于从异步迭代器（包括异步生成器）中获取下一个项目的标准库函数。由于我们的 fixture 只 `yield` 一次，`await anext(s3_bucket)` 将正确地执行 fixture 直到 `yield` 点，并返回 `yield` 的值。这样，测试的其余部分就能以正确的字符串类型继续执行。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #task/domain/storage #task/object/io-provider #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 修正 S3 测试文件

我们将修改 `tests/providers/test_s3.py`，在两个失败的测试中正确地消费 `s3_bucket` 异步生成器。

~~~~~act
patch_file
tests/providers/test_s3.py
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_s3_write_read_text(s3_bucket):
    """Tests writing and reading a text file from S3."""
    
    # Workflow: Write then Read
    key = "test.txt"
    content = "hello s3"
    
    write_op = cs.io.s3.write_text(bucket=s3_bucket, key=key, content=content)
    
    # The read operation depends on the write operation to complete
    read_op = cs.io.s3.read_text(bucket=s3_bucket, key=key).run_if(write_op)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(read_op)

    assert result == content

@pytest.mark.asyncio
async def test_s3_write_read_bytes(s3_bucket):
    """Tests writing and reading a binary file from S3."""
    key = "test.bin"
    content = b"\x01\x02\x03"
    
    write_op = cs.io.s3.write_bytes(bucket=s3_bucket, key=key, content=content)
    read_op = cs.io.s3.read_bytes(bucket=s3_bucket, key=key).run_if(write_op)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(read_op)

    assert result == content
~~~~~
~~~~~python
@pytest.mark.asyncio
async def test_s3_write_read_text(s3_bucket):
    """Tests writing and reading a text file from S3."""
    
    # Consume the async generator fixture to get the bucket name string
    bucket_name = await anext(s3_bucket)

    # Workflow: Write then Read
    key = "test.txt"
    content = "hello s3"
    
    write_op = cs.io.s3.write_text(bucket=bucket_name, key=key, content=content)
    
    # The read operation depends on the write operation to complete
    read_op = cs.io.s3.read_text(bucket=bucket_name, key=key).run_if(write_op)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(read_op)

    assert result == content

@pytest.mark.asyncio
async def test_s3_write_read_bytes(s3_bucket):
    """Tests writing and reading a binary file from S3."""
    
    bucket_name = await anext(s3_bucket)
    
    key = "test.bin"
    content = b"\x01\x02\x03"
    
    write_op = cs.io.s3.write_bytes(bucket=bucket_name, key=key, content=content)
    read_op = cs.io.s3.read_bytes(bucket=bucket_name, key=key).run_if(write_op)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(read_op)

    assert result == content
~~~~~

### 下一步建议
现在我们已经应用了修复程序，请重新运行测试套件。如果所有测试都通过，我们将确认 `cs.io` 的重构和 S3 Provider 的实现已稳定，可以继续执行路线图中的下一个任务：**任务 1.2: `cs.http` 原子化网络提供者**。
