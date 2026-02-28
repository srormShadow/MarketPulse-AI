from fastapi import APIRouter

from marketpulse.routes.debug import router as debug_router
from marketpulse.routes.forecast import router as forecast_router
from marketpulse.routes.upload import router as upload_router

router = APIRouter()
router.include_router(upload_router)
router.include_router(debug_router)
router.include_router(forecast_router)
