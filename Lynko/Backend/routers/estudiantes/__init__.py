from fastapi import APIRouter

# Importamos cada sub-módulo de estudiante
from .auth_landing import router as auth_landing_router
from .dashboard import router as dashboard_router
from .materias import router as materias_router
from .examenes import router as examenes_router
from .retos import router as retos_router
from .actividades import router as actividades_router
from .notificaciones import router as notificaciones_router

# Creamos el router general para estudiantes (sin prefijo estricto o con el que prefieras)
router = APIRouter(tags=["Estudiantes"])

# Incluimos cada sub-router
router.include_router(auth_landing_router)
router.include_router(dashboard_router)
router.include_router(materias_router)
router.include_router(examenes_router)
router.include_router(retos_router)
router.include_router(actividades_router)
router.include_router(notificaciones_router)