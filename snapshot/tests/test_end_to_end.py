import pytest
import cascade as cs
import io
import sys
from contextlib import redirect_stdout

def test_e2e_linear_workflow():
    @cs.task
    def get_name():
        return "Cascade"

    @cs.task
    def greet(name: str):
        return f"Hello, {name}!"

    final_greeting = greet(get_name())
    
    output = io.StringIO()
    with redirect_stdout(output):
        result = cs.run(final_greeting)

    assert result == "Hello, Cascade!"
    
    logs = output.getvalue()
    assert "▶️  Starting Run" in logs
    assert "⏳ Running task `get_name`" in logs
    assert "✅ Finished task `get_name`" in logs
    assert "⏳ Running task `greet`" in logs
    assert "✅ Finished task `greet`" in logs
    assert "🏁 Run finished successfully" in logs

def test_e2e_diamond_workflow_and_result():
    @cs.task
    def t_a(): return 5
    @cs.task
    def t_b(x): return x * 2  # 10
    @cs.task
    def t_c(x): return x + 3  # 8
    @cs.task
    def t_d(y, z): return y + z # 18

    r_a = t_a()
    r_b = t_b(r_a)
    r_c = t_c(r_a)
    r_d = t_d(r_b, z=r_c)

    result = cs.run(r_d)
    assert result == 18

def test_e2e_failure_propagation():
    @cs.task
    def ok_task():
        return True

    @cs.task
    def failing_task(x):
        raise ValueError("Something went wrong")

    @cs.task
    def unreachable_task(y):
        return False
    
    r1 = ok_task()
    r2 = failing_task(r1)
    r3 = unreachable_task(r2)

    output = io.StringIO()
    with redirect_stdout(output):
        with pytest.raises(ValueError, match="Something went wrong"):
            cs.run(r3)

    logs = output.getvalue()
    assert "✅ Finished task `ok_task`" in logs
    assert "❌ Failed task `failing_task`" in logs
    assert "💥 Run failed" in logs
    assert "unreachable_task" not in logs