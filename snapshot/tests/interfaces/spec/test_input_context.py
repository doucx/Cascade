import pytest
from cascade.context import get_current_context, WorkflowContext
from cascade.spec.input import ParamSpec, EnvSpec

def test_context_isolation():
    """验证上下文是隔离的。"""
    ctx1 = WorkflowContext()
    ctx2 = WorkflowContext()
    
    spec = ParamSpec(name="p1")
    ctx1.register(spec)
    
    assert len(ctx1.get_all_specs()) == 1
    assert len(ctx2.get_all_specs()) == 0

def test_param_factory_registration():
    """验证调用 cs.Param() 会自动注册 spec 到全局上下文。"""
    import cascade as cs
    
    # 获取并清理上下文
    ctx = get_current_context()
    # 模拟清理方法，具体实现待定
    if hasattr(ctx, "input_specs"):
        ctx.input_specs.clear()
    
    # 调用工厂函数
    result = cs.Param("env", default="dev", description="Environment")
    
    # 1. 验证注册
    specs = ctx.get_all_specs()
    assert len(specs) == 1
    spec = specs[0]
    assert isinstance(spec, ParamSpec)
    assert spec.name == "env"
    assert spec.default == "dev"
    assert spec.description == "Environment"
    
    # 2. 验证返回类型 (不再是 Param 对象，而是 LazyResult)
    from cascade.spec.lazy_types import LazyResult
    assert isinstance(result, LazyResult)
    # 验证内部任务名称
    assert result.task.name == "_get_param_value"

def test_env_factory_registration():
    """验证调用 cs.Env() 的行为。"""
    import cascade as cs
    ctx = get_current_context()
    if hasattr(ctx, "input_specs"):
        ctx.input_specs.clear()
    
    result = cs.Env("API_KEY")
    
    specs = ctx.get_all_specs()
    assert len(specs) == 1
    assert isinstance(specs[0], EnvSpec)
    assert specs[0].name == "API_KEY"
    
    assert result.task.name == "_get_env_var"