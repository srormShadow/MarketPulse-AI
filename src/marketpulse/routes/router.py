from fastapi import APIRouter

from marketpulse.core.config import get_settings
from marketpulse.routes.admin import router as admin_router
from marketpulse.routes.auth import router as auth_router
from marketpulse.routes.dashboard import router as dashboard_router
from marketpulse.routes.diagnostics import router as diagnostics_router
from marketpulse.routes.festivals import router as festivals_router
from marketpulse.routes.forecast import router as forecast_router
from marketpulse.routes.insights import router as insights_router
from marketpulse.routes.recommendations import router as recommendations_router
from marketpulse.routes.seed import router as seed_router
from marketpulse.routes.shopify import router as shopify_router
from marketpulse.routes.simulation import router as simulation_router
from marketpulse.routes.upload import router as upload_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(admin_router)
router.include_router(upload_router)
router.include_router(diagnostics_router)
router.include_router(festivals_router)
router.include_router(forecast_router)
router.include_router(insights_router)
router.include_router(simulation_router)
router.include_router(recommendations_router)
router.include_router(seed_router)
router.include_router(shopify_router)

# Only include debug routes in explicit local debug environments
_settings = get_settings()
if _settings.environment.lower() in {"development", "dev", "local"} and _settings.debug:
    from marketpulse.routes.debug import router as debug_router

    router.include_router(debug_router)
