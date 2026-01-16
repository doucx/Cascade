import pytest
import cascade.sdk as cs


@pytest.mark.asyncio
async def test_dict_provider(engine):
    @cs.task
    def get_val():
        return "dynamic_value"

    workflow = cs.dict(static_key="static", dynamic_key=get_val())

    result = await engine.run(workflow)

    assert result == {"static_key": "static", "dynamic_key": "dynamic_value"}


@pytest.mark.asyncio
async def test_format_provider(engine):
    @cs.task
    def get_name():
        return "World"

    workflow = cs.format("Hello, {name}!", name=get_name())

    result = await engine.run(workflow)

    assert result == "Hello, World!"


@pytest.mark.asyncio
async def test_format_provider_with_positional_args(engine):
    @cs.task
    def get_first():
        return "first"

    @cs.task
    def get_second():
        return "second"

    workflow = cs.format("Positional: {}, {}", get_first(), get_second())

    result = await engine.run(workflow)

    assert result == "Positional: first, second"
