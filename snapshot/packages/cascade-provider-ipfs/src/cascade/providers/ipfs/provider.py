import json
import cascade as cs
from cascade.providers import Provider, LazyFactory

try:
    import aiohttp
except ImportError:
    aiohttp = None


# --- Provider Implementations ---


class IpfsCatProvider(Provider):
    name = "ipfs.cat"

    def create_factory(self) -> LazyFactory:
        if aiohttp is None:
            raise ImportError(
                "The 'aiohttp' library is required. Please install it with: pip install aiohttp"
            )
        return _ipfs_cat_task


class IpfsAddProvider(Provider):
    name = "ipfs.add"

    def create_factory(self) -> LazyFactory:
        if aiohttp is None:
            raise ImportError(
                "The 'aiohttp' library is required. Please install it with: pip install aiohttp"
            )
        return _ipfs_add_task


# --- Atomic Tasks ---


@cs.task(name="ipfs_cat")
async def _ipfs_cat_task(
    cid: str, api_base_url: str = "http://127.0.0.1:5001"
) -> bytes:
    """
    Fetches content from IPFS for a given CID.
    """
    async with aiohttp.ClientSession() as session:
        url = f"{api_base_url}/api/v0/cat"
        async with session.post(url, params={"arg": cid}) as resp:
            if resp.status >= 400:
                body = await resp.text()
                raise RuntimeError(f"IPFS API Error ({resp.status}): {body}")
            return await resp.read()


@cs.task(name="ipfs_add")
async def _ipfs_add_task(path: str, api_base_url: str = "http://127.0.0.1:5001") -> str:
    """
    Adds a local file to IPFS and returns its CID.
    """
    form = aiohttp.FormData()
    # Note: This reads the whole file into memory. For large files, a streaming
    # approach would be better, but this simplifies the task implementation.
    with open(path, "rb") as f:
        form.add_field("file", f)

        async with aiohttp.ClientSession() as session:
            url = f"{api_base_url}/api/v0/add"
            async with session.post(url, data=form) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    raise RuntimeError(f"IPFS API Error ({resp.status}): {body}")

                # The response is a stream of JSON objects, newline-separated.
                # The last one is the summary for the whole directory/file.
                lines = (await resp.text()).strip().split("\n")
                last_line = lines[-1]
                return json.loads(last_line)["Hash"]
