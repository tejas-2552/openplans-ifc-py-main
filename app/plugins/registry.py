"""Dynamic plugin registry for BIM element builders.

Usage
-----
1. Subclass ``ElementBuilder`` and implement ``build()``.
2. Decorate the class with ``@plugin_registry.register("WALL")``
   (or the appropriate type key).
3. At import-time the class is registered; the core API resolves
   builders via ``plugin_registry.get("WALL")``.
"""

from __future__ import annotations

import importlib
import pkgutil
from abc import ABC, abstractmethod
from typing import Any, Dict, Type

import ifcopenshell


class ElementBuilder(ABC):
    """Abstract base class every element plugin must implement."""

    @abstractmethod
    def build(
        self,
        model: ifcopenshell.file,
        body_context: Any,
        storey: Any,
        payload: Any,
    ) -> Any:
        """Create the IFC element and attach it to *storey*.

        Parameters
        ----------
        model : ifcopenshell.file
            The current IFC model.
        body_context : IfcGeometricRepresentationSubContext
            The ``Body`` sub-context for 3-D geometry.
        storey : IfcBuildingStorey
            The storey to contain the element.
        payload : Pydantic model
            The validated element payload.

        Returns
        -------
        IfcProduct
            The created IFC element entity.
        """
        ...


class PluginRegistry:
    """A simple dictionary-based registry with a decorator API."""

    def __init__(self) -> None:
        self._builders: Dict[str, ElementBuilder] = {}

    def register(self, type_key: str):
        """Class decorator that registers a builder under *type_key*.

        Example::

            @plugin_registry.register("WALL")
            class Wall3DBuilder(ElementBuilder):
                ...
        """

        def decorator(cls: Type[ElementBuilder]):
            instance = cls()
            self._builders[type_key.upper()] = instance
            return cls

        return decorator

    def get(self, type_key: str) -> ElementBuilder:
        """Look up a registered builder by its type key.

        Raises ``KeyError`` with a helpful message on miss.
        """
        key = type_key.upper()
        if key not in self._builders:
            available = ", ".join(sorted(self._builders.keys())) or "(none)"
            raise KeyError(
                f"No plugin registered for type '{key}'. "
                f"Available types: {available}"
            )
        return self._builders[key]

    @property
    def available_types(self) -> list[str]:
        return sorted(self._builders.keys())


# ── Global singleton ──────────────────────────────────────────────
plugin_registry = PluginRegistry()


def discover_plugins() -> None:
    """Auto-import every module under ``app.plugins.elements``.

    Importing a module triggers its ``@plugin_registry.register``
    decorators, populating the registry automatically.
    """
    import app.plugins.elements as elements_pkg

    for _importer, module_name, _ispkg in pkgutil.iter_modules(elements_pkg.__path__):
        importlib.import_module(f"app.plugins.elements.{module_name}")
