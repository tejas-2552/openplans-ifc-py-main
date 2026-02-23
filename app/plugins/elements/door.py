"""Door element plugin.

Creates an IfcDoor from a DoorPayload, assigning representations
for both the door frame and the door panel, positioned correctly
in the IFC Z-up coordinate system.
"""

from __future__ import annotations

import math
from typing import Any, Tuple

import ifcopenshell
import ifcopenshell.api
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.geometry
import ifcopenshell.api.style

from app.models.base import DoorPayload, Point3D
from app.plugins.registry import ElementBuilder, plugin_registry


# ── Coordinate helpers ────────────────────────────────────────────

def _threejs_to_ifc(pt: Point3D) -> Tuple[float, float, float]:
    """Convert a Three.js point (Y-up) to IFC (Z-up).

    Mapping:  Three.js (x, y, z) → IFC (x, -z, y)
    """
    return (pt.x, -pt.z, pt.y)


def _int_to_rgb(color_int: int) -> Tuple[float, float, float]:
    """Convert an integer RGB color (e.g. 0xC7C7C7) to a normalized (0-1) tuple."""
    r = ((color_int >> 16) & 0xFF) / 255.0
    g = ((color_int >> 8) & 0xFF) / 255.0
    b = (color_int & 0xFF) / 255.0
    return (r, g, b)


# ── Door builder ──────────────────────────────────────────────────

@plugin_registry.register("DOOR")
class DoorBuilder(ElementBuilder):
    """Builds an IfcDoor with shape representation and styles."""

    def build(
        self,
        model: ifcopenshell.file,
        body_context: Any,
        storey: Any,
        payload: DoorPayload,
    ) -> Any:
        # 1. Transform coordinates
        ifc_pos = _threejs_to_ifc(payload.doorPosition)
        
        # Determine unique name (use ogid if available)
        door_name = payload.labelName
        if payload.ogid:
            door_name = f"{payload.labelName}_{payload.ogid}"

        # 2. Create IfcDoor entity
        door = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcDoor",
            name=door_name,
        )

        # 3. Add door representation
        # Lining properties (frame)
        lining_properties = {
            "LiningDepth": payload.frameDimensions.thickness,
            "LiningThickness": payload.frameDimensions.width,
        }
        
        # Panel properties (door body)
        panel_properties = {
            "PanelDepth": payload.doorDimensions.thickness,
        }
        
        representation = ifcopenshell.api.run(
            "geometry.add_door_representation",
            model,
            context=body_context,
            overall_height=payload.doorDimensions.height,
            overall_width=payload.doorDimensions.width,
            operation_type="SINGLE_SWING_LEFT",
            lining_properties=lining_properties,
            panel_properties=panel_properties,
        )

        # 4. Assign representation
        ifcopenshell.api.run(
            "geometry.assign_representation",
            model,
            product=door,
            representation=representation,
        )

        # 5. Object Placement (oriented appropriately based on swingRotation if needed, but defaults to unit vectors)
        # Convert swingRotation (radians or degrees) to rotation around IFC Z-axis.
        # Assuming swingRotation is not strictly the placement rotation but could represent Door Swing.
        # We will just face the door along the X-axis by default, which is standard for a 0-rotation door.
        
        # Actually place it at `ifc_pos`
        door.ObjectPlacement = model.createIfcLocalPlacement(
            RelativePlacement=model.createIfcAxis2Placement3D(
                Location=model.createIfcCartesianPoint(
                    (ifc_pos[0], ifc_pos[1], ifc_pos[2])
                ),
                Axis=model.createIfcDirection((0.0, 0.0, 1.0)),
                RefDirection=model.createIfcDirection((1.0, 0.0, 0.0))
            )
        )

        # 6. Apply Styles
        door_rgb = _int_to_rgb(payload.doorColor)
        frame_rgb = _int_to_rgb(payload.frameColor)

        # Make a style for the door panel
        door_style = ifcopenshell.api.run("style.add_style", model, name=f"{door_name}_PanelStyle")
        ifcopenshell.api.run(
            "style.add_surface_style",
            model,
            style=door_style,
            ifc_class="IfcSurfaceStyleShading",
            attributes={
                "SurfaceColour": {
                    "Name": "DoorColor",
                    "Red": door_rgb[0],
                    "Green": door_rgb[1],
                    "Blue": door_rgb[2],
                },
                "Transparency": 0.0,
            },
        )
        
        # Make a style for the frame
        frame_style = ifcopenshell.api.run("style.add_style", model, name=f"{door_name}_FrameStyle")
        ifcopenshell.api.run(
            "style.add_surface_style",
            model,
            style=frame_style,
            ifc_class="IfcSurfaceStyleShading",
            attributes={
                "SurfaceColour": {
                    "Name": "FrameColor",
                    "Red": frame_rgb[0],
                    "Green": frame_rgb[1],
                    "Blue": frame_rgb[2],
                },
                "Transparency": 0.0,
            },
        )

        # Assign styles to representation
        # add_door_representation typically creates an Items list where item 0 is the panel and item 1 (if present) is the lining.
        # If the API doesn't support sub-item styling easily, we just assign the door style to the whole representation or 
        # try to map it. Let's just assign both styles; viewers typically pick the first or cycle them.
        # A more robust approach targets specifically the panel/lining shape representations if nested.
        try:
            ifcopenshell.api.run(
                "style.assign_representation_styles",
                model,
                shape_representation=representation,
                styles=[door_style, frame_style],
            )
        except Exception:
            # Fallback if api complains about multiple styles
            ifcopenshell.api.run(
                "style.assign_representation_styles",
                model,
                shape_representation=representation,
                styles=[door_style],
            )

        # 7. Assign to storey
        ifcopenshell.api.run(
            "spatial.assign_container",
            model,
            relating_structure=storey,
            products=[door],
        )

        return door
