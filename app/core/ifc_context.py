"""IFC project hierarchy initialisation.

Creates the standard IFC spatial structure:
    IfcProject → IfcSite → IfcBuilding → IfcBuildingStorey

Returns the ``(model, storey, body_context)`` tuple that every element
builder needs to attach geometry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

import ifcopenshell
import ifcopenshell.api
import ifcopenshell.api.context
import ifcopenshell.api.root
import ifcopenshell.api.unit
import ifcopenshell.api.spatial
import ifcopenshell.util.shape_builder

if TYPE_CHECKING:
    pass


def create_ifc_context(
    project_name: str = "OpenPlans BIM Project",
    site_name: str = "Default Site",
    building_name: str = "Default Building",
    storey_name: str = "Ground Floor",
) -> Tuple[ifcopenshell.file, object, object]:
    """Bootstrap a minimal IFC model with spatial hierarchy.

    Returns
    -------
    model : ifcopenshell.file
        The fresh IFC model.
    storey : IfcBuildingStorey
        The default storey to assign elements to.
    body_context : IfcGeometricRepresentationSubContext
        The ``Body`` sub-context for 3-D shape representations.
    """
    model = ifcopenshell.file(schema="IFC4")

    # ── Project (must exist BEFORE unit assignment) ───────────
    project = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject", name=project_name)

    # ── Units (SI metres — NOT the IfcOpenShell default of mm) ──
    length = ifcopenshell.api.run("unit.add_si_unit", model, unit_type="LENGTHUNIT", prefix=None)
    area = ifcopenshell.api.run("unit.add_si_unit", model, unit_type="AREAUNIT", prefix=None)
    volume = ifcopenshell.api.run("unit.add_si_unit", model, unit_type="VOLUMEUNIT", prefix=None)
    ifcopenshell.api.run("unit.assign_unit", model, units=[length, area, volume])

    # ── Geometric representation contexts ─────────────────────
    ctx = ifcopenshell.api.run("context.add_context", model, context_type="Model")
    body_context = ifcopenshell.api.run(
        "context.add_context",
        model,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=ctx,
    )

    # ── Spatial hierarchy ────────────────────────────────────
    site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite", name=site_name)
    building = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding", name=building_name)
    storey = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey", name=storey_name)

    # Aggregate: Project → Site → Building → Storey
    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=project, products=[site])
    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=site, products=[building])
    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=building, products=[storey])

    return model, storey, body_context
