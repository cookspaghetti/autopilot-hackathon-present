# app/routers/examples.py
"""
Example endpoints demonstrating authorization patterns.

These endpoints show how to use the authorization engine in different scenarios:
1. Simple role-based access control
2. Context-aware authorization with database data
3. Geofencing based on request origin
4. Path parameter authorization

For production use, remove or adapt these examples to your specific needs.
"""

import logging

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from ..authz import AuthzEngine
from ..core.database import get_db
from ..models import Item as ItemModel
from ..security import get_current_user

log = logging.getLogger(__name__)

router = APIRouter(tags=["Examples"])

# Load the authorization engine
authz_engine = AuthzEngine("app/authz.map.json", "app/public.map.json")

# Optional: GeoIP for geofencing
geoip_reader = None
try:
    import geoip2.database
    import geoip2.errors

    geoip_reader = geoip2.database.Reader("GeoLite2-Country.mmdb")
except FileNotFoundError:
    log.warning("GeoLite2-Country.mmdb not found. Geofencing will default to 'US'.")
except ImportError:
    log.warning("geoip2 not installed. Geofencing will default to 'US'.")


# =============================================================================
# SIMPLE SCENARIOS
# =============================================================================


@router.get("/test", tags=["Simple Scenarios"])
def read_test_data(user: dict = Depends(get_current_user)):
    """
    Simple test endpoint.
    Requires any authenticated user (not pending).
    Authorization is handled by authz.map.json: ANY: ["admin", "user"]
    """
    return {"message": f"Hello, {user.get('preferred_username')}"}


@router.get("/admin/dashboard", tags=["Simple Scenarios"])
def get_admin_dashboard(user: dict = Depends(get_current_user)):
    """
    Admin dashboard endpoint.
    Requires the 'admin' role.
    Authorization is handled by authz.map.json: ALL: ["admin"]
    """
    return {
        "message": f"Welcome to the admin dashboard, {user.get('preferred_username')}"
    }


# =============================================================================
# CONTEXT-AWARE SCENARIOS
# These demonstrate the 3-step pattern:
# 1. Fetch data needed for context from database
# 2. Build the 'context' dictionary
# 3. Call the engine manually: authz_engine.check(request, user, context)
# =============================================================================


@router.put("/items/{item_id}", tags=["Context Scenarios"])
def update_item(
    item_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update an item. Demonstrates context-aware authorization using database data.

    The authorization engine can check ownership or other business rules
    by inspecting the 'resource' in the context.

    Example authz rule (in authz.map.json):
    ```
    "/api/items/{item_id}": {
        "PUT": {
            "ANY": ["admin", { "claims": { "sub": "{context.resource.owner_id}" } }]
        }
    }
    ```
    """
    item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
    if not item:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Item not found")

    # Pass the database record to the authorization engine
    authz_engine.check(request, user, context={"resource": item})

    # If authorization passes, update the item
    item.name = f"Updated: {item.name}"
    db.commit()
    return {"status": "Item updated", "item_id": item.id, "name": item.name}


@router.get("/analytics/{region}", tags=["Context Scenarios"])
def get_analytics(
    region: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """
    Regional analytics endpoint.

    Demonstrates path parameter authorization - the engine automatically
    resolves {path.region} from the URL.

    Example authz rule:
    ```
    "/api/analytics/{region}": {
        "ALL": ["regional-manager", { "claims": { "region": "{path.region}" } }]
    }
    ```
    """
    authz_engine.check(request, user)  # No custom context needed
    return {"region": region, "sales": 12345, "revenue": 567890}


@router.get("/secure-asset", tags=["Context Scenarios"])
def get_secure_asset(
    request: Request,
    user: dict = Depends(get_current_user),
    x_forwarded_for: str | None = Header(None),
):
    """
    Geofencing example.

    Authorization is based on request origin country.
    Uses GeoIP lookup to determine the user's country.

    Example authz rule:
    ```
    "/api/secure-asset": {
        "ALL": [{ "claims": { "source_country": "US" } }]
    }
    ```
    """
    country = "US"  # Default for development
    if geoip_reader and x_forwarded_for:
        try:
            import geoip2.errors

            country = geoip_reader.country(
                x_forwarded_for.split(",")[0]
            ).country.iso_code
        except geoip2.errors.AddressNotFoundError:
            country = "UNKNOWN"

    authz_engine.check(
        request, user, context={"environment": {"source_country": country}}
    )
    return {"asset": "Top Secret Data", "accessed_from": country}


# For additional context-aware scenarios, see the project documentation.
