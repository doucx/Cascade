import pytest
import cascade as cs

def test_router_selects_correct_path():
    @cs.task
    def get_source():
        return "a"

    @cs.task
    def task_a():
        return "Result A"

    @cs.task
    def task_b():
        return "Result B"

    @cs.task
    def process(data):
        return f"Processed: {data}"

    # Router depends on get_source
    router = cs.Router(
        selector=get_source(),
        routes={
            "a": task_a(),
            "b": task_b()
        }
    )

    final = process(data=router)

    result = cs.run(final)
    assert result == "Processed: Result A"

def test_router_with_params():
    # Use Param as selector
    mode = cs.Param("mode")
    
    @cs.task
    def prod_task(): return "PROD"
    
    @cs.task
    def dev_task(): return "DEV"
    
    @cs.task
    def deploy(env_name):
        return f"Deploying to {env_name}"
        
    router = cs.Router(
        selector=mode,
        routes={
            "production": prod_task(),
            "development": dev_task()
        }
    )
    
    flow = deploy(env_name=router)
    
    # Test case 1: Development
    res_dev = cs.run(flow, params={"mode": "development"})
    assert res_dev == "Deploying to DEV"
    
    # Test case 2: Production
    res_prod = cs.run(flow, params={"mode": "production"})
    assert res_prod == "Deploying to PROD"

def test_router_invalid_selection():
    selector = cs.Param("sel")
    
    @cs.task
    def t1(): return 1
    
    router = cs.Router(selector=selector, routes={"a": t1()})
    
    @cs.task
    def consumer(x): return x
    
    with pytest.raises(ValueError, match="no matching route found"):
        cs.run(consumer(router), params={"sel": "invalid_key"})