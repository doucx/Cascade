import pytest
from cascade.spec.task import task
from cascade.runtime.graph.hashing import compute_topology_hash

@task
def add(a, b):
    return a + b

@task
def sub(a, b):
    return a - b

def test_topology_hash_ignores_literal_values():
    """
    Verify that task(1, 2) and task(3, 4) have the SAME topology hash.
    This is the key requirement for TCO graph reuse.
    """
    workflow_a = add(1, 2)
    workflow_b = add(3, 4)
    
    hash_a = compute_topology_hash(workflow_a)
    hash_b = compute_topology_hash(workflow_b)
    
    assert hash_a == hash_b, "Topology hash should be invariant to literal values"

def test_topology_hash_respects_structure():
    """
    Verify that changing the task or nesting structure changes the hash.
    """
    # Same args, different task
    hash_add = compute_topology_hash(add(1, 2))
    hash_sub = compute_topology_hash(sub(1, 2))
    assert hash_add != hash_sub
    
    # Same task, different dependency structure
    # Case 1: Flat
    flat = add(1, 2)
    # Case 2: Nested
    nested = add(add(1, 2), 3)
    
    assert compute_topology_hash(flat) != compute_topology_hash(nested)

def test_topology_hash_respects_kwargs_structure():
    """
    Verify that changing keys in kwargs changes the hash.
    """
    t1 = add(a=1, b=2)
    t2 = add(a=1, c=2) # Different arg name
    
    assert compute_topology_hash(t1) != compute_topology_hash(t2)

def test_topology_hash_literal_types_matter():
    """
    Verify that changing the TYPE of a literal changes the hash.
    Graph inputs are often typed, so int vs string might imply different validation logic.
    """
    t_int = add(1, 2)
    t_str = add("1", "2")
    
    assert compute_topology_hash(t_int) != compute_topology_hash(t_str)