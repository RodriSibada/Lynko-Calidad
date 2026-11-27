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
    crear_actividad_y_notificar_db,
    obtener_estudiante_por_id_db,
    obtener_metricas_globales_db,
    obtener_historial_examenes_db,
    obtener_todos_los_estudiantes_db,
    obtener_ranking_top_10_db,
    obtener_listado_retos_con_metricas_db,
    obtener_catalogo_preguntas_detallado_db,
    obtener_listado_retos_con_estadisticas_db,
    crear_nueva_pregunta_completa_db,
    crear_nuevo_reto_completo_db,
    insertar_pregunta_reto_db,
    eliminar_fila_db,
    editar_datos_estudiante_db,
    obtener_historial_estudiante_db,
    obtener_logros_estudiante_db
)

router = APIRouter(prefix="/admin", tags=["Administración"])

@router.get("/materias-actividades", response_class=HTMLResponse)
def vista_admin_materias_actividades(request: Request):
    try:
        with obtener_conexion() as conexion:
            with conexion.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute("SELECT id_materia, nombre, descripcion, icono, link_imagen, imagen_banner FROM public.materias ORDER BY id_materia ASC;")
                materias = cursor.fetchall() or []
    except Exception as e:
        print(f"⚠️ Error al obtener materias: {e}")
        materias = []
        
    return templates.TemplateResponse(
        request=request,
        name="admin-preguntas.html", # O el nombre exacto de tu plantilla HTML
        context={
            "request": request, 
            "materias": materias  # Ahora cada materia es un diccionario con nombre, descripcion, etc.
        }
    )

@router.post("/nuevas-preguntas")
def crear_pregunta(
    pregunta: str = Form(...), 
    id_materia: int = Form(...), 
    nivel: int = Form(...), 
    puntos: int = Form(...), 
    opcion1: str = Form(...), 
    opcion2: str = Form(...), 
    opcion3: str = Form(...), 
    correcta: str = Form(...)  
):
    conn = obtener_conexion()
    msg = ""
    if conn:
        try:
            # Forzamos la conversión a entero de forma segura
            opcion_correcta_int = int(correcta)
            
            with conn.cursor() as cursor:
                # 1. Insertamos la pregunta principal
                cursor.execute("""
                    INSERT INTO preguntas (id_materia, pregunta, nivel_dificultad, puntos_recompensa) 
                    VALUES (%s, %s, %s, %s) 
                    RETURNING id_pregunta;
                """, (id_materia, pregunta, nivel, puntos))
                
                id_p = cursor.fetchone()[0]
                
                # 2. Insertamos las opciones comparando de forma estricta con el entero convertido
                cursor.execute("INSERT INTO opciones (id_pregunta, opcion, es_correcta) VALUES (%s, %s, %s);", 
                               (id_p, opcion1, True if opcion_correcta_int == 1 else False))
                               
                cursor.execute("INSERT INTO opciones (id_pregunta, opcion, es_correcta) VALUES (%s, %s, %s);", 
                               (id_p, opcion2, True if opcion_correcta_int == 2 else False))
                               
                cursor.execute("INSERT INTO opciones (id_pregunta, opcion, es_correcta) VALUES (%s, %s, %s);", 
                               (id_p, opcion3, True if opcion_correcta_int == 3 else False))
                
                # 3. Confirmamos los cambios de manera persistente en PostgreSQL
                conn.commit()
                msg = "Pregunta añadida correctamente al banco"
                print("✅ [ÉXITO] Pregunta y opciones guardadas correctamente en la base de datos.")
                
        except Exception as e:
            if conn:
                conn.rollback()  
            print(f"❌ [ERROR CRÍTICO EN BD]: {e}")
            msg = "Error interno al guardar la pregunta"
        finally:
            conn.close()
    else:
        print("❌ [ERROR DE CONEXIÓN]: No se pudo conectar a PostgreSQL.")
        msg = "Error de conexión con el servidor"
            
    return RedirectResponse(url=f"/admin?msg={msg}", status_code=303)


@router.get("/preguntas", response_class=HTMLResponse)
def vista_admin_preguntas(request: Request):
    conn = obtener_conexion()
    lista_preguntas = []
    
    if conn:
        try:
            with conn.cursor() as cursor:
                
                cursor.execute("""
                    SELECT p.id_pregunta, m.nombre AS materia, p.pregunta, p.nivel_dificultad, p.puntos_recompensa,
                           json_agg(json_build_object('opcion', o.opcion, 'es_correcta', o.es_correcta)) AS opciones
                    FROM preguntas p
                    JOIN materias m ON p.id_materia = m.id_materia
                    LEFT JOIN opciones o ON p.id_pregunta = o.id_pregunta
                    GROUP BY p.id_pregunta, m.nombre
                    ORDER BY p.id_pregunta DESC;
                """)
                for row in cursor.fetchall():
                    lista_preguntas.append({
                        "id_pregunta": row[0],
                        "materia": row[1],
                        "pregunta": row[2],
                        "nivel": row[3],
                        "puntos": row[4],
                        "opciones": row[5]  
                    })
        except Exception as e:
            print(f"⚠️ Error al listar preguntas y respuestas para el administrador: {e}")
        finally:
            conn.close()

    return templates.TemplateResponse(
        request=request,
        name="admin-preguntas.html",
        context={"preguntas": lista_preguntas}
    )



@router.get("/preguntas/borrar/{id_pregunta}")
def borrar_pregunta(id_pregunta: int):
    conn = obtener_conexion()
    msg = ""
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM preguntas WHERE id_pregunta = %s;", (id_pregunta,))
                conn.commit()
            msg = "Pregunta eliminada del sistema"
        except Exception as e:
            print(f"⚠️ Error al eliminar la pregunta {id_pregunta}: {e}")
            msg = "No se pudo eliminar la pregunta"
        finally:
            conn.close()
    return RedirectResponse(url=f"/admin?msg={msg}", status_code=303)

