import asyncio
import uuid
import pytest
from typing import Any, Dict, Optional, Tuple

from cascade.spec.physical.object import Ref
from cascade.spec.runtime.storage import ObjectStore
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute.local import LocalComputeDelegate


# --- Mocks ---


class MockObjectStore:
    def __init__(self):
        self._data: Dict[str, Any] = {}

    def put(self, obj: Any, metadata: Optional[Dict[str, Any]] = None) -> Ref:
        uri = f"mem://{uuid.uuid4()}"
        self._data[uri] = obj
        return Ref(uri=uri, meta=metadata or {})

    def get(self, ref: Ref) -> Any:
        return self._data[ref.uri]

    def peek(self, ref: Ref) -> Ref:
        return ref

    def delete(self, ref: Ref) -> None:
        pass


def sync_add(a, b):
    return a + b


async def async_mul(a, b):
    await asyncio.sleep(0.01)
    return a * b


def sync_fail():
    raise ValueError("Boom")


# --- Tests ---


@pytest.fixture
def registry():
    reg = CodeRegistry()
    reg.register("hash_add", sync_add)
    reg.register("hash_mul", async_mul)
    reg.register("hash_fail", sync_fail)
    return reg


@pytest.fixture
def store():
    return MockObjectStore()


@pytest.fixture
def delegate(store, registry):
    return LocalComputeDelegate(store, registry)


@pytest.mark.asyncio
async def test_submit_sync_task(delegate, store):
    # Prepare inputs
    ref_a = store.put(10)
    ref_b = store.put(20)

    # Submit
    result_ref = await delegate.submit(
        "hash_add", {"0": ref_a, "1": ref_b}, config={}
    )

    # Verify
    result = store.get(result_ref)
    assert result == 30


@pytest.mark.asyncio
async def test_submit_async_task(delegate, store):
    # Prepare inputs
    ref_a = store.put(10)
    ref_b = store.put(20)

    # Submit
    result_ref = await delegate.submit(
        "hash_mul", {"a": ref_a, "b": ref_b}, config={}
    )

    # Verify
    result = store.get(result_ref)
    assert result == 200


@pytest.mark.asyncio
async def test_argument_resolution_mixed(delegate, store, registry):
    # Register a function taking mixed args
    def mixed(a, b, c=0):
        return a + b + c

    registry.register("hash_mixed", mixed)

    ref_1 = store.put(1)
    ref_2 = store.put(2)
    ref_3 = store.put(3)

    # Submit with positional '0', '1' and keyword 'c'
    result_ref = await delegate.submit(
        "hash_mixed", {"0": ref_1, "1": ref_2, "c": ref_3}, config={}
    )

    assert store.get(result_ref) == 6


@pytest.mark.asyncio
async def test_exception_propagation(delegate, store):
    with pytest.raises(ValueError, match="Boom"):
        await delegate.submit("hash_fail", {}, config={})