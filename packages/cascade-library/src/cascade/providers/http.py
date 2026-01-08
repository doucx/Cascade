import os
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union, Tuple, IO
from cascade.spec.dsl.task import task
from cascade.spec.runtime.interfaces import LazyFactory, Provider

try:
    import httpx
except ImportError:
    httpx = None


@dataclass
class HttpResponse:
    status: int
    headers: Dict[str, str]
    body: bytes

    def text(self, encoding: str = "utf-8") -> str:
        return self.body.decode(encoding)

    def json(self) -> Any:
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
    if httpx is None:
        raise ImportError(
            "The 'httpx' library is required to use the http provider. "
            "Please install it with: pip install cascade-py[http]"
        )

    # Use ExitStack to ensure any files opened for upload are closed
    with ExitStack() as stack:
        # Prepare files for httpx
        httpx_files: Optional[Dict[str, Union[IO[bytes], Tuple[str, IO[bytes]]]]] = None
        
        if files:
            httpx_files = {}
            for field_name, file_path in files.items():
                if isinstance(file_path, str) and os.path.exists(file_path):
                    f = stack.enter_context(open(file_path, "rb"))
                    httpx_files[field_name] = (os.path.basename(file_path), f)
                else:
                    httpx_files[field_name] = file_path  # type: ignore

        # In httpx, if 'data' is a dict and 'files' is present, it handles multipart/form-data.
        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            response = await client.request(
                method,
                url,
                params=params,
                json=json_data,
                data=data,
                files=httpx_files,
            )
            
            # Construct the response object
            resp_obj = HttpResponse(
                status=response.status_code,
                headers=dict(response.headers),
                body=response.content,
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
        url,
        "POST",
        params=params,
        json_data=json,
        data=data,
        files=files,
        headers=headers,
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
        url,
        method,
        params=params,
        json_data=json,
        data=data,
        files=files,
        headers=headers,
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