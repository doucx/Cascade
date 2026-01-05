import asyncio
from typing import Dict, Union, Optional


class ResourceManager:
    def __init__(self, capacity: Optional[Dict[str, Union[int, float]]] = None):
        # Total capacity of the system (e.g., {"gpu": 2, "memory_gb": 16})
        # If a resource is not in capacity dict, it is assumed to be infinite.
        self._capacity: Dict[str, float] = {}
        if capacity:
            self._capacity = {k: float(v) for k, v in capacity.items()}

        # Current usage
        self._usage: Dict[str, float] = {k: 0.0 for k in self._capacity}

        # Condition variable for waiting tasks
        self._condition = asyncio.Condition()

    def set_capacity(self, capacity: Dict[str, Union[int, float]]):
        self._capacity = {k: float(v) for k, v in capacity.items()}
        # Initialize usage for new keys if needed
        for k in self._capacity:
            if k not in self._usage:
                self._usage[k] = 0.0

    def update_resource(self, name: str, capacity: float):
        self._capacity[name] = float(capacity)
        if name not in self._usage:
            self._usage[name] = 0.0
        # If we reduced capacity below current usage, that's allowed (soft limit),
        # but new acquisitions will block.

    def can_acquire(self, requirements: Dict[str, Union[int, float]]) -> bool:
        if not requirements:
            return True
        return self._can_acquire(requirements)

    async def acquire(self, requirements: Dict[str, Union[int, float]]):
        if not requirements:
            return

        async with self._condition:
            # Check if request is impossible to satisfy even when empty
            self._validate_feasibility(requirements)

            while not self._can_acquire(requirements):
                await self._condition.wait()

            # Commit acquisition
            for res, amount in requirements.items():
                if res in self._capacity:
                    self._usage[res] += float(amount)

    async def release(self, requirements: Dict[str, Union[int, float]]):
        if not requirements:
            return

        async with self._condition:
            for res, amount in requirements.items():
                if res in self._capacity:
                    self._usage[res] -= float(amount)
                    # Prevent floating point drift below zero
                    if self._usage[res] < 0:
                        self._usage[res] = 0.0

            # Notify all waiting tasks to re-check their conditions
            self._condition.notify_all()

    def _can_acquire(self, requirements: Dict[str, Union[int, float]]) -> bool:
        for res, amount in requirements.items():
            if res not in self._capacity:
                continue  # Unmanaged resources are always available

            if self._usage[res] + float(amount) > self._capacity[res]:
                return False
        return True

    def _validate_feasibility(self, requirements: Dict[str, Union[int, float]]):
        for res, amount in requirements.items():
            if res in self._capacity:
                if float(amount) > self._capacity[res]:
                    raise ValueError(
                        f"Resource requirement '{res}={amount}' exceeds total system capacity ({self._capacity[res]})."
                    )
