from fastapi import APIRouter

from app.routes.debug import router as debug_router
from app.routes.upload import router as upload_router

router = APIRouter()
router.include_router(upload_router)
router.include_router(debug_router)
