You've hit another fascinating and deep-seated issue. The analysis is spot-on: the error `TypeError: object bytes can't be used in 'await' expression` happening deep inside `aiobotocore` is a strong signal of an incompatibility between how `moto`'s patching mechanism creates mock responses and how `aiobotocore` expects to consume them.

## [WIP] fix: Refactor S3 tests to use moto server mode for aiobotocore compatibility

### 错误分析
测试失败的根本原因是 `moto` 的默认“装饰器/上下文管理器”模式与 `aiobotocore` 的内部异步 HTTP 处理之间存在不兼容。

1.  **Mocking Mismatch**: `moto` 的 patching 机制在拦截 `aiobotocore` 的请求后，返回了一个 `botocore.awsrequest.AWSResponse` 对象。这个对象的 `.content` 属性是**同步的**（即一个 `bytes` 对象）。
2.  **Async Expectation**: 然而，`aiobotocore` 的 `endpoint.py` 中的代码路径 `await http_response.content` **期望** `.content` 是一个**异步的** awaitable 对象（一个可以 `await` 的协程）。
3.  **The TypeError**: 当 `aiobotocore` 尝试 `await` 一个普通的 `bytes` 对象时，Python 解释器正确地抛出了 `TypeError`，因为字节对象不是一个协程。

这表明，简单的 patching 模式对于这个版本的 `aiobotocore` 和 `moto` 组合来说是不够的。最健壮、最可靠的解决方案是完全放弃 patching，转而使用 `moto` 的 **Server Mode**。

**Server Mode 原理**:
`moto` 会在后台线程中启动一个真实的 Flask web 服务器，该服务器实现了 S3 API 的子集。然后，我们配置 `aiobotocore` 客户端，将它的 API 请求目标 (`endpoint_url`) 从真实的 AWS URL 指向我们本地的 `moto` 服务器。这样一来，`aiobotocore` 会发出真实的、异步的 HTTP 请求，而 `moto` 服务器会像真实的 S3 一样响应，完全绕过了有问题的 patching 层。

### 用户需求
修复 S3 Provider 测试中因 `moto` 与 `aiobotocore` 异步处理不兼容而导致的 `TypeError`。

### 评论
采用 `moto` 的服务器模式是解决此类问题的黄金标准。它将我们的测试从依赖脆弱的、深入库内部的 monkey-patching，转变为一个更清晰、更真实的集成测试模型：我们的客户端正在与一个符合 API 规范的 HTTP 端点进行通信。这不仅修复了当前的 bug，也使我们的测试套件对未来库版本的变化更具韧性。

### 目标
1.  修改 `s3_mock` fixture，使其启动一个 `moto.server.ThreadedMotoServer`。
2.  该 fixture 将 `yield` 出 `moto` 服务器的本地 `endpoint_url` (例如 `http://127.0.0.1:5000`)。
3.  修改测试用例，在创建 `aiobotocore` 客户端时，明确将 `endpoint_url` 参数设置为 fixture 提供的 URL。

### 基本原理
通过将 `aiobotocore` 客户端指向本地的 `moto` 服务器，我们确保了整个交互都是通过标准的异步网络 I/O 进行的。`aiobotocore` 发出请求，`moto` 服务器接收并返回一个符合 HTTP 规范的响应。`aiobotocore` 的异步 HTTP 客户端可以正确地处理这个响应，从而避免了因 mock 对象属性类型不匹配而导致的 `TypeError`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #concept/tooling #task/domain/storage #task/object/io-provider #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 重构 S3 Fixture 以使用 Moto Server Mode

我们将彻底改变 `s3_mock` fixture 的实现，并相应地更新测试用例来使用 `endpoint_url`。

~~~~~act
patch_file
tests/providers/test_s3.py
~~~~~
~~~~~python
@pytest.fixture
def s3_mock(aws_credentials):
    """A sync fixture that activates the moto mock context."""
    from moto import mock_aws
    with mock_aws():
        yield


# --- Tests ---

@pytest.mark.asyncio
async def test_s3_write_read_text(s3_mock):
    """Tests writing and reading a text file from S3."""
    import aiobotocore.session

    # Async setup is now inside the test
    bucket_name = "test-cascade-bucket"
    session = aiobotocore.session.get_session()
    async with session.create_client("s3", region_name="us-east-1") as client:
        await client.create_bucket(Bucket=bucket_name)

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
async def test_s3_write_read_bytes(s3_mock):
    """Tests writing and reading a binary file from S3."""
    import aiobotocore.session

    # Async setup is inside the test
    bucket_name = "test-cascade-bucket"
    session = aiobotocore.session.get_session()
    async with session.create_client("s3", region_name="us-east-1") as client:
        await client.create_bucket(Bucket=bucket_name)
    
    key = "test.bin"
    content = b"\x01\x02\x03"
    
    write_op = cs.io.s3.write_bytes(bucket=bucket_name, key=key, content=content)
    read_op = cs.io.s3.read_bytes(bucket=bucket_name, key=key).run_if(write_op)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(read_op)

    assert result == content
~~~~~
~~~~~python
@pytest.fixture
def s3_mock(aws_credentials):
    """A sync fixture that runs moto in server mode."""
    from moto.server import ThreadedMotoServer
    
    server = ThreadedMotoServer()
    server.start()
    endpoint_url = "http://127.0.0.1:5000"
    yield endpoint_url
    server.stop()


# --- Tests ---

@pytest.mark.asyncio
async def test_s3_write_read_text(s3_mock):
    """Tests writing and reading a text file from S3."""
    import aiobotocore.session
    
    endpoint_url = s3_mock
    bucket_name = "test-cascade-bucket"

    # Async setup using the moto server endpoint
    session = aiobotocore.session.get_session()
    async with session.create_client("s3", region_name="us-east-1", endpoint_url=endpoint_url) as client:
        await client.create_bucket(Bucket=bucket_name)

    # Workflow: Write then Read
    key = "test.txt"
    content = "hello s3"
    
    # We need to re-configure the client used by the provider to use the mock server.
    # We can do this by monkeypatching the session object.
    
    original_create_client = session.create_client

    def mock_create_client(*args, **kwargs):
        kwargs['endpoint_url'] = endpoint_url
        return original_create_client(*args, **kwargs)

    session.create_client = mock_create_client
    
    write_op = cs.io.s3.write_text(bucket=bucket_name, key=key, content=content)
    read_op = cs.io.s3.read_text(bucket=bucket_name, key=key).run_if(write_op)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(read_op)

    assert result == content
    
    # cleanup patch
    session.create_client = original_create_client


@pytest.mark.asyncio
async def test_s3_write_read_bytes(s3_mock):
    """Tests writing and reading a binary file from S3."""
    import aiobotocore.session

    endpoint_url = s3_mock
    bucket_name = "test-cascade-bucket"

    # Async setup
    session = aiobotocore.session.get_session()
    async with session.create_client("s3", region_name="us-east-1", endpoint_url=endpoint_url) as client:
        await client.create_bucket(Bucket=bucket_name)
    
    key = "test.bin"
    content = b"\x01\x02\x03"

    # Monkeypatch the session for the provider
    original_create_client = session.create_client
    def mock_create_client(*args, **kwargs):
        kwargs['endpoint_url'] = endpoint_url
        return original_create_client(*args, **kwargs)
    session.create_client = mock_create_client

    write_op = cs.io.s3.write_bytes(bucket=bucket_name, key=key, content=content)
    read_op = cs.io.s3.read_bytes(bucket=bucket_name, key=key).run_if(write_op)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())
    result = await engine.run(read_op)

    assert result == content
    
    # cleanup patch
    session.create_client = original_create_client
~~~~~

### 下一步建议
这次的修复方案非常底层和健壮，它解决了 `moto` 和 `aiobotocore` 之间最棘手的集成问题。请运行测试。如果成功，我们就可以确认 **任务 1.1** 已完全完成，并可以放心地开始实施路线图中的下一项核心功能。
