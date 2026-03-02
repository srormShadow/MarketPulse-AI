from fastapi import APIRouter

from marketpulse.routes.debug import router as debug_router
from marketpulse.routes.diagnostics import router as diagnostics_router
from marketpulse.routes.forecast import router as forecast_router
from marketpulse.routes.insights import router as insights_router
from marketpulse.routes.recommendations import router as recommendations_router
from marketpulse.routes.seed import router as seed_router
from marketpulse.routes.upload import router as upload_router

router = APIRouter()
router.include_router(upload_router)
router.include_router(debug_router)
router.include_router(diagnostics_router)
router.include_router(forecast_router)
router.include_router(insights_router)
router.include_router(recommendations_router)
router.include_router(seed_router)
