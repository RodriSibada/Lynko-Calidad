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
    
    obtener_todos_los_estudiantes_db,
)

router = APIRouter(prefix="/admin", tags=["Administración"])

@router.get("/estudiantes", response_class=HTMLResponse)
def lista_estudiantes(request: Request, q: Optional[str] = Query(None)):
    """Renderiza lista de estudiantes con opción de búsqueda."""
    try:
        # Obtenemos los datos crudos de la base de datos
        datos_raw = obtener_todos_los_estudiantes_db() or []
        
        # 🛠️ Convertimos las tuplas a diccionarios seguros para que .get() funcione
        lista_usuarios_raw = []
        for u in datos_raw:
            if isinstance(u, tuple):
                lista_usuarios_raw.append({
                    "id_usuario": u[0],
                    "nombre": u[1] if len(u) > 1 else "",
                    "correo": u[2] if len(u) > 2 else "",
                    "puntaje_total": u[3] if len(u) > 3 else 0,
                    "nivel": u[4] if len(u) > 4 else 1,
                    "dias_racha": u[5] if len(u) > 5 else 0
                })
            else:
                lista_usuarios_raw.append(u)
                
    except Exception as e:
        print(f"Error al obtener estudiantes: {e}")
        lista_usuarios_raw = []
    
    # Filtrado simple en el controlador
    if q and q.strip():
        q_lower = q.strip().lower()
        if q_lower.isdigit():
            lista_usuarios_raw = [
                u for u in lista_usuarios_raw 
                if q_lower in str(u.get('id_usuario', '')) or q_lower in str(u.get('puntaje_total', ''))
            ]
        else:
            lista_usuarios_raw = [
                u for u in lista_usuarios_raw 
                if q_lower in str(u.get('nombre', '')).lower() or q_lower in str(u.get('correo', '')).lower()
            ]
    
    # 🏆 Ordenar de mayor a menor puntaje (puntaje_total)
    lista_usuarios_raw.sort(
        key=lambda x: x.get('puntaje_total', 0) if isinstance(x, dict) else 0, 
        reverse=True
    )
    
   
    return templates.TemplateResponse(
        request=request, 
        name="Ver-estudiantes.html", 
        context={
            "request": request, 
            "usuarios": lista_usuarios_raw, 
            "query_busqueda": q
        }
    )

@router.post("/estudiantes/editar")
def editar_estudiante(
    id_usuario: int = Form(...),       
    nombre: str = Form(...),          
    correo: str = Form(...),          
    puntaje_total: int = Form(...)    
):
    try:
        with obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                query = """
                    UPDATE usuarios 
                    SET nombre = %s, correo = %s, puntaje_total = %s 
                    WHERE id_usuario = %s AND rol = 'estudiante';
                """
                cursor.execute(query, (nombre, correo, puntaje_total, id_usuario))
                conexion.commit()
                
        return RedirectResponse(url="/admin/estudiantes?msg=Estudiante+actualizado+correctamente", status_code=303)

    except Exception as e:
        print(f"⚠️ Error al actualizar el estudiante {id_usuario}: {e}")
        return RedirectResponse(url="/admin/estudiantes?error=No+se+pudo+actualizar", status_code=303)

@router.post("/estudiantes/eliminar/{id_usuario}")
def dar_baja_estudiante(id_usuario: int):
    msg = ""
    try:
        # Usamos el context manager 'with' correctamente
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM usuarios WHERE id_usuario = %s AND rol = 'estudiante';", 
                    (id_usuario,)
                )
                conn.commit()
        msg = "Estudiante eliminado correctamente"
    except Exception as e:
        print(f"⚠️ Error al eliminar al usuario {id_usuario}: {e}")
        msg = "No se pudo eliminar al estudiante (verifique dependencias)"
        
    return RedirectResponse(url=f"/admin?msg={msg}", status_code=303)

@router.get("/estudiantes/ver/{id_usuario}", response_class=HTMLResponse)
def ver_estudiante(request: Request, id_usuario: int):
    """Renderiza el expediente completo, historial de actividades y logros del estudiante."""
    estudiante = {"nombre": "Desconocido", "correo": "", "puntos": 0}
    respuestas = []
    logros = []
    
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                # 1. Datos básicos del estudiante
                cursor.execute(
                    "SELECT id_usuario, nombre, correo, puntaje_total, nivel, dias_racha, fecha_registro FROM usuarios WHERE id_usuario = %s;", 
                    (id_usuario,)
                )
                estudiante_raw = cursor.fetchone()
                
                if not estudiante_raw:
                    raise HTTPException(status_code=404, detail="El estudiante no fue encontrado.")
                
                # Mapeo directo (asumiendo que fetchone() devuelve un diccionario o tupla estándar)
                # Si usas tuplas por índice:
                estudiante = {
                    "id_usuario": estudiante_raw[0],
                    "nombre": estudiante_raw[1],
                    "correo": estudiante_raw[2],
                    "puntaje_total": estudiante_raw[3],
                    "puntos": estudiante_raw[3],
                    "nivel": estudiante_raw[4],
                    "racha": estudiante_raw[5],
                }

                # 2. Historial de actividades con JOIN en base de datos
                cursor.execute("""
                    SELECT e.titulo, ie.nota_final, ie.aprobado, ie.fecha_fin 
                    FROM intentos_examen ie 
                    JOIN examenes e ON ie.id_examen = e.id_examen 
                    WHERE ie.id_usuario = %s 
                    ORDER BY ie.fecha_fin DESC;
                """, (id_usuario,))
                
                for row in cursor.fetchall():
                    respuestas.append({
                        "materia": row[0],  # Título o nombre del examen
                        "pregunta": f"Nota: {row[1]} pts",  # Muestra la nota final obtenida
                        "correcta": row[2],  # Booleano (aprobado o no)
                        "fecha": row[3]      # Fecha de finalización del examen
                    })

                # 3. Logros y medallas con JOIN en base de datos
                cursor.execute("""
                    SELECT l.nombre, l.descripcion, l.imagen_medalla, lu.fecha_desbloqueo 
                    FROM logros_usuario lu 
                    JOIN logros l ON lu.id_logro = l.id_logro 
                    WHERE lu.id_usuario = %s 
                    ORDER BY lu.fecha_desbloqueo DESC;
                """, (id_usuario,))
                
                for row in cursor.fetchall():
                    logros.append({
                        "nombre": row[0],
                        "descripcion": row[1],
                        "icono": row[2],  # Mapea directamente a l.icono en tu HTML
                        "fecha": row[3]   # Mapea directamente a l.fecha en tu HTML
                    })

    except Exception as e:
        print(f"⚠️ Error al cargar el perfil del estudiante: {e}")

    # 4. Renderizar vista pasando las variables requeridas
    return templates.TemplateResponse(
        request=request, 
        name="admin-ver-mas.html", 
        context={
            "request": request, 
            "estudiante": estudiante,
            "respuestas": respuestas,
            "logros": logros
        }
    )