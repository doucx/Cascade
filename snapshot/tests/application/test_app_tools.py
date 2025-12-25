import cascade as cs
from cascade.app import CascadeApp


def test_app_dry_run_linear_workflow(capsys):
    """
    Tests that CascadeApp.dry_run() prints the correct plan for a simple
    linear workflow.
    """
    @cs.task
    def step_a():
        return 1

    @cs.task
    def step_b(x, y=10):
        return x + y

    target = step_b(step_a(), y=10)
    app = CascadeApp(target)

    app.dry_run()

    captured = capsys.readouterr().out
    assert "--- Cascade Execution Plan (Dry Run) ---" in captured
    assert "[1/2] step_a" in captured
    assert "[2/2] step_b" in captured
    assert "Bindings: {'y': 10}" in captured


def test_app_dry_run_diamond_workflow(capsys):
    """
    Tests that CascadeApp.dry_run() correctly orders a diamond-shaped graph.
    """
    @cs.task
    def t_a(): return 1
    @cs.task
    def t_b(x): return x + 1
    @cs.task
    def t_c(x): return x * 2
    @cs.task
    def t_d(y, z): return y + z

    r_a = t_a()
    r_d = t_d(t_b(r_a), z=t_c(r_a))

    app = CascadeApp(r_d)
    app.dry_run()

    captured = capsys.readouterr().out
    lines = [line.strip() for line in captured.strip().split('\n')]
    
    assert "t_a" in lines[1] # A is first
    assert "t_d" in lines[-2] # D is last
    
    # B and C should be in the middle
    middle_nodes = {lines[2].split(' ')[1], lines[3].split(' ')[1]}
    assert middle_nodes == {"t_b", "t_c"}


def test_app_dry_run_with_list_input(capsys):
    """
    Verifies that dry_run handles a list of LazyResults and includes the
    implicit gather node in its plan.
    """
    @cs.task(pure=True)
    def t_a(): return "a"
    @cs.task(pure=True)
    def t_b(): return "b"

    lr_a = t_a()
    lr_b = t_b()

    app = CascadeApp([lr_a, lr_b])
    app.dry_run()

    captured = capsys.readouterr().out
    lines = [line.strip() for line in captured.strip().split('\n')]

    # .strip() removes the final newline, so we expect 5 lines:
    # Header, t_a, t_b, _internal_gather, Footer
    assert len(lines) == 5
    assert "_internal_gather" in lines[-2]
    node_names = {l.split(' ')[1] for l in lines[1:-2]}
    assert node_names == {"t_a", "t_b", "_internal_gather"}
