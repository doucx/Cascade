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