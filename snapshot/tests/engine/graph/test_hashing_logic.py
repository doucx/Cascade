import pytest
import cascade as cs
from cascade.graph.hashing import ShallowHasher


@cs.task
def simple_task(a, b=None):
    pass


def test_shallow_hasher_ignores_literals():
    """
    Verifies that the ShallowHasher produces the same hash for tasks
    that differ only in their literal (non-LazyResult) arguments.
    This is critical for structural caching of recursive tasks.
    """
    hasher = ShallowHasher()

    # Create two instances with different literal arguments
    lr1 = simple_task(1, b="hello")
    lr2 = simple_task(2, b="world")

    # Their structural hashes MUST be identical
    hash1 = hasher.hash(lr1)
    hash2 = hasher.hash(lr2)

    assert hash1 == hash2, "ShallowHasher should ignore literal argument values."


def test_shallow_hasher_differentiates_structure():
    """
    Verifies that the hasher correctly identifies changes in graph structure,
    such as adding a dependency.
    """
    hasher = ShallowHasher()

    @cs.task
    def upstream():
        pass

    lr_simple = simple_task(1)
    lr_complex = simple_task(upstream())

    hash_simple = hasher.hash(lr_simple)
    hash_complex = hasher.hash(lr_complex)

    assert hash_simple != hash_complex, "ShallowHasher should differentiate based on dependencies."