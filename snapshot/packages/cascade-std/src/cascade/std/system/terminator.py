from typing import Any
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.std.specs import TerminatorSpec
from cascade.std.kernel_tools import implements


@implements(TerminatorSpec)
def halt_signal(io: TerminatorSpec.IO, node: PhysicsNode, resources: Any) -> None:
    # The output token is a special system type, not a standard data Token.
    # The VM will need to have a special port/handler for these.
    # We wrap it in a standard token for transport through a standard channel.
    control_token = SystemControlToken(command=ControlCommand.HALT)
    io.out = Token(payload=control_token)
