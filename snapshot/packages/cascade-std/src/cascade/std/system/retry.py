from typing import Dict, Any

from cascade.spec import RetryNode
from cascade.spec.physical.nodes import Token


def standard_retry_logic(
    inputs: Dict[str, Token], node: RetryNode, resources: Any
) -> Dict[str, Token]:
    """
    Implements topological retry logic.

    Inputs:
        - error_in: The error token from the failed task.
        - context_in: The original input context token.

    Outputs:
        - retry_out: The context token, to be routed back for retry.
        - fail_out: The error token, if retries are exhausted.
    """
    error_token = inputs["error_in"]
    context_token = inputs["context_in"]

    # State is in the token trace
    trace = context_token.trace
    retry_count = trace.get("retry_count", 0)
    retry_count += 1

    # Policy is in the node definition
    max_attempts = node.max_attempts

    if retry_count < max_attempts:
        # Retry: update state and route context token back
        trace["retry_count"] = retry_count
        return {"retry_out": context_token}
    else:
        # Fail permanently: route error token to failure sink
        return {"fail_out": error_token}