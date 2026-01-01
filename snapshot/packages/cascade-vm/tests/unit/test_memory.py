import pytest
from cascade.spec.physics import Token, PhysicsDataNode
from cascade.vm.memory import VolatileMemory, MemoryFullError, MemoryEmptyError

def test_basic_put_and_take():
    """Test standard token storage and retrieval."""
    mem = VolatileMemory()
    node = PhysicsDataNode(id="D1", name="InputSlot", capacity=1)
    token = Token(payload="hello")
    
    mem.put(node, token)
    assert mem.get_count(node.id) == 1
    
    retrieved = mem.take(node.id)
    assert retrieved.payload == "hello"
    assert mem.get_count(node.id) == 0

def test_fifo_behavior():
    """Tokens must be retrieved in the order they were put (FIFO)."""
    mem = VolatileMemory()
    node = PhysicsDataNode(id="D1", name="Buffer", capacity=10)
    
    mem.put(node, Token(payload="first"))
    mem.put(node, Token(payload="second"))
    
    assert mem.take(node.id).payload == "first"
    assert mem.take(node.id).payload == "second"

def test_capacity_overflow():
    """Putting more tokens than capacity must raise MemoryFullError."""
    mem = VolatileMemory()
    node = PhysicsDataNode(id="D1", name="SmallSlot", capacity=1)
    
    mem.put(node, Token(payload="one"))
    with pytest.raises(MemoryFullError):
        mem.put(node, Token(payload="two"))

def test_empty_take():
    """Taking from an empty node must raise MemoryEmptyError."""
    mem = VolatileMemory()
    with pytest.raises(MemoryEmptyError):
        mem.take("non-existent")

def test_excitement_check():
    """
    A node is 'excited' if it has at least one token (or a specific threshold).
    This is the core signal for the Reactor.
    """
    mem = VolatileMemory()
    node = PhysicsDataNode(id="D1", name="Trigger", capacity=5)
    
    assert not mem.is_excited(node.id)
    
    mem.put(node, Token(payload="pulse"))
    assert mem.is_excited(node.id)
    assert mem.is_excited(node.id, threshold=1)
    assert not mem.is_excited(node.id, threshold=2)