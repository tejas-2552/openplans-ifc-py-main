"""Window element placeholder plugin.

Registered as ``WINDOW`` so the discriminated union validates payloads
of that type, but the geometry builder is not yet implemented.
"""

from __future__ import annotations

from typing import Any

import ifcopenshell

from app.models.base import WindowPayload
from app.plugins.registry import ElementBuilder, plugin_registry


@plugin_registry.register("WINDOW")
class WindowBuilder(ElementBuilder):
    """Placeholder — raises ``NotImplementedError`` with guidance."""

    def build(
        self,
        model: ifcopenshell.file,
        body_context: Any,
        storey: Any,
        payload: WindowPayload,
    ) -> Any:
        raise NotImplementedError(
            "WindowBuilder is not yet implemented. "
            "To add support, create the geometry logic in this file "
            "following the same pattern as Wall3DBuilder."
        )
