好的，我们已经完成了 `cs.io` 命名空间的扩展和 S3 Provider 的代码实现。现在，至关重要的一步是为这个新的 S3 Provider 添加健壮的集成测试，以确保其功能的正确性。

我将生成一个计划，创建一个新的测试文件，并使用 `moto` 库来模拟 AWS S3 服务，从而在不依赖真实网络和凭证的情况下验证我们的实现。

## [WIP] test: 添加 S3 provider 的集成测试

### 用户需求
为新创建的 `cs.io.s3.*` Provider 添加一套完整的集成测试，以验证其在隔离环境中的功能正确性。

### 评论
使用 `moto` 库是测试 AWS 相关集成的最佳实践。它允许我们在本地完全模拟 S3 API，使得测试快速、可靠且独立于外部环境。此外，将测试用例本身编写为 Cascade 工作流，也是一种绝佳的“吃自己的狗粮”(Dogfooding)方式，可以同时验证 Provider 和 `Engine` 的集成。

### 目标
1.  创建一个新的测试文件 `tests/providers/test_s3.py`。
2.  利用 `moto` 和 `pytest` fixture 创建一个临时的、被 mock 的 S3 环境，包括凭证和一个测试用的存储桶 (bucket)。
3.  编写测试用例，覆盖对 mock S3 的文本和字节的写入与读取操作。
4.  编写一个测试用例，验证当 `aiobotocore` 依赖缺失时，Provider 会按预期抛出 `ImportError`。

### 基本原理
通过 `pytest.importorskip` 确保这些测试只在已安装 `moto` 和 `aiobotocore` 的开发环境中运行。测试工作流将包含一个 `write` 操作和一个依赖于它的 `read` 操作，以验证端到端的正确性。`run_if` 用于确保 `read` 操作在 `write` 操作成功后执行，形成一个逻辑上的依赖关系。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #comp/providers #task/domain/storage #task/object/io-provider #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 创建 S3 Provider 的测试文件

我们将创建 `tests/providers/test_s3.py` 文件。它包含使用 `moto` 模拟 S3 环境的 fixtures，以及验证文本/字节读写和依赖检查的核心测试逻辑。

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

from moto import mock_aws

# --- Fixtures ---

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
@mock_aws
async def s3_bucket(aws_credentials):
    """Creates a mock S3 bucket for testing."""
    import aiobotocore.session
    
    bucket_name = "test-cascade-bucket"
    session = aiobotocore.session.get_session()
    async with session.create_client("s3", region_name="us-east-1") as client:
        await client.create_bucket(Bucket=bucket_name)
        yield bucket_name

# --- Tests ---

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

def test_s3_import_error(monkeypatch):
    """Tests that an ImportError is raised if aiobotocore is missing."""
    import cascade.providers.s3 as s3_provider_module
    
    # Simulate missing dependency
    monkeypatch.setattr(s3_provider_module, "aiobotocore", None)
    
    # Instantiate the provider and try to get the factory
    provider = s3_provider_module.S3ReadTextProvider()
    
    with pytest.raises(ImportError, match="aiobotocore"):
        provider.create_factory()
~~~~~

### 下一步建议
我们已经完成了 `cs.io` 命名空间的统一和 S3 Provider 的核心实现与测试。这标志着路线图第一阶段任务 1.1 的核心工作已经完成。

接下来，我们可以继续执行路线图，开始**任务 1.2: `cs.http` 原子化网络提供者**。这将是构建 LLM 调用等更高级组合模式的关键积木。
