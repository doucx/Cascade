import asyncio
import time
from typing import Dict, Any

import numpy as np
from cascade.connectors.local import LocalBusConnector


class ConvergenceMonitor:
    """
    Listens to firefly flashes and periodically calculates the Kuramoto order
    parameter to measure the degree of synchronization.
    """

    def __init__(self, num_agents: int, period: float, connector: LocalBusConnector):
        self.num_agents = num_agents
        self.period = period
        self.connector = connector

        # State: Store the phase reported at the last flash time for each agent
        self.phases_at_flash: Dict[int, float] = {}
        self.last_flash_time: Dict[int, float] = {}

        self._is_running = False
        self._flash_count = 0
        self.pulse_count = 0

    async def on_flash(self, topic: str, payload: Dict[str, Any]):
        """Callback to update agent state when a flash is received."""
        agent_id = payload.get("agent_id")
        if agent_id is not None:
            self._flash_count += 1
            if self._flash_count <= 5:  # Log first 5 flashes to confirm activity
                print(
                    f"\n[Monitor] Received flash from agent {agent_id} at t={time.time():.2f}"
                )

            self.phases_at_flash[agent_id] = payload.get("phase", 0.0)
            self.last_flash_time[agent_id] = time.time()

    def _calculate_order_parameter(self) -> float:
        """
        Calculates the Kuramoto order parameter, R.
        R = 0 indicates complete desynchronization.
        R = 1 indicates complete synchronization.
        """
        if not self.phases_at_flash:
            return 0.0

        now = time.time()
        current_thetas = []

        # Extrapolate the *current* phase for each agent
        for agent_id, phase_at_flash in self.phases_at_flash.items():
            time_since_flash = now - self.last_flash_time.get(agent_id, now)
            current_phase = (phase_at_flash + time_since_flash) % self.period

            # Convert phase [0, period] to angle theta [0, 2*pi]
            theta = 2 * np.pi * current_phase / self.period
            current_thetas.append(theta)

        # Calculate the order parameter R = | (1/N) * sum(e^(i * theta_j)) |
        if not current_thetas:
            return 0.0

        # We use num_agents as N for a stable denominator, even if not all have flashed yet
        z = np.sum(np.exp(1j * np.array(current_thetas))) / self.num_agents
        return np.abs(z)

    def _print_status(self, order_param: float):
        """Prints a simple text-based progress bar for synchronization."""
        self.pulse_count = self._flash_count // self.num_agents

        if self.callback:
            self.callback(order_param, self.pulse_count)
            return

        bar_length = 40
        filled_length = int(bar_length * order_param)
        bar = "█" * filled_length + "-" * (bar_length - filled_length)
        # Use carriage return to print on the same line
        # Add a check to not overwrite initial log messages
        if self._flash_count > 0:
            print(f"\r[SYNC: {bar}] {order_param:.4f}", end="", flush=True)

    async def run(self, frequency_hz: float = 2.0, callback=None):
        """
        The main loop of the monitor.

        Args:
            frequency_hz: How often to calculate R.
            callback: Optional function(float) -> None to receive the R value
                      instead of printing to stdout.
        """
        self._is_running = True
        self.callback = callback
        subscription = await self.connector.subscribe("firefly/flash", self.on_flash)

        if not self.callback:
            print("🔭 Convergence Monitor Started...")

        try:
            while self._is_running:
                # Offload heavy numpy/math calculation to thread to avoid stuttering the UI
                order_parameter = await asyncio.to_thread(self._calculate_order_parameter)
                self._print_status(order_parameter)
                await asyncio.sleep(1.0 / frequency_hz)
        finally:
            if not self.callback:
                print("\nShutting down monitor.")
            if subscription:
                await subscription.unsubscribe()

    def stop(self):
        self._is_running = False
