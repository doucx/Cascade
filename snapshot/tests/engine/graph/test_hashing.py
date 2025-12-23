from cascade import task
from cascade.graph.hashing import StructuralHasher, ShallowHasher


@task
def add(a, b):
    return a + b


@task
def sub(a, b):
    return a - b


def test_hashing_simple_structure():
    # Case 1: Same structure, different values
    t1 = add(1, 2)
    t2 = add(3, 4)

    h1, l1 = StructuralHasher().hash(t1)
    h2, l2 = StructuralHasher().hash(t2)

    assert h1 == h2, "Same task structure should have same hash"
    assert l1 != l2
    assert l1["root.args.0"] == 1
    assert l2["root.args.0"] == 3

    # Case 2: Different structure (different task)
    t3 = sub(1, 2)
    h3, _ = StructuralHasher().hash(t3)
    assert h1 != h3


def test_hashing_nested_structure():
    # Structure: add(1, sub(2, 3))
    t1 = add(1, sub(2, 3))
    t2 = add(10, sub(20, 30))

    h1, l1 = StructuralHasher().hash(t1)
    h2, l2 = StructuralHasher().hash(t2)

    assert h1 == h2
    assert l1["root.args.1.args.0"] == 2
    assert l2["root.args.1.args.0"] == 20


def test_hashing_list_structure():
    # Structure: add([1, 2], 3)
    t1 = add([1, 2], 3)
    t2 = add([10, 20], 30)
    t3 = add([1, 2, 3], 4)  # Different list length -> Different structure

    h1, _ = StructuralHasher().hash(t1)
    h2, _ = StructuralHasher().hash(t2)
    h3, _ = StructuralHasher().hash(t3)

    assert h1 == h2
    assert h1 != h3


def test_hashing_kwargs():
    t1 = add(a=1, b=2)
    t2 = add(a=3, b=4)
    t3 = add(b=2, a=1)  # Order shouldn't matter for structure

    h1, _ = StructuralHasher().hash(t1)
    h2, _ = StructuralHasher().hash(t2)
    h3, _ = StructuralHasher().hash(t3)

    assert h1 == h2
    assert h1 == h3


def test_hashing_distinguishes_nested_lazy_results():
    """
    This is the critical test to expose the bug.
    The structure of task_a(task_b()) and task_a(task_c()) should be different.
    The current hasher will fail this test because it replaces both task_b()
    and task_c() with a generic "LAZY" placeholder.
    """

    @task
    def task_a(dep):
        return dep

    @task
    def task_b():
        return "b"

    @task
    def task_c():
        return "c"

    # These two targets have different dependency structures
    target1 = task_a(task_b())
    target2 = task_a(task_c())

    # But the current ShallowHasher will produce the same hash for both
    hasher = ShallowHasher()
    hash1 = hasher.hash(target1)
    hash2 = hasher.hash(target2)

    assert hash1 != hash2, "Hasher must distinguish between different nested LazyResult dependencies"
