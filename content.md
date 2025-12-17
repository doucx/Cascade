## [WIP] fix: 修复 S3 测试中的逻辑依赖并应用环境变量配置

### 摘要
我们遇到了 `DependencyMissingError`，这是因为 `run_if` 机制的工作原理导致的：`run_if` 期望上游任务返回“真值” (Truthy)。然而，我们的 `write_text` 任务返回 `None` (Falsy)，导致下游的 `read_text` 任务被判定为“条件不满足”而被跳过。

为了修复这个问题并验证 S3 Provider 的核心功能，我们将测试逻辑改为两步执行：先执行写任务，再执行读任务。这不仅避开了 `run_if` 对返回值的限制，还更清晰地隔离了写入和读取的测试环节。同时，我们整合了之前关于 `moto` 服务器模式和环境变量配置的修复。

### 详细变更
1.  **Fixture 重构**: 使用 `ThreadedMotoServer` 和 `monkeypatch.setenv` 来确保所有 `aiobotocore` 客户端（包括 Provider 内部的）都指向 Mock 服务器。
2.  **测试流程优化**: 移除 `run_if`，将写操作和读操作分为两个独立的 `engine.run()` 调用。

### 完整文件内容

~~~~~act
write_file
tests/providers/test_s3.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver

# Skip if dependencies are missing
pytest.importorskip("aiobotocore")
pytest.importorskip("moto")
pytest.importorskip("requests") # Moto server needs requests sometimes

@pytest.fixture(scope="module")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    import os
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

@pytest.fixture
def s3_mock(aws_credentials, monkeypatch):
    """A sync fixture that runs moto in server mode and configures client via env var."""
    from moto.server import ThreadedMotoServer
    
    # Start Moto Server in a separate thread
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=0) # port 0 lets OS pick a free port
    server.start()
    
    # Get the dynamic port
    host, port = server.get_host_and_port()
    endpoint_url = f"http://{host}:{port}"
    
    # Use monkeypatch to set environment variable for aiobotocore
    # This ensures ANY client created by aiobotocore within the test uses this endpoint
    monkeypatch.setenv("AWS_ENDPOINT_URL_S3", endpoint_url)
    
    yield endpoint_url
    
    server.stop()

# --- Tests ---

@pytest.mark.asyncio
async def test_s3_write_read_text(s3_mock):
    """Tests writing and reading a text file from S3."""
    import aiobotocore.session
    
    bucket_name = "test-cascade-bucket"

    # 1. Setup: Create Bucket
    # Note: Since AWS_ENDPOINT_URL_S3 is set, this client automatically hits moto
    session = aiobotocore.session.get_session()
    async with session.create_client("s3", region_name="us-east-1") as client:
        await client.create_bucket(Bucket=bucket_name)

    # 2. Define Operations
    key = "test.txt"
    content = "hello s3"
    
    write_op = cs.io.s3.write_text(bucket=bucket_name, key=key, content=content)
    read_op = cs.io.s3.read_text(bucket=bucket_name, key=key)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())

    # 3. Execute Write
    await engine.run(write_op)
    
    # 4. Execute Read
    result = await engine.run(read_op)

    assert result == content

@pytest.mark.asyncio
async def test_s3_write_read_bytes(s3_mock):
    """Tests writing and reading a binary file from S3."""
    import aiobotocore.session

    bucket_name = "test-cascade-bucket"

    # 1. Setup
    session = aiobotocore.session.get_session()
    async with session.create_client("s3", region_name="us-east-1") as client:
        await client.create_bucket(Bucket=bucket_name)
    
    key = "test.bin"
    content = b"\x01\x02\x03"
    
    write_op = cs.io.s3.write_bytes(bucket=bucket_name, key=key, content=content)
    read_op = cs.io.s3.read_bytes(bucket=bucket_name, key=key)

    engine = cs.Engine(solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus())

    # 2. Execute Write
    await engine.run(write_op)
    
    # 3. Execute Read
    result = await engine.run(read_op)

    assert result == content

def test_s3_import_error(monkeypatch):
    """Tests that an ImportError is raised if aiobotocore is missing."""
    import cascade.providers.s3 as s3_provider_module
    
    # Simulate missing dependency
    monkeypatch.setattr(s3_provider_module, "aiobotocore", None)
    
    # Instantiate the provider
    provider = s3_provider_module.S3ReadTextProvider()
    
    # Try to get the factory
    with pytest.raises(ImportError, match="aiobotocore"):
        provider.create_factory()
~~~~~
