import logging
from typing import Dict

from cascade.spec.physical.nodes import Token, PhysicsFuncNode
from cascade.vm.services.contracts import DelayRequest
from cascade.reflection import PhysicalIdGenerator

logger = logging.getLogger(__name__)


def standard_sleep(
    inputs: Dict[str, Token], node: PhysicsFuncNode, resources: any
) -> Dict[str, Token]:
    try:
        chronos_queue = resources.get("system.chronos_queue")

        delay_token = inputs["delay_in"]
        data_token = inputs["data_in"]

        delay_seconds = float(delay_token.payload)

        # The logical_id is the base part of our own node ID.
        # e.g., for "task123.sleep", the logical_id is "task123"
        logical_id = node.id.rsplit(".", 1)[0]
        target_nid = PhysicalIdGenerator.wakeup_data(logical_id)

        request = DelayRequest(
            delay_seconds=delay_seconds,
            target_nid=target_nid,
            token=data_token,
        )

        chronos_queue.put_nowait(request)

    except KeyError as e:
        logger.error(f"Sleep IC failed: resource '{e}' not found.")
    except Exception:
        logger.exception(f"Error in standard_sleep for node {node.id}")

    # This function returns no tokens to the graph. The flow is paused.
    return {}
