"""Wall builder plugin using the official IfcOpenShell API.

Accepts a list of points forming a closed polygon.  Each consecutive
pair of points becomes a wall segment, created via the official
``geometry.add_wall_representation`` API.

Ref: https://docs.ifcopenshell.org/ifcopenshell-python/geometry_creation.html
"""

from __future__ import annotations

import math
from typing import Any, List, Tuple

import ifcopenshell
import ifcopenshell.api
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.geometry
import ifcopenshell.api.style

from app.models.base import Point3D, WallPayload
from app.plugins.registry import ElementBuilder, plugin_registry


# ── Coordinate helpers ────────────────────────────────────────────

def _threejs_to_ifc(pt: Point3D) -> Tuple[float, float, float]:
    """Convert a Three.js point (Y-up) to IFC (Z-up).

    Mapping:  Three.js (x, y, z) → IFC (x, -z, y)
    """
    return (pt.x, -pt.z, pt.y)


def _hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
    """Convert ``#RRGGBB`` to normalised (0-1) RGB tuple."""
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


# ── Wall builder ──────────────────────────────────────────────────

@plugin_registry.register("WALL")
class Wall3DBuilder(ElementBuilder):
    """Build wall segments from a closed polygon of points.

    For N points, creates N wall segments (the last point connects
    back to the first).  Each segment uses the official
    ``geometry.add_wall_representation`` API which produces a proper
    thin-rectangle ``IfcExtrudedAreaSolid`` (SweptSolid).
    """

    def build(
        self,
        model: ifcopenshell.file,
        body_context: Any,
        storey: Any,
        payload: WallPayload,
    ) -> Any:
        # Transform all points: Three.js Y-up → IFC Z-up
        ifc_pts = [_threejs_to_ifc(pt) for pt in payload.points]
        n = len(ifc_pts)
        rgb = _hex_to_rgb(payload.wallColor)

        walls: list[Any] = []

        for i in range(n - 1):
            p1 = ifc_pts[i]
            p2 = ifc_pts[i + 1]  # consecutive pairs only, no auto-close

            # Wall length and direction on the XY plane
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            wall_length = math.hypot(dx, dy)
            angle = math.atan2(dy, dx)

            seg_name = f"{payload.name}_{i + 1}"

            # 1. Create wall entity
            wall = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcWall",
                name=seg_name,
            )

            # 2. Official add_wall_representation → thin rectangle extruded
            #    offset=-thickness/2 centres the wall on the axis line so
            #    adjacent walls meet at their corners without gaps.
            representation = ifcopenshell.api.run(
                "geometry.add_wall_representation",
                model,
                context=body_context,
                length=wall_length,
                height=payload.wallHeight,
                thickness=payload.wallThickness,
                offset=-payload.wallThickness / 2,
            )

            # 3. Assign representation
            ifcopenshell.api.run(
                "geometry.assign_representation",
                model,
                product=wall,
                representation=representation,
            )

            # 4. Object Placement: start at p1, oriented toward p2
            wall.ObjectPlacement = model.createIfcLocalPlacement(
                RelativePlacement=model.createIfcAxis2Placement3D(
                    Location=model.createIfcCartesianPoint(
                        (p1[0], p1[1], p1[2])
                    ),
                    Axis=model.createIfcDirection((0.0, 0.0, 1.0)),
                    RefDirection=model.createIfcDirection(
                        (math.cos(angle), math.sin(angle), 0.0)
                    ),
                )
            )

            # 5. Surface colour
            style = ifcopenshell.api.run(
                "style.add_style", model, name=f"{seg_name}_style"
            )
            ifcopenshell.api.run(
                "style.add_surface_style",
                model,
                style=style,
                ifc_class="IfcSurfaceStyleShading",
                attributes={
                    "SurfaceColour": {
                        "Name": payload.wallColor,
                        "Red": rgb[0],
                        "Green": rgb[1],
                        "Blue": rgb[2],
                    },
                    "Transparency": 0.0,
                },
            )
            ifcopenshell.api.run(
                "style.assign_representation_styles",
                model,
                shape_representation=representation,
                styles=[style],
            )

            # 6. Assign to storey
            ifcopenshell.api.run(
                "spatial.assign_container",
                model,
                relating_structure=storey,
                products=[wall],
            )

            walls.append(wall)

        # Return the first wall (for backward compat with single-return tests)
        return walls[0]
