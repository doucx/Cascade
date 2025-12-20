import pickle
import logging
from typing import Any, Optional
import aiohttp

from cascade.interfaces.protocols import CacheBackend

logger = logging.getLogger(__name__)


class IpfsCacheBackend(CacheBackend):
    """
    A cache backend that stores results in IPFS via its HTTP RPC API.

    It uses a secondary 'metadata_backend' (like Redis or In-Memory) to map
    application cache keys to IPFS Content Identifiers (CIDs).

    Structure:
       App Key -> Metadata Backend -> CID -> IPFS -> Serialized Data
    """

    def __init__(
        self,
        metadata_backend: CacheBackend,
        ipfs_api_url: str = "http://127.0.0.1:5001",
    ):
        """
        Args:
            metadata_backend: A fast K-V backend to store Key->CID mappings.
            ipfs_api_url: The base URL of the IPFS RPC API (default: local Kubo node).
        """
        self._meta_db = metadata_backend
        self._api_base = ipfs_api_url.rstrip("/")

    async def get(self, key: str) -> Optional[Any]:
        """Retrieves a CID from metadata and then fetches content from IPFS."""
        # 1. Resolve Key -> CID
        cid = await self._meta_db.get(key)
        if not cid:
            return None

        # 2. Fetch Content from IPFS
        try:
            async with aiohttp.ClientSession() as session:
                # ipfs cat <cid>
                url = f"{self._api_base}/api/v0/cat"
                async with session.post(url, params={"arg": cid}) as resp:
                    if resp.status != 200:
                        logger.warning(
                            f"Failed to fetch CID {cid} from IPFS: {resp.status}"
                        )
                        return None
                    data = await resp.read()

            # 3. Deserialize
            return pickle.loads(data)
        except Exception as e:
            logger.error(f"Error reading from IPFS cache (key={key}, cid={cid}): {e}")
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Serializes value, adds it to IPFS to get a CID, then stores key->CID mapping."""
        try:
            # 1. Serialize
            data = pickle.dumps(value)

            # 2. Upload to IPFS
            async with aiohttp.ClientSession() as session:
                url = f"{self._api_base}/api/v0/add"
                # IPFS expects 'file' field in multipart/form-data
                form = aiohttp.FormData()
                form.add_field("file", data)

                async with session.post(url, data=form) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise RuntimeError(f"IPFS add failed: {resp.status} - {text}")

                    # IPFS add returns JSON: {"Name": "...", "Hash": "Qm...", ...}
                    resp_json = await resp.json()
                    cid = resp_json["Hash"]

            # 3. Store Key -> CID Mapping
            # Note: We apply the TTL to the mapping, effectively expiring the cache entry
            # even though the data remains in IPFS (until GC).
            await self._meta_db.set(key, cid, ttl=ttl)

        except Exception as e:
            logger.error(f"Error writing to IPFS cache (key={key}): {e}")
            # We don't raise here to avoid failing the workflow just because caching failed
