"""Shared ownership behavior for SmartCoop components."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .smart_coop import SmartCoop


class SmartCoopComponentMixin:
    """Provide attachment to and access to an owning SmartCoop."""

    __slots__ = ("_smart_coop",)
    _component_name = "Component"

    def attach(self, smart_coop: SmartCoop) -> None:
        """Attach this component to its owning SmartCoop."""
        self._smart_coop = smart_coop

    def _require_smart_coop(self) -> SmartCoop:
        smart_coop = getattr(self, "_smart_coop", None)
        if smart_coop is None:
            raise RuntimeError(f"{self._component_name} is not attached to a SmartCoop.")
        return smart_coop
