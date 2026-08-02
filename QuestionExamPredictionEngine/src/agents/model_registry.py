from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel

from src.agents.contracts import AgentWarning


class ModelUnavailableError(RuntimeError):
    pass


class ModelCapabilityStatus(BaseModel):
    name: str
    version: str
    optional: bool
    loaded: bool
    error: str | None = None


@dataclass(frozen=True)
class _Registration:
    version: str
    loader: Callable[[], Any]
    optional: bool


class ModelRegistry:
    def __init__(self):
        self._registrations: dict[str, _Registration] = {}
        self._instances: dict[str, Any] = {}
        self._errors: dict[str, str] = {}

    def register(
        self,
        name: str,
        version: str,
        loader: Callable[[], Any],
        optional: bool = True,
    ) -> None:
        if name in self._registrations:
            raise ValueError(f"Model capability already registered: {name}")
        self._registrations[name] = _Registration(version, loader, optional)

    def get(self, name: str) -> Any:
        if name not in self._registrations:
            raise KeyError(name)
        if name in self._instances:
            return self._instances[name]

        registration = self._registrations[name]
        try:
            instance = registration.loader()
        except Exception as exc:
            self._errors[name] = str(exc)
            raise ModelUnavailableError(f"{name}: {exc}") from exc

        self._instances[name] = instance
        return instance

    def try_get(self, name: str) -> tuple[Any | None, AgentWarning | None]:
        try:
            return self.get(name), None
        except ModelUnavailableError as exc:
            registration = self._registrations[name]
            if not registration.optional:
                raise
            return None, AgentWarning(
                code="model_unavailable",
                message=str(exc),
                capability=name,
            )

    def versions(self) -> dict[str, str]:
        return {
            name: registration.version
            for name, registration in self._registrations.items()
        }

    def statuses(self) -> list[ModelCapabilityStatus]:
        return [
            ModelCapabilityStatus(
                name=name,
                version=registration.version,
                optional=registration.optional,
                loaded=name in self._instances,
                error=self._errors.get(name),
            )
            for name, registration in self._registrations.items()
        ]
