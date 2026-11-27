from pydantic import BaseModel, Field, EmailStr, ValidationError, ConfigDict, conint
from typing import Any, List, Optional, Dict, Annotated
from typing import ForwardRef
from fastapi import Form, HTTPException
from datetime import date, datetime

# ==============================================================================
# 1. ESQUEMAS BASE Y COMPARTIDOS (Utilitarios)
# ==============================================================================

class OpcionSchema(BaseModel):
    """Esquema base para representar una opción de respuesta."""
    opcion: str
    es_correcta: bool

    
    model_config = ConfigDict(from_attributes=True)


OpcionCreateSchema = OpcionSchema

class PreguntaExamenCreateSchema(BaseModel):
    pregunta: str = Field(..., min_length=10)
    puntos_recompensa: int = 10
    opciones: List[OpcionCreateSchema]
    
# ==============================================================================
# 2. GESTIÓN DE EXÁMENES / RETOS (Administrador)
# ==============================================================================

class ExamenCreate(BaseModel):
    """Esquema para la creación o edición de un examen/reto principal."""
    titulo: str = Field(..., min_length=3, max_length=255, description="Título del examen")
    descripcion: str = Field(..., description="Descripción detallada del examen")
    id_materia: int = Field(..., gt=0, description="ID de la materia a la que pertenece")
    
    duracion_minutos: Annotated[int, Field(gt=0, description="Duración en minutos")]
    
    puntaje_minimo_aprobatorio: Annotated[int, Field(ge=0, description="Puntaje mínimo para aprobar")]
    
    preguntas: List[Annotated[PreguntaExamenCreateSchema, "PreguntaExamenCreateSchema"]]



class ExamenResponse(ExamenCreate):
    """Esquema de respuesta al leer un examen (incluye datos de BD)."""
    id_examen: int
    fecha_creacion: datetime

    model_config = ConfigDict(from_attributes=True)


class RetoAdminSchema(BaseModel):
    """Esquema para listar retos con métricas (Vista Administrador)."""
    id_reto: int
    titulo: str
    descripcion: str
    puntos_totales: int
    fecha_inicio: date
    fecha_fin: date
    total_preguntas: int
    total_intentos: int
    promedio_puntos: float

    model_config = ConfigDict(from_attributes=True)

# --- Estructuras complejas para creación de retos ---

class RetoParteCreateSchema(BaseModel):
    """Esquema para una parte/capítulo individual al crear un reto."""
    parte_cuento: str
    pregunta: str
    puntos: int
    opciones: List[OpcionCreateSchema]
    model_config = ConfigDict(from_attributes=True)


class CrearRetoSchema(BaseModel):
    """Esquema principal para crear un reto completo con sus partes."""
    titulo: str
    descripcion: str
    puntos_totales: int
    fecha_inicio: datetime
    fecha_fin: datetime
    partes: List[RetoParteCreateSchema]
    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 3. GESTIÓN DE PREGUNTAS (Catálogo)
# ==============================================================================


class PreguntaCreateSchema(BaseModel):
    """Esquema general para crear/editar preguntas en el catálogo."""
    pregunta: str
    id_materia: int
    nivel: int
    puntos: int
    opciones: List[OpcionCreateSchema]
    model_config = ConfigDict(from_attributes=True)


class PreguntaAdminSchema(BaseModel):
    """Esquema de respuesta para visualizar preguntas en el panel de admin."""
    id_pregunta: int
    materia: str # Nombre de la materia
    pregunta: str
    nivel_dificultad: int
    puntos_recompensa: int
    opciones: List[OpcionSchema]

    model_config = ConfigDict(from_attributes=True)


PreguntaRetoCreate = PreguntaExamenCreateSchema

class OpcionSchema(BaseModel):
    opcion: str
    es_correcta: bool

class PreguntaRetoCreate(BaseModel):
    pregunta: str
    opciones: List[OpcionSchema]
    puntos_recompensa: int

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 4. GESTIÓN DE USUARIOS (Estudiantes)
# ==============================================================================

class EstudianteAdminSchema(BaseModel):
    """Esquema para listar/gestionar estudiantes (Vista Administrador)."""
    id_usuario: int
    nombre: str
    correo: EmailStr
    puntaje_total: int
    nivel: int
    dias_racha: int

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def as_form(
        cls,
        id_estudiante: int = Form(...),
        nombre: str = Form(...),
        correo: str = Form(...),
        
    ):
        
        try:
            # NOTA: Al editar, usualmente no se cambian estos valores desde el form
            return cls(
                id_usuario=id_estudiante,
                nombre=nombre,
                correo=correo,
                puntaje_total=0, 
                nivel=1,         
                dias_racha=0    
            )
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=e.errors())


class RankingEstudianteSchema(BaseModel):
    """Esquema para visualizar el Top 10 de estudiantes."""
    nombre: str
    nivel: int
    puntaje_total: int

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 5. REPORTES, MÉTRICAS E HISTORIAL
# ==============================================================================

class MetricaMateriaSchema(BaseModel):
    """Esquema para métricas globales agrupadas por materia."""
    nombre_materia: str
    total_intentos: int
    promedio_nota: float
    total_aprobados: int

    model_config = ConfigDict(from_attributes=True)


class HistorialExamenSchema(BaseModel):
    """Esquema para visualizar el historial detallado de intentos."""
    nombre_estudiante: str
    titulo_examen: str
    nombre_materia: str
    nota_final: float

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# 6. SISTEMA (Login Administrador)
# ==============================================================================

class AdminLoginSchema(BaseModel):
    """Esquema para recibir datos de login desde form-data."""
    correo: EmailStr
    contrasena: str = Field(..., alias="contraseña")

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def as_form(
        cls,
        correo: str = Form(...),
        contrasena: str = Form(..., alias="contraseña")
    ):
        return cls(correo=correo, contrasena=contrasena)
    

