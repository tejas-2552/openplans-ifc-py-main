"""REST API routes for BIM generation."""

from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict
import base64
import os
import io


from fastapi import APIRouter, HTTPException

from app.core.ifc_context import create_ifc_context
from app.core.storage import get_storage_backend
from app.models.base import GenerateRequest
from app.plugins.registry import plugin_registry

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Liveness probe for Cloud Run / App Runner."""
    return {
        "status": "healthy",
        "available_plugins": ", ".join(plugin_registry.available_types),
    }


@router.post("/generate")
async def generate_bim(request: GenerateRequest) -> Dict[str, Any]:
    """Accept a list of element payloads and return an IFC file.

    Each element is routed to its registered plugin builder based on
    the ``type`` discriminator field.
    """
    # ── Resolve project metadata ─────────────────────────────
    meta = request.metadata or type(request.metadata)()  # defaults
    if request.metadata is None:
        from app.models.base import ProjectMetadata
        meta = ProjectMetadata()

    model, storey, body_context = create_ifc_context(
        project_name=meta.projectName,
        site_name=meta.siteName,
        building_name=meta.buildingName,
        storey_name=meta.storeyName,
    )

    # ── Process each element ─────────────────────────────────
    created_elements: list[str] = []
    errors: list[str] = []

    for idx, element in enumerate(request.elements):
        element_type = element.type
        try:
            builder = plugin_registry.get(element_type)
            product = builder.build(model, body_context, storey, element)
            created_elements.append(
                f"{element_type}:{getattr(product, 'Name', f'element_{idx}')}"
            )
            logger.info("Built %s element #%d", element_type, idx)
        except NotImplementedError as exc:
            errors.append(f"Element #{idx} ({element_type}): {exc}")
            logger.warning("Skipped element #%d: %s", idx, exc)
        except KeyError as exc:
            errors.append(f"Element #{idx}: {exc}")
            logger.error("Unknown plugin for element #%d: %s", idx, exc)
        except Exception as exc:
            errors.append(f"Element #{idx} ({element_type}): {exc}")
            logger.exception("Error building element #%d", idx)

    if not created_elements:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "No elements could be built.",
                "errors": errors,
            },
        )

    # ── Write IFC to tmp & upload ────────────────────────────
    tmp_dir = Path(tempfile.gettempdir())
    filename = f"bim_{uuid.uuid4().hex[:12]}.ifc"
    local_path = str(tmp_dir / filename)
    # TODO : commenting this part as it not saving anywher
    #model.write(local_path)
    logger.info("Wrote IFC file: %s", local_path)

    ifc_string = model.to_string()
    file_content = ifc_string.encode("utf-8")
    base64_encoded = base64.b64encode(file_content).decode("utf-8")
    file_size = len(file_content)
    file_name = f"bim_{uuid.uuid4().hex[:12]}.ifc"
    
    storage = get_storage_backend()
    download_url = storage.upload(local_path)

    # Read the file and convert to base64
    #with open(local_path, "rb") as file:
        #file_content = file.read()
        #base64_encoded = base64.b64encode(file_content).decode('utf-8')
    
    # Get file info
    #file_name = os.path.basename(local_path)
    #file_size = os.path.getsize(local_path)

    return {
        "status": "success",
        "file_url": download_url, 
        "base64": {
            "data": base64_encoded,
            "filename": file_name,
            "size": file_size,
            "mime_type": "application/octet-stream"  # Adjust based on your file type
        },
        "created_elements": created_elements,
        "warnings": errors if errors else None,
    }
