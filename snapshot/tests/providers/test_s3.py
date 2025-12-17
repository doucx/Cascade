import pytest
import cascade as cs
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver

# anext is in asyncio for Python 3.10+
try:
    from asyncio import anext
except ImportError:
    # Basic fallback for Python 3.9
    async def anext(ait):
        return await ait.__anext__()

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
async def s3_bucket(aws_credentials):
    """Creates a mock S3 bucket for testing."""
    from moto import mock_aws
    import aiobotocore.session
    
    with mock_aws():
        bucket_name = "test-cascade-bucket"
        session = aiobotocore.session.get_session()
        async with session.create_client("s3", region_name="us-east-1") as client:
            await client.create_bucket(Bucket=bucket_name)
            yield bucket_name

# --- Tests ---

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

def test_s3_import_error(monkeypatch):
    """Tests that an ImportError is raised if aiobotocore is missing."""
    import cascade.providers.s3 as s3_provider_module
    
    # Simulate missing dependency
    monkeypatch.setattr(s3_provider_module, "aiobotocore", None)
    
    # Instantiate the provider and try to get the factory
    provider = s3_provider_module.S3ReadTextProvider()
    
    with pytest.raises(ImportError, match="aiobotocore"):
        provider.create_factory()