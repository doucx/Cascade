from typing import Any

from cascade.spec import RetryNode
from cascade.std.specs import RetrySpec
from cascade.spec.physics.binding import implements


@implements(RetrySpec)
def standard_retry_logic(io: RetrySpec.IO, node: RetryNode, resources: Any) -> None:
    error_token = io.error_in
    context_token = io.context_in

    assert context_token is not None, "Context token for retry is missing"
    assert error_token is not None, "Error token for retry is missing"

    # State is in the token trace
    trace = context_token.trace
    retry_count = trace.get("retry_count", 0)
    retry_count += 1

    # Policy is in the node definition
    max_attempts = node.max_attempts

    if retry_count < max_attempts:
        # Retry: update state and route context token back
        trace["retry_count"] = retry_count
        io.retry_out = context_token
    else:
        # Fail permanently: route error token to the failure output port
        io.fail_out = error_token
