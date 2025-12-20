import os
from contextlib import ExitStack
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
    files: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    """Core logic to perform an HTTP request using aiohttp."""
    if aiohttp is None:
        raise ImportError(
            "The 'aiohttp' library is required to use the http provider. "
            "Please install it with: pip install cascade-py[http]"
        )

    # Use ExitStack to ensure any files opened for upload are closed
    with ExitStack() as stack:
        final_data = data

        if files:
            # If files are provided, we must use FormData
            form = aiohttp.FormData()

            # Add existing data fields if it's a dict
            if isinstance(data, dict):
                for k, v in data.items():
                    form.add_field(k, str(v))

            for field_name, file_path in files.items():
                if isinstance(file_path, str) and os.path.exists(file_path):
                    f = stack.enter_context(open(file_path, "rb"))
                    form.add_field(field_name, f, filename=os.path.basename(file_path))
                else:
                    # Fallback for bytes or other content
                    form.add_field(field_name, file_path)
            
            final_data = form

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.request(
                method, url, params=params, json=json_data, data=final_data
            ) as response:
                # Note: We do NOT raise_for_status() automatically here.
                # We want to return the response object so the user (or a downstream task)
                # can decide how to handle 4xx/5xx codes.
                
                body_bytes = await response.read()

                # We construct the response object FIRST
                resp_obj = HttpResponse(
                    status=response.status,
                    headers=dict(response.headers),
                    body=body_bytes,
                )

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
    files: Optional[Dict[str, str]] = None,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    return await _perform_request(
        url, "POST", params=params, json_data=json, data=data, files=files, headers=headers
    )


@task(name="http_put")
async def _http_put_task(
    url: str,
    json: Optional[Any] = None,
    data: Optional[Any] = None,
    files: Optional[Dict[str, str]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    return await _perform_request(
        url, "PUT", json_data=json, data=data, files=files, headers=headers
    )


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
    files: Optional[Dict[str, str]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> HttpResponse:
    return await _perform_request(
        url, method, params=params, json_data=json, data=data, files=files, headers=headers
    )


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