import cascade as cs


def test_dry_run_linear_graph(capsys):
    @cs.task
    def step_a():
        return 1

    @cs.task
    def step_b(x, y=10):
        return x + y

    result = step_b(step_a())
    cs.dry_run(result)

    captured = capsys.readouterr()
    output = captured.out

    assert "--- Cascade Execution Plan (Dry Run) ---" in output
    assert "[1/2] step_a (Literals: {})" in output
    assert "[2/2] step_b (Literals: {'y': 10})" in output
    assert "----------------------------------------" in output
    # Check order
    assert output.find("step_a") < output.find("step_b")


def test_dry_run_diamond_graph(capsys):
    @cs.task
    def t_a():
        return 1

    @cs.task
    def t_b(x):
        return x + 1

    @cs.task
    def t_c(x):
        return x * 2

    @cs.task
    def t_d(y, z):
        return y + z

    r_a = t_a()
    r_b = t_b(r_a)
    r_c = t_c(r_a)
    r_d = t_d(r_b, z=r_c)

    cs.dry_run(r_d)

    captured = capsys.readouterr()
    output = captured.out

    assert "[1/4] t_a" in output
    assert "[4/4] t_d" in output
    # Check that both B and C are present
    assert "t_b (Literals: {})" in output
    assert "t_c (Literals: {})" in output
    # Check order: A must be before B and C, B and C before D
    assert output.find("t_a") < output.find("t_b")
    assert output.find("t_a") < output.find("t_c")
    assert output.find("t_b") < output.find("t_d")
    assert output.find("t_c") < output.find("t_d")