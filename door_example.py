"""Standalone script to demonstrate the IFC Door Builder.

Generates a simple IFC file containing a single door based on the provided JSON payload.
"""

from pathlib import Path

import ifcopenshell
from pydantic import ValidationError

from app.core.ifc_context import create_ifc_context
from app.models.base import DoorPayload
from app.plugins.elements.door import DoorBuilder


def main():
    print("Initializing IFC context...")
    model, storey, body_ctx = create_ifc_context()

    door_json = {
        "type": "DOOR",
        "labelName": "Main Entry Door",
        "doorPosition": {"x": 2, "y": 0, "z": 0},
        "doorDimensions": {"width": 0.9, "height": 2.1, "thickness": 0.05},
        "frameDimensions": {"width": 0.05, "height": 2.1, "thickness": 0.15},
        "frameColor": 255,          # Example integer color (Blue)
        "doorColor": 13092807,      # #C7C7C7 / 13092807
        "swingRotation": 90.0,
        "isOpen": True,
        "doorMaterial": "WOOD",
        "ogid": "door-12345"
    }

    try:
        print("Parsing door payload...")
        payload = DoorPayload(**door_json)
    except ValidationError as e:
        print("Error parsing door payload:")
        print(e)
        return

    print("Building door geometry...")
    builder = DoorBuilder()
    door = builder.build(model, body_ctx, storey, payload)

    print(f"Created door: {door.Name}")

    out_file = Path("door_output.ifc")
    print(f"Writing IFC file to {out_file.absolute()}...")
    model.write(str(out_file))
    print("Done!")


if __name__ == "__main__":
    main()
