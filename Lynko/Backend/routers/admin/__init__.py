from fastapi import APIRouter

# Importamos cada sub-archivo que ya tienes creado en la carpeta admin
from .dashboard import router as dashboard_router
from .preguntas import router as preguntas_router
from .estudiantes import router as estudiantes_router
from .examenes import router as examenes_router
from .retos import router as retos_router
from .actividades import router as actividades_router

# Unificamos todo bajo el prefijo /admin
router = APIRouter(prefix="/admin", tags=["Administración"])

# Agregamos cada módulo al router principal del admin
router.include_router(dashboard_router)
router.include_router(preguntas_router)
router.include_router(estudiantes_router)
router.include_router(examenes_router)
router.include_router(retos_router)
router.include_router(actividades_router)