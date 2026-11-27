import psycopg2

from config.database import obtener_conexion
import traceback
import os
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Request, Form, HTTPException, status, UploadFile, File, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

# --- Importaciones de la nueva estructura modular ---
# 1. Instancia global de Jinja2Templates
from config_templates import templates 

# 2. Esquemas de validación (DTOs) - Se asume que existen en app/schemas/admin.py
# IMPORTANTE: Se asume que EstudianteAdminSchema tiene el método estático .as_form()
from schemas.admin import PreguntaCreateSchema, EstudianteAdminSchema,PreguntaRetoCreate,OpcionSchema

# 3. Capa de Modelo (Funciones puras de acceso a datos) - Se asume que existen en app/models/admin.py
from models.admin import (
    insertar_pregunta_reto_db,
    
)

router = APIRouter(prefix="/admin", tags=["Administración"])

@router.get("/Panel_examenes", response_class=HTMLResponse)
def ver_gestion_examenes(request: Request):
    try:
        with obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                # CONSULTA : Usando tabla 'examenes' y columna 'id_examen'
                cursor.execute("SELECT id_examen, id_materia, titulo, descripcion, duracion_minutos, puntaje_minimo_aprobatorio, fecha_creacion FROM examenes ORDER BY id_examen DESC;")
                retos = cursor.fetchall()
        
        return templates.TemplateResponse("admin_examenes.html", {
            "request": request,
            "retos": retos
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener exámenes: {e}")

@router.post("/crear_examen")
def crear_examen(
    titulo: str = Form(...),
    descripcion: str = Form(...),
    duracion: int = Form(...), 
):
    try:
        
        ID_MATERIA_DEFECTO = 1 
        PUNTAJE_MINIMO_DEFECTO = 60
        
        with obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                
                sql = """
                    INSERT INTO examenes 
                    (id_materia, titulo, descripcion, duracion_minutos, puntaje_minimo_aprobatorio)
                    VALUES (%s, %s, %s, %s, %s) RETURNING id_examen;
                """
                                
                valores = (ID_MATERIA_DEFECTO, titulo, descripcion, duracion, PUNTAJE_MINIMO_DEFECTO)
                
                cursor.execute(sql, valores)
                
                
                resultado = cursor.fetchone()
                if resultado:
                    nuevo_id = resultado[0]
                    
                    return RedirectResponse(url="/admin/Panel_examenes", status_code=303)
                else:
                    raise HTTPException(status_code=500, detail="No se pudo obtener el ID del examen creado.")

    except Exception as e:
        
        if 'conexion' in locals() and conexion:
            conexion.rollback()
        raise HTTPException(status_code=500, detail=f"Error al crear examen: {e}")


@router.post("/admin/retos/{id_examen}/preguntas/crear")
async def crear_pregunta_para_examen(
    id_examen: int, 
    pregunta: str = Form(...),
    opcion1: str = Form(...),
    opcion2: str = Form(...),
    opcion3: str = Form(...),
    correcta: str = Form(...), 
    puntos_recompensa: int = Form(10)
):
    # Lógica para crear la lista de opciones
    opciones_list = [
        {"opcion": opcion1, "es_correcta": (correcta == "1")},
        {"opcion": opcion2, "es_correcta": (correcta == "2")},
        {"opcion": opcion3, "es_correcta": (correcta == "3")}
    ]
    
    with obtener_conexion() as conexion:
        exito, mensaje = insertar_pregunta_reto_db(
            id_examen=id_examen, 
            pregunta=pregunta, 
            puntos=puntos_recompensa, 
            opciones_list=opciones_list, 
            conexion_db=conexion
        )
    
    if exito:
        return RedirectResponse(url="/admin/Panel_examenes", status_code=303)
    else:
        raise HTTPException(status_code=500, detail=mensaje)