import pytest
import cascade as cs
# 注意：在实现阶段需要确保这些模块存在
# from cascade.context import get_current_context

@pytest.mark.asyncio
async def test_engine_executes_param_task():
    """验证 Engine 能正确地将 params 注入到 _get_param_value 任务中。"""
    
    # 定义参数
    p = cs.Param("count", type=int)
    
    # 定义简单的下游任务
    @cs.task
    def double(x):
        return x * 2
        
    workflow = double(p)
    
    engine = cs.Engine()
    
    # 执行，传入 params
    # 这里的关键是 Engine 需要将 {"count": 10} 传递给 _get_param_value 任务
    result = await engine.run(workflow, params={"count": 10})
    
    assert result == 20

@pytest.mark.asyncio
async def test_engine_executes_env_task(monkeypatch):
    """验证 Engine 能正确执行 _get_env_var 任务。"""
    monkeypatch.setenv("TEST_VAR", "cascade_value")
    
    e = cs.Env("TEST_VAR")
    
    engine = cs.Engine()
    result = await engine.run(e)
    
    assert result == "cascade_value"