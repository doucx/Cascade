import pytest
from cascade.adapters.solvers.csp import CSPSolver

# Skip tests if python-constraint is not installed
pytest.importorskip("constraint")


def test_csp_solver_init():
    """Test that CSPSolver can be initialized with resources."""
    solver = CSPSolver(system_resources={"cpu": 4, "ram": 16})
    assert solver.system_resources == {"cpu": 4, "ram": 16}


def test_csp_solver_missing_dependency(monkeypatch):
    """Test that meaningful error is raised if dependency is missing."""
    import cascade.adapters.solvers.csp as csp_module
    
    # Simulate missing dependency by setting constraint to None
    monkeypatch.setattr(csp_module, "constraint", None)
    
    with pytest.raises(ImportError, match="python-constraint"):
        CSPSolver(system_resources={})