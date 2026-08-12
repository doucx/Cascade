from __future__ import annotations

from typing import Any


class ResourceRegistry:
    def __init__(self):
        self._resources: dict[str, Any] = {}

    def register(self, resource_id: str, resource: Any) -> None:
        if resource_id in self._resources:
            raise ValueError(f"Resource '{resource_id}' is already registered.")
        self._resources[resource_id] = resource

    def get(self, resource_id: str) -> Any:
        if resource_id not in self._resources:
            raise KeyError(f"Resource '{resource_id}' not found.")
        return self._resources[resource_id]

    def has(self, resource_id: str) -> bool:
        return resource_id in self._resources
