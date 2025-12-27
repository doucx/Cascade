import pytest
import cascade as cs
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver


@pytest.fixture
def subflow_file(tmp_path):
    p = tmp_path / "my_flow.py"
    content = """
import cascade as cs

# Define a parameter
multiplier = cs.Param("multiplier", default=1)

@cs.task
def process(val, m):
    return val * m

# Define the workflow
result_node = process(10, multiplier)
"""
    p.write_text(content)
    return str(p)


@pytest.mark.asyncio
async def test_subflow_execution(subflow_file):
    # Define a parent workflow that calls the subflow
    # subflow is loaded via provider registry
    sub_result = cs.subflow(
        path=subflow_file, target="result_node", params={"multiplier": 5}
    )

    @cs.task
    def finalize(val):
        return f"Final: {val}"

    workflow = finalize(sub_result)

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )

    # 10 * 5 = 50 -> "Final: 50"
    result = await engine.run(workflow)

    assert result == "Final: 50"


@pytest.mark.asyncio
async def test_subflow_file_not_found():
    workflow = cs.subflow(path="non_existent.py", target="foo")

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )

    with pytest.raises(FileNotFoundError):
        await engine.run(workflow)


@pytest.mark.asyncio
async def test_subflow_target_not_found(subflow_file):
    workflow = cs.subflow(path=subflow_file, target="missing_var")

    engine = cs.Engine(
        solver=NativeSolver(), executor=LocalExecutor(), bus=cs.MessageBus()
    )

    with pytest.raises(ValueError, match="Target 'missing_var' not found"):
        await engine.run(workflow)
