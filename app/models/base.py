"""Pydantic v2 schemas for BIM element payloads.

Uses a discriminated union on the ``type`` field so that a single
``/generate`` endpoint can route heterogeneous element lists to the
correct plugin builder.
"""

from __future__ import annotations

from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Discriminator, Field, Tag


# ── Geometry primitives ───────────────────────────────────────────

class Point3D(BaseModel):
    """A point in Three.js coordinate space (Y-up).

    The coordinate transform to IFC (Z-up) is applied at the *builder*
    layer, not here — schemas always store raw frontend coordinates.
    """

    x: float
    y: float
    z: float


class Dimensions3D(BaseModel):
    """3D dimensions for elements like doors or frames."""

    width: float = Field(..., gt=0)
    height: float = Field(..., gt=0)
    thickness: float = Field(..., gt=0)


# ── Element payloads ──────────────────────────────────────────────

class WallPayload(BaseModel):
    """Wall defined by a list of points forming a closed polygon.

    Each consecutive pair of points becomes a wall segment.  The last
    point connects back to the first to close the polygon.  Each
    segment uses ``geometry.add_wall_representation`` (the official
    IfcOpenShell API) to create a proper thin-rectangle wall.
    """

    type: Literal["WALL"] = "WALL"
    name: str = Field(default="Wall", description="Human-readable wall name")
    points: List[Point3D] = Field(
        ..., min_length=2, description="Polygon vertices (Three.js coords). "
        "Consecutive pairs become wall segments; the polygon is auto-closed."
    )
    wallThickness: float = Field(
        ..., gt=0, description="Wall thickness in metres"
    )
    wallHeight: float = Field(
        default=3.0, gt=0, description="Wall height in metres"
    )
    wallColor: str = Field(
        default="#CCCCCC",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Hex colour, e.g. '#FF5733'",
    )


class WindowPayload(BaseModel):
    """Stub schema for future window plugin."""

    type: Literal["WINDOW"] = "WINDOW"
    name: str = Field(default="Window")
    width: float = Field(default=1.2, gt=0)
    height: float = Field(default=1.5, gt=0)
    sillHeight: float = Field(default=0.9, ge=0)
    position: Point3D = Field(default_factory=lambda: Point3D(x=0, y=0, z=0))


class DoorPayload(BaseModel):
    """Payload for door element."""

    type: Literal["DOOR"] = "DOOR"
    labelName: str = Field(default="Door")
    doorPosition: Point3D = Field(default_factory=lambda: Point3D(x=0, y=0, z=0))
    doorDimensions: Dimensions3D
    frameDimensions: Dimensions3D
    frameColor: int = Field(default=0, description="Integer RGB color for frame")
    doorColor: int = Field(default=0xC7C7C7, description="Integer RGB color for door panel")
    swingRotation: float = Field(default=0.0)
    isOpen: bool = Field(default=False)
    doorMaterial: str = Field(default="WOOD")
    ogid: Optional[str] = Field(default=None, description="External unique ID")


# ── Discriminated union ──────────────────────────────────────────


def _get_element_type(v: dict) -> str:
    """Extract the ``type`` key for discriminator routing."""
    return v.get("type", "")


ElementPayload = Annotated[
    Union[
        Annotated[WallPayload, Tag("WALL")],
        Annotated[WindowPayload, Tag("WINDOW")],
        Annotated[DoorPayload, Tag("DOOR")],
    ],
    Discriminator(_get_element_type),
]


# ── Top-level request ────────────────────────────────────────────

class ProjectMetadata(BaseModel):
    """Optional metadata attached to an IFC project."""

    projectName: str = Field(default="OpenPlans BIM Project")
    siteName: str = Field(default="Default Site")
    buildingName: str = Field(default="Default Building")
    storeyName: str = Field(default="Ground Floor")


class GenerateRequest(BaseModel):
    """Top-level payload accepted by ``POST /generate``."""

    elements: List[ElementPayload] = Field(
        ..., min_length=1, description="One or more element payloads"
    )
    metadata: Optional[ProjectMetadata] = Field(default=None)
