import os
import pytest
import cascade as cs
from cascade.adapters.caching import FileExistenceCache

def test_file_existence_cache_hit(tmp_path):
    """Test that a task is skipped if the target file exists."""
    target_file = tmp_path / "output.txt"
    target_file.touch()  # Create the file to simulate cache hit

    call_count = 0

    @cs.task
    def create_file(path: str):
        nonlocal call_count
        call_count += 1
        return "New Content"

    # Configure cache
    policy = FileExistenceCache(target_path=str(target_file))
    task = create_file(str(target_file)).with_cache(policy)

    result = cs.run(task)

    # Should return the path (cache value), and NOT execute the function
    assert result == str(target_file)
    assert call_count == 0

def test_file_existence_cache_miss(tmp_path):
    """Test that a task runs if the target file does not exist."""
    target_file = tmp_path / "output_miss.txt"

    call_count = 0

    @cs.task
    def create_file(path: str):
        nonlocal call_count
        call_count += 1
        # Create the file to satisfy the cache save contract
        with open(path, "w") as f:
            f.write("content")
        return "Executed"

    policy = FileExistenceCache(target_path=str(target_file))
    task = create_file(str(target_file)).with_cache(policy)

    result = cs.run(task)

    assert result == "Executed"
    assert call_count == 1
    assert target_file.exists()