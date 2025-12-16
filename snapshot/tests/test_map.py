import pytest
import cascade as cs

@cs.task
def double(x: int) -> int:
    return x * 2

@cs.task
def sum_all(numbers: list[int]) -> int:
    return sum(numbers)

@pytest.mark.asyncio
async def test_map_basic():
    """Test mapping a task over a static list."""
    inputs = [1, 2, 3]
    
    # 1. Map 'double' over the inputs -> [2, 4, 6]
    mapped_results = double.map(x=inputs)
    
    # 2. Reduce the results -> 12
    total = sum_all(numbers=mapped_results)
    
    result = cs.run(total)
    assert result == 12

@pytest.mark.asyncio
async def test_map_empty():
    """Test mapping over an empty list returns an empty list."""
    inputs = []
    
    mapped_results = double.map(x=inputs)
    total = sum_all(numbers=mapped_results)
    
    result = cs.run(total)
    assert result == 0

@pytest.mark.asyncio
async def test_map_dynamic_input():
    """Test mapping over a list produced by an upstream task."""
    
    @cs.task
    def generate_numbers(n: int) -> list[int]:
        return list(range(n))

    # 1. Generate [0, 1, 2, 3] dynamically
    nums = generate_numbers(4)
    
    # 2. Map over the dynamic result -> [0, 2, 4, 6]
    doubled = double.map(x=nums)
    
    # 3. Sum -> 12
    total = sum_all(numbers=doubled)
    
    result = cs.run(total)
    assert result == 12

@pytest.mark.asyncio
async def test_map_multiple_args():
    """Test mapping with multiple iterable arguments."""
    
    @cs.task
    def add(a: int, b: int) -> int:
        return a + b
        
    list_a = [1, 2, 3]
    list_b = [10, 20, 30]
    
    # Should produce [11, 22, 33]
    mapped = add.map(a=list_a, b=list_b)
    total = sum_all(numbers=mapped)
    
    result = cs.run(total)
    assert result == 66

@pytest.mark.asyncio
async def test_map_mismatched_lengths():
    """Test that mapping with mismatched lengths raises an error."""
    
    @cs.task
    def add(a: int, b: int) -> int:
        return a + b
        
    list_a = [1, 2]
    list_b = [10, 20, 30] # Mismatched
    
    mapped = add.map(a=list_a, b=list_b)
    
    with pytest.raises(ValueError, match="mismatched lengths"):
        cs.run(mapped)