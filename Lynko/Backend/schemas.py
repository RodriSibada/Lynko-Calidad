from pydantic import BaseModel, EmailStr
from typing import Optional


class EstudianteBase(BaseModel):
    nombre: str
    correo: EmailStr
    contrasena: str


class EstudianteUpdate(BaseModel):
    nombre: Optional[str] = None
    correo: Optional[EmailStr] = None
    contrasena: Optional[str] = None


class Materia(BaseModel):
    id_materia: int
    nombre: str
    link_imagen: Optional[str] = None