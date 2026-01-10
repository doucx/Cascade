import pytest
from unittest.mock import MagicMock

from cascade.runtime.host.instance import Engine
from cascade.runtime.strategies.vm import VMExecutionStrategy
from cascade.execution.graph.strategy import GraphExecutionStrategy


# Fixtures for Engine dependencies
@pytest.fixture
def mock_solver():
    return MagicMock()


@pytest.fixture
def mock_executor():
    return MagicMock()


@pytest.fixture
def mock_bus():
    return MagicMock()


@pytest.mark.parametrize(
    "backend_env, expected_strategy_type",
    [
        ("vm", VMExecutionStrategy),
        ("VM", VMExecutionStrategy),  # Test case-insensitivity
        ("graph", GraphExecutionStrategy),
        ("GRAPH", GraphExecutionStrategy),
        ("other", GraphExecutionStrategy),  # Test fallback for unknown values
        (None, GraphExecutionStrategy),  # Test unset env var defaults to graph
    ],
)
def test_engine_selects_strategy_from_env(
    monkeypatch,
    mock_solver,
    mock_executor,
    mock_bus,
    backend_env,
    expected_strategy_type,
):
    if backend_env is None:
        monkeypatch.delenv("CASCADE_BACKEND", raising=False)
    else:
        monkeypatch.setenv("CASCADE_BACKEND", backend_env)

    # We pass strategy=None to trigger the default selection logic
    engine = Engine(
        solver=mock_solver,
        executor=mock_executor,
        bus=mock_bus,
        strategy=None,
    )

    assert isinstance(engine.strategy, expected_strategy_type)


def test_engine_uses_explicit_strategy_over_env(
    monkeypatch, mock_solver, mock_executor, mock_bus
):
    # Set env to a value that would normally select GraphExecutionStrategy
    monkeypatch.setenv("CASCADE_BACKEND", "graph")

    # But explicitly provide the VM strategy
    explicit_strategy = VMExecutionStrategy(executor=mock_executor, bus=mock_bus)

    engine = Engine(
        solver=mock_solver,
        executor=mock_executor,
        bus=mock_bus,
        strategy=explicit_strategy,
    )

    assert engine.strategy is explicit_strategy
    assert isinstance(engine.strategy, VMExecutionStrategy)
