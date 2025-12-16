from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    import aiohttp
except ImportError:
    aiohttp = None

from cascade.spec.task import task
from cascade.providers import LazyFactory


class HttpProvider:
    name = "http"

    def create_factory(self) -> LazyFactory:
        if aiohttp is None:
            raise ImportError(
                "The 'aiohttp' library is required to use the http provider. "
                "Please install it with: pip install cascade-py[http]"
            )
        return _http_task


@dataclass
class SimpleHttpResponse:
    """A simple, safe data holder for the HTTP response."""

    status: int
    headers: Dict[str, str]
    body: bytes

    def text(self) -> str:
        """Decodes the response body into a string, assuming utf-8."""
        return self.body.decode("utf-8")

    def json(self) -> Any:
        """Parses the response body as JSON and returns a Python object."""
        import json

        return json.loads(self.text())

    def __repr__(self) -> str:
        return f"<HttpResponse status={self.status}>"


# Let's refine the task to return the SimpleHttpResponse
@task(name="http")
async def _http_task(
    url: str,
    method: str = "GET",
    params: Optional[Dict[str, str]] = None,
    json_data: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
) -> SimpleHttpResponse:
    """
    Performs an asynchronous HTTP request and returns a data-safe response object.
    """
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.request(
            method, url, params=params, json=json_data
        ) as response:
            response.raise_for_status()  # Raise exception for non-2xx status

            return SimpleHttpResponse(
                status=response.status,
                headers=dict(response.headers),
                body=await response.read(),
            )
