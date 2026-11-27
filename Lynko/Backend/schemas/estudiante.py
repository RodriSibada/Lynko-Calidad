from typing import Dict, Any, Annotated, List, Optional
from pydantic import BaseModel, Field, field_validator, EmailStr, ValidationError, ConfigDict
from datetime import datetime
from fastapi import Form, HTTPException
from decimal import Decimal
import re

def to_float(v: Any) -> float:
    return float(v) if isinstance(v, Decimal) else v

# --- Esquemas Compartidos ---

class OpcionBaseSchema(BaseModel):
    opcion: str
    model_config = ConfigDict(from_attributes=True)
        
class PerfilEstudianteUpdateSchema(BaseModel):
    nombre: str = Field(..., min_length=2)
    correo: EmailStr
    contrasena: str = Field(..., min_length=8, alias="contraseña")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

    @field_validator('contrasena')
    @classmethod
    def validar_complejidad_contrasena(cls, v: str) -> str:
        if not re.search(r"[a-zA-Z]", v) or not re.search(r"[0-9]", v):
            raise ValueError("La contraseña debe combinar letras y números.")
        return v

    @classmethod
    def as_form(
        cls,
        nombre: str = Form(...),
        correo: str = Form(...),
        contrasena: str = Form(..., alias="contraseña")
    ):
        try:
            return cls(nombre=nombre, correo=correo, contrasena=contrasena)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=e.errors())

class RespuestasRetoSchema(BaseModel):
    respuestas: Dict[int, int]

    @field_validator('respuestas')
    @classmethod
    def validar_no_vacio(cls, v: dict):
        if not v:
            raise ValueError("No se han enviado respuestas.")
        return v         

class RecuperarRequest(BaseModel):
    correo: str

class ActualizarPasswordRequest(BaseModel):
    token: str
    nueva_contrasena: str

class EstudianteActualizar(BaseModel):
    nombre: str = Field(..., min_length=2)
    correo: EmailStr = Field(...)
    contrasena: str = Field(..., min_length=8)

    @field_validator('contrasena')
    @classmethod
    def validar_complejidad_contrasena(cls, v: str) -> str:
        if not re.search(r"[a-zA-Z]", v) or not re.search(r"[0-9]", v):
            raise ValueError("La contraseña debe combinar letras y números.")
        if len(set(v)) < 4:
            raise ValueError("La contraseña debe tener más variedad de caracteres diferentes.")
        return v

    @field_validator('correo')
    @classmethod
    def validar_formato_correo(cls, v: str) -> str:
        if "@" not in v or "." not in v:
            raise ValueError("El correo electrónico no es válido. ¡Revisa el formato!")
        return v

    @classmethod
    def as_form(
        cls,
        nombre: str = Form(...),
        correo: EmailStr = Form(...),
        contrasena: str = Form(...)
    ):
        return cls(nombre=nombre, correo=correo, contrasena=contrasena)

class PreguntaLandingSchema(BaseModel):
    id_pregunta: int
    materia: str 
    pregunta: str
    puntos: int = Field(..., alias="puntos_recompensa")
    opciones: List[OpcionBaseSchema]

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

# --- Esquemas para el Dashboard / Perfil ---

class DatosUsuarioSchema(BaseModel):
    id_usuario: int
    nombre: str
    correo: EmailStr
    puntaje_total: int
    nivel: int
    dias_racha: int

    model_config = ConfigDict(from_attributes=True)

class ProgresoSchema(BaseModel):
    id_pregunta: int
    correcta: bool
    fecha: datetime
    id_materia: int
    nombre_materia: str

    model_config = ConfigDict(from_attributes=True)

class LogroSchema(BaseModel):
    id_logro: int
    nombre: str
    descripcion: str
    icono: str = Field(..., alias="imagen_medalla")
    obtenido: bool = False

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

class DashboardDataSchema(BaseModel):
    usuario: DatosUsuarioSchema
    progreso: List[ProgresoSchema]
    logros: List[LogroSchema]

# --- Esquemas para Actividades (Exámenes) ---

class ActividadExamenSchema(BaseModel):
    id_examen: int
    titulo: str
    descripcion: str
    materia: str = Field(..., alias="nombre_materia")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

# --- Esquemas para Retos Semanales ---

class OpcionRetoSchema(OpcionBaseSchema):
    id_opcion: int = Field(..., alias="id_opcion_reto")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

class PreguntaRetoSchema(BaseModel):
    id_pregunta: int = Field(..., alias="id_pregunta_reto")
    pregunta: str
    puntos: int = Field(..., alias="puntos_recompensa")
    parte_cuento: int = Field(..., alias="numero_parte")
    opciones: List[OpcionRetoSchema]

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )

class RetoActivoSchema(BaseModel):
    id_reto: int
    titulo: str = Field(..., alias="titulo")

class MinijuegoRequest(BaseModel):
    id_usuario: int 
    actividad_id: int
    puntos: int = 50

class RespuestaEstudianteCompletar(BaseModel):
    id_completar_espacio: int
    respuesta_usuario: str