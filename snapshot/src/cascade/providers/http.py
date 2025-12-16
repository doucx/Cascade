from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    import aiohttp
except ImportError:
    aiohttp = None

from cascade.spec.task import task
from cascade.providers import LazyFactory


@dataclass
class HttpResponse:
    """A wrapper around the aiohttp response for a better downstream API."""

    _session: aiohttp.ClientSession
    _response: aiohttp.ClientResponse

    @property
    def status(self) -> int:
        return self._response.status

    async def json(self) -> Any:
        return await self._response.json()

    async def text(self) -> str:
        return await self._response.text()

    async def read(self) -> bytes:
        return await self._response.read()

    def __repr__(self) -> str:
        return f"<HttpResponse status={self.status}>"


class HttpProvider:
    name = "http"

    def create_factory(self) -> LazyFactory:
        if aiohttp is None:
            raise ImportError(
                "The 'aiohttp' library is required to use the http provider. "
                "Please install it with: pip install cascade-py[http]"
            )
        return _http_task


@task(name="http")
async def _http_task(
    url: str,
    method: str = "GET",
    params: Optional[Dict[str, str]] = None,
    json_data: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    """
    Performs an asynchronous HTTP request.
    """
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.request(
            method, url, params=params, json=json_data
        ) as response:
            # Ensure the response is fully read or buffered if needed,
            # but for now we pass the raw response to the wrapper.
            # The wrapper will handle reading the body on demand.
            # IMPORTANT: The session will be closed, so the response object
            # must be used within the task that receives it. This is a limitation
            # we might need to address later by e.g. reading the body here.
            # For now, let's keep it simple and assume immediate consumption.

            # Re-evaluating: To make this safe, we should probably return a simple
            # wrapper that already contains the read data. Let's adjust.

            # The session will close, so we need to read the content now.
            # We'll create a more robust wrapper that holds the data.

            # This is a better design:
            final_response = SimpleHttpResponse(
                status=response.status,
                headers=dict(response.headers),
                body=await response.read(),
            )
            response.raise_for_status()
            return final_response


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
