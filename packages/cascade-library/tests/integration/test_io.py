import pytest
import cascade as cs
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


@pytest.fixture
def test_file(tmp_path):
    return tmp_path / "test.txt"


@pytest.mark.asyncio
async def test_read_text_provider(test_file):
    test_file.write_text("hello cascade")

    # cs.read.text matches "read.text" provider
    lazy = cs.read.text(str(test_file))

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )
    result = await engine.run(lazy)
    assert result == "hello cascade"


@pytest.mark.asyncio
async def test_write_text_provider(test_file):
    # cs.write.text matches "write.text" provider
    lazy = cs.write.text(str(test_file), "written by cascade")

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )
    await engine.run(lazy)

    assert test_file.read_text() == "written by cascade"


@pytest.mark.asyncio
async def test_fs_exists_provider(test_file):
    # cs.fs.exists matches "fs.exists" provider
    lazy_true = cs.fs.exists(str(test_file))
    lazy_false = cs.fs.exists(str(test_file) + ".missing")

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )

    test_file.touch()
    assert await engine.run(lazy_true) is True
    assert await engine.run(lazy_false) is False


def test_provider_registry_namespace_resolution():
    # This requires the entry points to be loaded.
    # Since we are in a test env, we might need to rely on the fact that 'cs' import loaded them
    # or that we registered them via pyproject.toml (if installed in editable mode).
    # If not installed, we can manually register for this unit test.

    from cascade.providers.registry import registry, ProviderNamespace
    from cascade.providers.io import ReadTextProvider

    # Manual registration to ensure test isolation
    registry.register("read.text", ReadTextProvider().create_factory())

    # Access "read" -> should return Namespace
    ns = registry.get("read")
    assert isinstance(ns, ProviderNamespace)

    # Access "read.text" -> should return factory
    factory = ns.text
    assert factory.name == "read_text"  # Task name from @task
