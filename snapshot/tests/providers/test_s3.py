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

def test_s3_import_error(monkeypatch):
    """Tests that an ImportError is raised if aiobotocore is missing."""
    import cascade.providers.s3 as s3_provider_module
    
    # Simulate missing dependency
    monkeypatch.setattr(s3_provider_module, "aiobotocore", None)
    
    # Instantiate the provider and try to get the factory
    provider = s3_provider_module.S3ReadTextProvider()
    
    with pytest.raises(ImportError, match="aiobotocore"):
        provider.create_factory()