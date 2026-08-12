from __future__ import annotations

from typing import MutableMapping, Protocol

from cascade.spec.physical.nodes import Token
from cascade.spec.physics import PhysicsSpec, Port, PortRole, PortType


class LauncherSpec(PhysicsSpec):
    # Inputs (Dynamic)
    # Collects all inputs not matched by other static input definitions.
    args = Port.MapInput(role=PortRole.DATA)

    # Conditional Execution
    condition = Port.Input("condition", role=PortRole.SIGNAL, type="Bool")
    # Startup Pulse
    pulse = Port.Input("__pulse__", role=PortRole.SIGNAL)

    # Outputs
    # Note: No DATA output. The Compute Request is sent via the System Bus (Tunnel).
    obs_output = Port.Output("obs_output", role=PortRole.OBSERVABILITY, type="Event")

    class IO(Protocol):
        # Inputs
        args: dict[str, Token]
        condition: Token | None
        pulse: Token | None

        # Outputs
        obs_output: Token


class LanderSpec(PhysicsSpec):
    # Inputs
    # The result arrives via this port from the D_result node.
    result_token = Port.Input("result_token", role=PortRole.DATA, type=PortType.Any)

    # Outputs
    output_default = Port.Output(
        "output_default", role=PortRole.DATA, type=PortType.Token
    )
    output_error = Port.Output("output_error", role=PortRole.DATA, type=PortType.Token)
    obs_output = Port.Output("obs_output", role=PortRole.OBSERVABILITY, type="Event")

    # Resource returns are dynamic
    resource_returns = Port.MapOutput(role=PortRole.RESOURCE, type=PortType.Token)

    class IO(Protocol):
        # Inputs
        result_token: Token | None

        # Outputs
        output_default: Token
        output_error: Token
        obs_output: Token
        resource_returns: MutableMapping[str, Token]
