import pytest
import cascade as cs
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver

# Skip if dependencies are missing
pytest.importorskip("aiobotocore")
pytest.importorskip("moto")
pytest.importorskip("requests")  # Moto server needs requests sometimes


@pytest.fixture(scope="module")
def aws_credentials():
    import os

    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def s3_mock(aws_credentials, monkeypatch):
    from moto.server import ThreadedMotoServer

    # Start Moto Server in a separate thread
    server = ThreadedMotoServer(
        ip_address="127.0.0.1", port=0
    )  # port 0 lets OS pick a free port
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

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )

    # 3. Execute Write
    await engine.run(write_op)

    # 4. Execute Read
    result = await engine.run(read_op)

    assert result == content


@pytest.mark.asyncio
async def test_s3_write_read_bytes(s3_mock):
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

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )

    # 2. Execute Write
    await engine.run(write_op)

    # 3. Execute Read
    result = await engine.run(read_op)

    assert result == content


def test_s3_import_error(monkeypatch):
    import cascade.providers.s3 as s3_provider_module

    # Simulate missing dependency
    monkeypatch.setattr(s3_provider_module, "aiobotocore", None)

    # Instantiate the provider
    provider = s3_provider_module.S3ReadTextProvider()

    # Try to get the factory
    with pytest.raises(ImportError, match="aiobotocore"):
        provider.create_factory()
