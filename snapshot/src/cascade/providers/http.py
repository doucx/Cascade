from dataclasses import dataclass
from typing import Any, Dict, Optional
from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider

try:
    import aiohttp
except ImportError:
    aiohttp = None


@dataclass
class HttpResponse:
    """A simple, safe data holder for the HTTP response."""

    status: int
    headers: Dict[str, str]
    body: bytes

    def text(self, encoding: str = "utf-8") -> str:
        """Decodes the response body into a string."""
        return self.body.decode(encoding)

    def json(self) -> Any:
        """Parses the response body as JSON and returns a Python object."""
        import json
        return json.loads(self.text())

    def __repr__(self) -> str:
        return f"<HttpResponse status={self.status}>"


async def _perform_request(
    url: str,
    method: str,
    params: Optional[Dict[str, str]] = None,
    json_data: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Any] = None,
) -> HttpResponse:
    """Core logic to perform an HTTP request using aiohttp."""
    if aiohttp is None:
        raise ImportError(
            "The 'aiohttp' library is required to use the http provider. "
            "Please install it with: pip install cascade-py[http]"
        )

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.request(
            method, url, params=params, json=json_data, data=data
        ) as response:
            # Note: We do NOT raise_for_status() automatically here.
            # We want to return the response object so the user (or a downstream task)
            # can decide how to handle 4xx/5xx codes.
            # However, for convenience in simple workflows, users often expect failure on error.
            # But adhering to "Atomic Provider" philosophy, raw HTTP provider should probably
            # just return the response.
            # EDIT: The original implementation did raise_for_status().
            # To be robust, let's read the body first, then check status?
            # Or just let it be.
            # Let's keep it pure: Return the response. If status check is needed,
            # it should be a separate logic or a .with_retry() policy triggered by exception.
            # BUT, .with_retry() only triggers on Exception. If we don't raise, we can't retry on 503.
            # So we MUST raise for 5xx/4xx if we want to use Cascade's retry mechanisms easily.
            # Compromise: raise for status, but capture the body first so we can attach it to the error if needed.
            # Actually, aiohttp's raise_for_status() is good.
            
            body_bytes = await response.read()
            
            # We construct the response object FIRST
            resp_obj = HttpResponse(
                status=response.status,
                headers=dict(response.headers),
                body=body_bytes,
            )
            
            # If we want to allow 404 handling without try/catch in the graph, we shouldn't raise.
            # But then .with_retry() won't work for 503s.
            # Let's verify standard practices. Typically, raw HTTP clients usually have a 'raise_for_status' flag.
            # We'll default to NOT raising, to allow logic like "if 404 do X".
            # Users can use a generic "check_status" task or we can add a flag.
            # Let's NOT raise by default to keep it atomic and pure.
            # User can throw in a downstream task if they want to trigger retry.
            
            return resp_obj


# --- Tasks ---

@task(name="http_get")
async def _http_get_task(
    url: str,
    params: Optional[Dict[str, str]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    return await _perform_request(url, "GET", params=params, headers=headers)


@task(name="http_post")
async def _http_post_task(
    url: str,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    return await _perform_request(url, "POST", params=params, json_data=json, data=data, headers=headers)


@task(name="http_put")
async def _http_put_task(
    url: str,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    return await _perform_request(url, "PUT", json_data=json, data=data, headers=headers)


@task(name="http_delete")
async def _http_delete_task(
    url: str,
    headers: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    return await _perform_request(url, "DELETE", headers=headers)


@task(name="http_request")
async def _http_request_task(
    url: str,
    method: str = "GET",
    params: Optional[Dict[str, str]] = None,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    headers: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    return await _perform_request(url, method, params=params, json_data=json, data=data, headers=headers)


# --- Providers ---

class HttpGetProvider(Provider):
    name = "http.get"
    def create_factory(self) -> LazyFactory:
        return _http_get_task

class HttpPostProvider(Provider):
    name = "http.post"
    def create_factory(self) -> LazyFactory:
        return _http_post_task

class HttpPutProvider(Provider):
    name = "http.put"
    def create_factory(self) -> LazyFactory:
        return _http_put_task

class HttpDeleteProvider(Provider):
    name = "http.delete"
    def create_factory(self) -> LazyFactory:
        return _http_delete_task

class HttpRequestProvider(Provider):
    name = "http.request"
    def create_factory(self) -> LazyFactory:
        return _http_request_task