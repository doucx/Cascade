import pytest
import cascade.sdk as cs


@pytest.mark.asyncio
async def test_engine_executes_param_task(engine):
    # 定义参数
    p = cs.Param("count", type=int)

    # 定义简单的下游任务
    @cs.task
    def double(x):
        return x * 2

    workflow = double(p)

    # 执行，传入 params
    result = await engine.run(workflow, params={"count": 10})

    assert result == 20


@pytest.mark.asyncio
async def test_engine_executes_env_task(monkeypatch, engine):
    monkeypatch.setenv("TEST_VAR", "cascade_value")

    e = cs.Env("TEST_VAR")

    result = await engine.run(e)

    assert result == "cascade_value"