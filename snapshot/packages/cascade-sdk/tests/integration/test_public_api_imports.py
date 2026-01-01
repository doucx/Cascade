import pytest


def test_core_components_are_accessible_from_top_level():
    try:
        from cascade import (
            Engine,
            MessageBus,
            NativeSolver,
            LocalExecutor,
            DependencyMissingError,
        )
    except ImportError as e:
        pytest.fail(f"Failed to import core components from top-level 'cascade': {e}")

    # Dummy assertion to ensure the test runs if imports succeed
    assert Engine is not None
    assert MessageBus is not None
    assert NativeSolver is not None
    assert LocalExecutor is not None
    assert DependencyMissingError is not None


def test_accessing_non_existent_attribute_raises_attribute_error():
    import cascade as cs

    with pytest.raises(
        AttributeError,
        match="module 'cascade' has no attribute 'ThisClassShouldNotExist'",
    ):
        _ = cs.ThisClassShouldNotExist
