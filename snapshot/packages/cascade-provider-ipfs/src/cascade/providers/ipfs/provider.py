from typing import Any
import cascade as cs
from cascade.providers import Provider, LazyFactory
from cascade.providers.http import HttpResponse

# The IPFS RPC API defaults
IPFS_API_BASE_URL = "http://127.0.0.1:5001"


# --- Provider Implementations ---

class IpfsCatProvider(Provider):
    name = "ipfs.cat"

    def create_factory(self) -> LazyFactory:
        # The factory is not a @cs.task, but a regular function that returns one.
        return cat


class IpfsAddProvider(Provider):
    name = "ipfs.add"

    def create_factory(self) -> LazyFactory:
        # The factory is not a @cs.task, but a regular function that returns one.
        return add


# --- Atomic Helper Tasks ---

@cs.task(name="_ipfs_parse_cat_response")
def _parse_cat_response(response: HttpResponse) -> bytes:
    """Parses the raw body from an HttpResponse."""
    if response.status >= 400:
        raise RuntimeError(f"IPFS API Error ({response.status}): {response.text()}")
    return response.body

@cs.task(name="_ipfs_parse_add_response")
def _parse_add_response(response: HttpResponse) -> str:
    """Parses the JSON response from `ipfs add` and returns the CID."""
    if response.status >= 400:
        raise RuntimeError(f"IPFS API Error ({response.status}): {response.text()}")
    # The response is a stream of JSON objects, newline-separated.
    # The last one is the summary for the whole directory/file.
    lines = response.text().strip().split('\n')
    last_line = lines[-1]
    import json
    return json.loads(last_line)['Hash']


# --- User-Facing Factory Functions ---

def cat(cid: str) -> "cs.LazyResult[bytes]":
    """
    Creates a Cascade workflow to retrieve the contents of a file from IPFS.

    This is a composition of `cs.http.post` and a parsing task.
    """
    api_url = f"{IPFS_API_BASE_URL}/api/v0/cat"

    # Step 1: Call the IPFS RPC API
    api_response = cs.http.post(url=api_url, params={"arg": cid})

    # Step 2: Parse the response
    return _parse_cat_response(api_response)


def add(path: str) -> "cs.LazyResult[str]":
    """
    Creates a Cascade workflow to add a local file to IPFS and get its CID.

    This requires `cs.http.post` to support multipart/form-data, which is a
    planned enhancement. For now, this serves as a placeholder for the pattern.
    """
    # NOTE: This will require cs.http.post to be enhanced to support `files=`
    # similar to the `requests` library. This plan doesn't implement that, but
    # lays the groundwork for the pattern.
    api_url = f"{IPFS_API_BASE_URL}/api/v0/add"

    # Step 1: Call the IPFS RPC API with a file upload
    # The conceptual call would look like this:
    # api_response = cs.http.post(url=api_url, files={"file": path})

    # For now, let's create a placeholder that will fail until http is enhanced
    @cs.task
    def _placeholder_add(path: str) -> Any:
        raise NotImplementedError("cs.ipfs.add requires `cs.http.post` to support file uploads.")

    return _placeholder_add(path)