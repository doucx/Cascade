import cascade as cs
from cascade.graph.build import build_graph
from cascade.spec.constraint import ResourceConstraint


def test_resource_constraint_definition():
    """Test the basic definition of ResourceConstraint."""
    constraints = cs.with_constraints(gpu_count=1, memory_gb=8)
    
    assert isinstance(constraints, ResourceConstraint)
    assert constraints.requirements["gpu_count"] == 1
    assert not constraints.is_empty()
    assert bool(constraints) is True


def test_lazy_result_constraint_chaining():
    """Test that .with_constraints is chainable and attaches metadata."""
    @cs.task
    def heavy_task():
        pass
    
    lazy_result = heavy_task().with_constraints(cpu_cores=4)
    
    assert lazy_result._constraints is not None
    assert lazy_result._constraints.requirements["cpu_cores"] == 4


def test_constraint_propagation_to_node():
    """Test that the constraint metadata is correctly stored on the graph node."""
    @cs.task
    def heavy_task():
        pass
    
    target = heavy_task().with_constraints(io_bandwidth="high")
    graph = build_graph(target)
    
    node = next(n for n in graph.nodes if n.name == "heavy_task")
    
    assert node.constraints is not None
    assert isinstance(node.constraints, ResourceConstraint)
    assert node.constraints.requirements["io_bandwidth"] == "high"