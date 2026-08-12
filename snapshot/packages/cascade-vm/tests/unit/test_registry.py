import logging

import pytest
from cascade.vm.registry import CodeRegistry


def sample_task_one():
    return "one"


def sample_task_two():
    return "two"


class TestCodeRegistry:
    def test_register_and_get(self):
        registry = CodeRegistry()
        sample_hash = "hash_one"

        assert not registry.has(sample_hash)
        registry.register(sample_hash, sample_task_one)

        assert registry.has(sample_hash)
        retrieved_func = registry.get(sample_hash)
        assert retrieved_func is sample_task_one
        assert retrieved_func() == "one"

    def test_get_missing_raises_key_error(self):
        registry = CodeRegistry()
        with pytest.raises(KeyError, match="not found in registry"):
            registry.get("non_existent_hash")

    def test_reregister_idempotent(self, caplog):
        registry = CodeRegistry()
        sample_hash = "hash_one"

        registry.register(sample_hash, sample_task_one)

        with caplog.at_level(logging.WARNING):
            registry.register(sample_hash, sample_task_one)

        # No warning should be logged for idempotent re-registration
        assert "Hash collision detected" not in caplog.text

        # Ensure the registration is still valid
        assert registry.get(sample_hash) is sample_task_one

    def test_reregister_collision_warns(self, caplog):
        registry = CodeRegistry()
        sample_hash = "hash_collision"

        # Initial registration
        registry.register(sample_hash, sample_task_one)

        # Re-register with a different function
        with caplog.at_level(logging.WARNING):
            registry.register(sample_hash, sample_task_two)

        # A warning should be logged
        assert "Hash collision detected" in caplog.text
        assert (
            f"Overwriting registration for '{sample_task_one.__name__}'" in caplog.text
        )
        assert f"with new function '{sample_task_two.__name__}'" in caplog.text

        # Ensure the registry now holds the new function
        retrieved_func = registry.get(sample_hash)
        assert retrieved_func is sample_task_two
        assert retrieved_func() == "two"
