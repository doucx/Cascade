import cascade.sdk as cs
import pytest
from cascade.tools.lisp import to_lisp

# Skip if typer is not installed (dependency of cs.create_cli, often in same env)
pytest.importorskip("typer")


# --- Test Cases ---


def test_lisp_transpile_simple_param():
    target = cs.Param("my_param", description="A test parameter")
    lisp_code = to_lisp(target)
    assert lisp_code == '(param "my_param")'


def test_lisp_transpile_param_as_dependency():
    @cs.task
    def process_data(data, scale: int = 1):
        pass

    target = process_data(cs.Param("user_input"), scale=10)
    lisp_code = to_lisp(target)

    # Note: Param is not shared, so it's inlined.
    expected = '(process-data (param "user_input") :scale 10)'
    assert lisp_code == expected


def test_lisp_transpile_shared_param_in_let():
    @cs.task
    def task_a(dep):
        pass

    @cs.task
    def task_b(dep):
        pass

    @cs.task
    def gather(a, b):
        pass

    # 'user_input' is shared between task_a and task_b
    param = cs.Param("user_input")
    target = gather(task_a(param), task_b(param))

    lisp_code = to_lisp(target)
    print(lisp_code)

    # We expect 'user-input' to be defined in let* and referenced by name.
    # The name is sanitized from the node name (_get_param_value)
    expected_lines = [
        "(let* (",
        '  (-get-param-value (param "user_input"))',
        ")",
        "  (gather (task-a -get-param-value) (task-b -get-param-value)))",
    ]
    assert lisp_code == "\n".join(expected_lines)


def test_lisp_transpile_router_with_param_selector():
    @cs.task
    def branch_a():
        pass

    @cs.task
    def branch_b():
        pass

    router = cs.Router(
        selector=cs.Param("mode"), routes={"a": branch_a(), "b": branch_b()}
    )

    @cs.task
    def consumer(val):
        pass

    target = consumer(router)
    lisp_code = to_lisp(target)
    print(lisp_code)

    # The param is shared (as a selector), so it's hoisted.
    expected_lines = [
        "(let* (",
        '  (-get-param-value (param "mode"))',
        ")",
        '  (consumer (case -get-param-value (("a") (branch-a)) (("b") (branch-b)))))',
    ]

    assert lisp_code == "\n".join(expected_lines)
