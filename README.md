# OpenPlans BIM Service

> Production-ready Python cloud service for automated **Building Information Modeling (BIM)** generation using [IfcOpenShell](https://ifcopenshell.org). Deployable to Google Cloud Run or AWS App Runner.

---

## Architecture

```
                    ┌──────────────────┐
   POST /generate → │   FastAPI Core   │
                    │  (routes.py)     │
                    └───────┬──────────┘
                            │ discriminated union
                    ┌───────▼──────────┐
                    │  Plugin Registry │
                    │  (registry.py)   │
                    └───────┬──────────┘
                ┌───────────┼───────────┐
                ▼           ▼           ▼
           ┌────────┐ ┌─────────┐ ┌────────┐
           │ WALL   │ │ WINDOW  │ │ DOOR   │
           │ 3D     │ │ (stub)  │ │ (stub) │
           └────────┘ └─────────┘ └────────┘
```

**Key design decisions:**
- **Plugin registry** — core API contains zero element-specific logic; plugins self-register via `@plugin_registry.register("TYPE")`
- **Coordinate transform** — frontend sends Three.js (Y-up), builder converts to IFC (Z-up): `(x, y, z) → (x, -z, y)`
- **Cloud-native** — stateless container writes to `/tmp/`, uploads to cloud storage, returns signed URLs

---

## Quickstart

### Local Development

```bash
# 1. Create virtual environment
python3.10 -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the server
uvicorn app.main:app --reload --port 8080

# 4. Test it
curl -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{
    "elements": [{
      "type": "WALL",
      "name": "MyWall",
      "points": [
        {"x": -5, "y": 0, "z": -2},
        {"x":  5, "y": 0, "z": -2},
        {"x":  5, "y": 0, "z":  5},
        {"x": -2, "y": 0, "z":  5}
      ],
      "wallThickness": 0.2,
      "wallColor": "#FF5733"
    }]
  }'
```

### Docker

```bash
docker build -t bim-service .
docker run --rm -p 8080:8080 bim-service
```

---

## API Reference

### `GET /health`

Liveness probe. Returns `{"status": "healthy", "available_plugins": "DOOR, WALL, WINDOW"}`.

### `POST /generate`

Generate an IFC file from a list of element payloads.

**Request body:**

```json
{
  "elements": [
    {
      "type": "WALL",
      "name": "Living Room Wall",
      "points": [
        {"x": 0, "y": 0, "z": 0},
        {"x": 10, "y": 0, "z": 0},
        {"x": 10, "y": 0, "z": 3},
        {"x": 0, "y": 0, "z": 3}
      ],
      "wallThickness": 0.2,
      "wallColor": "#CCCCCC"
    }
  ],
  "metadata": {
    "projectName": "My House",
    "siteName": "Plot 42",
    "buildingName": "Main House",
    "storeyName": "Ground Floor"
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `elements` | `Array` | ✅ | One or more element payloads |
| `elements[].type` | `string` | ✅ | Discriminator — `"WALL"`, `"WINDOW"`, `"DOOR"` |
| `elements[].points` | `Array<{x,y,z}>` | ✅ (walls) | Three.js coordinates (Y-up) |
| `elements[].wallThickness` | `float` | ✅ (walls) | Extrusion thickness in metres |
| `elements[].wallColor` | `string` | ❌ | Hex colour, default `#CCCCCC` |
| `metadata` | `object` | ❌ | Project-level names |

**Response:**

```json
{
  "status": "success",
  "file_url": "/tmp/bim_abc123.ifc",
  "created_elements": ["WALL:Living Room Wall"],
  "warnings": null
}
```

---

## Plugin Development Guide

### Adding a New Element Type

1. **Create the schema** in `app/models/base.py`:

```python
class SlabPayload(BaseModel):
    type: Literal["SLAB"] = "SLAB"
    name: str = "Slab"
    # ... your fields
```

2. **Add it to the union** in `base.py`:

```python
ElementPayload = Annotated[
    Union[WallPayload, WindowPayload, DoorPayload, SlabPayload],
    PydanticDiscriminator(_get_element_type),
]
```

3. **Create the builder** in `app/plugins/elements/slab.py`:

```python
from app.plugins.registry import ElementBuilder, plugin_registry

@plugin_registry.register("SLAB")
class SlabBuilder(ElementBuilder):
    def build(self, model, body_context, storey, payload):
        # 1. Transform coords: _threejs_to_ifc(pt)
        # 2. Create geometry via ShapeBuilder
        # 3. Create IfcSlab entity
        # 4. Apply style
        # 5. Assign to storey
        return slab
```

**That's it.** The registry auto-discovers the module on startup. No changes to `main.py` or `routes.py`.

---

## Coordinate System

```
Three.js (Y-up)          IFC (Z-up)
    Y (up)                  Z (up)
    │                       │
    │                       │
    └──── X (right)         └──── X (right)
   /                       /
  Z (toward viewer)       Y (forward)

Transform: (x, y, z)_threejs → (x, -z, y)_ifc
```

The transform is applied in each plugin builder, NOT in the schema layer. Schemas always store raw frontend coordinates.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `STORAGE_BACKEND` | `local` | `local`, `gcs`, or `s3` |
| `GCS_BUCKET` | — | Required when `STORAGE_BACKEND=gcs` |
| `S3_BUCKET` | — | Required when `STORAGE_BACKEND=s3` |
| `AWS_REGION` | `us-east-1` | AWS region for S3 |

---

## Deployment

### Google Cloud Run

```bash
# Build & push
gcloud builds submit --tag gcr.io/YOUR_PROJECT/bim-service

# Deploy
gcloud run deploy bim-service \
  --image gcr.io/YOUR_PROJECT/bim-service \
  --port 8080 \
  --set-env-vars STORAGE_BACKEND=gcs,GCS_BUCKET=your-bucket \
  --allow-unauthenticated
```

### AWS App Runner

```bash
# Build & push to ECR
aws ecr get-login-password | docker login --username AWS --password-stdin YOUR_ACCOUNT.dkr.ecr.REGION.amazonaws.com
docker build -t bim-service .
docker tag bim-service:latest YOUR_ACCOUNT.dkr.ecr.REGION.amazonaws.com/bim-service:latest
docker push YOUR_ACCOUNT.dkr.ecr.REGION.amazonaws.com/bim-service:latest

# Deploy via console or CLI with:
#   Port: 8080
#   Environment: STORAGE_BACKEND=s3, S3_BUCKET=your-bucket
```

---

## Running Tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

---

## Project Structure

```
openplans-ifc-py/
├── Dockerfile
├── requirements.txt
├── README.md
├── .antigravity/rules.md        # Project constraints
├── app/
│   ├── main.py                  # FastAPI entry point
│   ├── api/
│   │   └── routes.py            # REST endpoints
│   ├── core/
│   │   ├── ifc_context.py       # IFC hierarchy init
│   │   └── storage.py           # Cloud storage backends
│   ├── models/
│   │   └── base.py              # Pydantic schemas
│   └── plugins/
│       ├── registry.py          # Plugin ABC + registry
│       └── elements/
│           ├── wall_3d.py       # 3D polyline wall ✅
│           ├── window.py        # Stub 🚧
│           └── door.py          # Stub 🚧
└── tests/
    ├── conftest.py              # Shared fixtures
    ├── test_wall.py             # Wall builder + API tests
    ├── test_registry.py         # Registry + stub tests
    └── test_ifc_context.py      # IFC hierarchy tests
```
