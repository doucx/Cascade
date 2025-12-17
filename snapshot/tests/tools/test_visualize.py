import pytest
import cascade as cs

@cs.task
def source():
    return True

@cs.task
def data_consumer(val):
    return val

@cs.task
def condition_consumer():
    return "conditioned"

@cs.task
def constraint_consumer():
    return "constrained"

@cs.task
def gather(a, b, c):
    return True

def test_visualize_differentiates_edge_types():
    """
    Tests that visualize() produces a DOT string that visually distinguishes
    between data, condition, and constraint edges.
    """
    src = source()
    
    # 1. Standard Data Edge
    data_edge_target = data_consumer(src)
    
    # 2. Condition Edge
    condition_edge_target = condition_consumer().run_if(src)
    
    # 3. Constraint Edge
    constraint_edge_target = constraint_consumer().with_constraints(cpu=src)
    
    # Use a gather task to create a single target for the graph
    final_target = gather(data_edge_target, condition_edge_target, constraint_edge_target)
    
    dot_string = cs.visualize(final_target)
    
    # --- Assertions ---
    
    # Find node UUIDs
    src_id = src._uuid
    data_id = data_edge_target.task._uuid
    cond_id = condition_edge_target._uuid
    cons_id = constraint_edge_target._uuid
    
    # Assert Data Edge (default style, just a label)
    assert f'"{src_id}" -> "{data_id}" [label="0"];' in dot_string
    
    # Assert Condition Edge (dashed, gray)
    assert f'"{src_id}" -> "{cond_id}"' in dot_string
    assert 'style=dashed, color=gray, label="run_if"' in dot_string
    
    # Assert Constraint Edge (dotted, purple)
    assert f'"{src_id}" -> "{cons_id}"' in dot_string
    assert 'style=dotted, color=purple, label="constraint: cpu"' in dot_string