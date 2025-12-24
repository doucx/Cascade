from cascade.spec.task import task
from cascade.graph.ast_analyzer import analyze_task_source

# --- Setup Dummy Tasks ---


@task
def downstream_a(x):
    return x


@task
def downstream_b(x):
    return x * 2


# --- Scenarios ---


def test_analyze_direct_return():
    """Test standard 'return task(...)' pattern with branching."""

    @task
    def orchestrator(x):
        if x > 5:
            return downstream_a(x)
        else:
            return downstream_b(x)

    analysis_result = analyze_task_source(orchestrator)
    targets = analysis_result.targets

    target_names = {t.name for t in targets}
    assert "downstream_a" in target_names
    assert "downstream_b" in target_names
    assert len(targets) == 2


def test_analyze_map_return():
    """Test 'return task.map(...)' pattern."""

    @task
    def mapper_orchestrator(items):
        return downstream_a.map(x=items)

    analysis_result = analyze_task_source(mapper_orchestrator)
    targets = analysis_result.targets
    target_names = {t.name for t in targets}
    assert "downstream_a" in target_names


def test_analyze_with_alias_in_globals():
    """Test when tasks are aliased in global scope."""
    alias_task = downstream_a

    @task
    def alias_user():
        return alias_task(1)

    analysis_result = analyze_task_source(alias_user)
    targets = analysis_result.targets
    target_names = {t.name for t in targets}
    assert "downstream_a" in target_names


def test_analyze_no_tco():
    """Test that regular returns are ignored."""

    @task
    def simple_calc():
        return 42

    analysis_result = analyze_task_source(simple_calc)
    targets = analysis_result.targets
    assert len(targets) == 0


def test_analyze_complex_attribute_access():
    """Test resolving tasks within namespaces."""

    class Actions:
        op = downstream_b

    actions = Actions()

    @task
    def namespace_user():
        return actions.op(10)

    analysis_result = analyze_task_source(namespace_user)
    targets = analysis_result.targets
    target_names = {t.name for t in targets}
    assert "downstream_b" in target_names