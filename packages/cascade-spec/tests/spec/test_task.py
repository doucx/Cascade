from cascade.spec.task import task, LazyResult


def test_task_decorator_and_lazy_result():
    @task
    def add(a, b):
        return a + b

    result = add(1, 2)
    assert isinstance(result, LazyResult)
    assert result.task.name == "add"
    assert result.args == (1, 2)
    assert result.kwargs == {}
