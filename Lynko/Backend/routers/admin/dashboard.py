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
    obtener_metricas_globales_db,
    obtener_historial_examenes_db,
    obtener_todos_los_estudiantes_db,
    obtener_listado_retos_con_metricas_db,
    obtener_catalogo_preguntas_detallado_db
)

router = APIRouter(prefix="/admin", tags=["Administración"])

@router.get("", response_class=HTMLResponse)
def panel_inicio(request: Request):
    """
    Dashboard principal unificado del administrador.
    DELEGACIÓN: Llama a múltiples funciones del modelo para obtener datos crudos.
    """
    # Obtenemos datos crudos del modelo
    try:
        preguntas_raw = obtener_catalogo_preguntas_detallado_db() or []
        usuarios_raw = obtener_todos_los_estudiantes_db() or []
        metricas_materias_raw = obtener_metricas_globales_db() or []
        mejores_examenes_raw = obtener_historial_examenes_db() or []
        lista_retos_raw = obtener_listado_retos_con_metricas_db() or []
    except Exception as e:
        # Manejo de error básico si falla la BD
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {e}")

    # Lógica de presentación simple (esto podría ir en un helper o filtro Jinja)
    total_estudiantes = len(usuarios_raw)
    total_preguntas = len(preguntas_raw)
    
    # Cálculo de promedio (lógica de presentación)
    exp_totales = [u['puntaje_total'] for u in usuarios_raw if isinstance(u, dict) and 'puntaje_total' in u]
    promedio_exp = round(sum(exp_totales) / total_estudiantes, 1) if total_estudiantes > 0 else 0.0
    
    # Reordenamiento para la vista (lógica de presentación)
    ultimas_preguntas = preguntas_raw[-5:][::-1]
    
    # Ordenar mejores estudiantes (lógica de presentación)
    mejores_estudiantes = sorted(
        usuarios_raw, 
        key=lambda x: x.get('puntaje_total', 0) if isinstance(x, dict) else 0, 
        reverse=True
    )[:5]

    # Renderizamos la plantilla pasando los datos
    return templates.TemplateResponse(
        request=request,
        name="Admin.html", 
        context={
            "request": request,
            "total_estudiantes": total_estudiantes,
            "total_preguntas": total_preguntas,
            "promedio_exp": promedio_exp,
            "ultimas_preguntas": ultimas_preguntas,
            "mejores_estudiantes": mejores_estudiantes,
            "retos": lista_retos_raw,
            "metricas_retos": [] # Ajustar si se usa una tabla separada en la vista
        }
    )

@router.get("", response_class=HTMLResponse)
def panel_admin(request: Request, msg: Optional[str] = None):
    conn = obtener_conexion()
    preguntas, usuarios, metricas_materias, mejores_examenes = [], [], [], []
    
    if conn:
        try:
            with conn.cursor() as cursor:
                # 1. Métricas de efectividad por materia
                cursor.execute("""
                    SELECT m.nombre, COUNT(i.id_intento), COALESCE(ROUND(AVG(i.nota_final), 1), 0), COUNT(CASE WHEN i.aprobado THEN 1 END)
                    FROM materias m LEFT JOIN examenes e ON m.id_materia = e.id_materia
                    LEFT JOIN intentos_examen i ON e.id_examen = i.id_examen GROUP BY m.nombre;
                """)
                metricas_materias = cursor.fetchall() or []
                
                # 2. Historial de mejores exámenes rendidos
                cursor.execute("""
                    SELECT u.nombre, e.titulo, m.nombre, i.nota_final FROM intentos_examen i
                    JOIN usuarios u ON i.id_usuario = u.id_usuario JOIN examenes e ON i.id_examen = e.id_examen
                    JOIN materias m ON e.id_materia = m.id_materia ORDER BY i.nota_final DESC;
                """)
                mejores_examenes = cursor.fetchall() or []

                # 3. Listado completo de preguntas del sistema
                cursor.execute("SELECT p.id_pregunta, p.pregunta, m.nombre, p.nivel_dificultad FROM preguntas p JOIN materias m ON p.id_materia = m.id_materia ORDER BY p.id_pregunta ASC;")
                preguntas = cursor.fetchall() or []

                # 4. Listado de estudiantes y suma de sus logros obtenidos
                cursor.execute("""
                    SELECT u.id_usuario, u.nombre, u.correo, u.puntaje_total, COUNT(lu.id_logro) FROM usuarios u
                    LEFT JOIN logros_usuario lu ON u.id_usuario = lu.id_usuario WHERE u.rol = 'estudiante' 
                    GROUP BY u.id_usuario, u.nombre, u.correo, u.puntaje_total
                    ORDER BY u.puntaje_total ASC;
                """)
                usuarios = cursor.fetchall() or []
        except Exception as e:
            print(f"⚠️ Error en consultas del Panel Admin: {e}")
        finally:
            conn.close()

    if not metricas_materias:
        metricas_materias = [("Matemáticas", 0, 0, 0), ("Español", 0, 0, 0), ("Biología", 0, 0, 0)]

    return templates.TemplateResponse(request=request, name="Admin.html", context={
        "preguntas": preguntas, "usuarios": usuarios,
        "metricas_materias": metricas_materias, "mejores_examenes": mejores_examenes, "msg": msg
    })
