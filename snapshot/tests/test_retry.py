import pytest
import cascade as cs


def test_retry_success_after_failure():
    """Test that a task retries and eventually succeeds."""

    call_count = 0

    @cs.task
    def flaky_task():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Fail!")
        return "Success"

    # Retry 3 times (total 4 attempts allowed)
    task_with_retry = flaky_task().with_retry(max_attempts=3, delay=0.01)

    result = cs.run(task_with_retry)

    assert result == "Success"
    assert call_count == 3  # Failed twice, succeeded on 3rd


def test_retry_exhausted_failure():
    """Test that a task fails after exhausting all retries."""

    call_count = 0

    @cs.task
    def always_fail():
        nonlocal call_count
        call_count += 1
        raise ValueError("Always fail")

    task_with_retry = always_fail().with_retry(max_attempts=2, delay=0.01)

    with pytest.raises(ValueError, match="Always fail"):
        cs.run(task_with_retry)

    assert call_count == 3  # Initial + 2 retries
