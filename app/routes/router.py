from fastapi import APIRouter

from app.routes.upload import router as upload_router

router = APIRouter()
router.include_router(upload_router)
