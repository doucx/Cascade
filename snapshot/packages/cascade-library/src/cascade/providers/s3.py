from cascade.spec.task import task
from cascade.spec.protocols import LazyFactory, Provider

try:
    import aiobotocore.session
except ImportError:
    aiobotocore = None


class S3ProviderBase(Provider):
    def _check_dependency(self):
        if aiobotocore is None:
            raise ImportError(
                "The 'aiobotocore' library is required to use S3 providers. "
                "Please install it with: pip install cascade-py[s3]"
            )


# --- Tasks ---


@task(name="s3_read_text")
async def _s3_read_text(bucket: str, key: str, encoding: str = "utf-8") -> str:
    if aiobotocore is None:
        raise ImportError("aiobotocore is required for S3 tasks.")
    session = aiobotocore.session.get_session()  # type: ignore
    async with session.create_client("s3") as client:  # type: ignore
        response = await client.get_object(Bucket=bucket, Key=key)
        async with response["Body"] as stream:
            data = await stream.read()
            return data.decode(encoding)


@task(name="s3_read_bytes")
async def _s3_read_bytes(bucket: str, key: str) -> bytes:
    session = aiobotocore.session.get_session()  # type: ignore
    async with session.create_client("s3") as client:  # type: ignore
        response = await client.get_object(Bucket=bucket, Key=key)
        async with response["Body"] as stream:
            return await stream.read()


@task(name="s3_write_text")
async def _s3_write_text(
    bucket: str, key: str, content: str, encoding: str = "utf-8"
) -> None:
    data = content.encode(encoding)
    session = aiobotocore.session.get_session()  # type: ignore
    async with session.create_client("s3") as client:  # type: ignore
        await client.put_object(Bucket=bucket, Key=key, Body=data)


@task(name="s3_write_bytes")
async def _s3_write_bytes(bucket: str, key: str, content: bytes) -> None:
    session = aiobotocore.session.get_session()  # type: ignore
    async with session.create_client("s3") as client:  # type: ignore
        await client.put_object(Bucket=bucket, Key=key, Body=content)


# --- Providers ---


class S3ReadTextProvider(S3ProviderBase):
    name = "io.s3.read_text"

    def create_factory(self) -> LazyFactory:
        self._check_dependency()
        return _s3_read_text


class S3ReadBytesProvider(S3ProviderBase):
    name = "io.s3.read_bytes"

    def create_factory(self) -> LazyFactory:
        self._check_dependency()
        return _s3_read_bytes


class S3WriteTextProvider(S3ProviderBase):
    name = "io.s3.write_text"

    def create_factory(self) -> LazyFactory:
        self._check_dependency()
        return _s3_write_text


class S3WriteBytesProvider(S3ProviderBase):
    name = "io.s3.write_bytes"

    def create_factory(self) -> LazyFactory:
        self._check_dependency()
        return _s3_write_bytes
