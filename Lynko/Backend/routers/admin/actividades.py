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

@router.post("/crear-actividad")
async def crear_actividad_admin(
    id_materia: int = Form(...),
    titulo: str = Form(...),
    descripcion: Optional[str] = Form(None),
    tipo: str = Form(...), # 'memorama', 'completar_espacio', 'baile'
    puntos_recompensa: int = Form(20),
    dato_curioso: Optional[str] = Form(None),
    imagen_url: Optional[str] = Form(None),
    frase: Optional[str] = Form(None),
    palabra_faltante: Optional[str] = Form(None),
    video_url: Optional[str] = Form(None),
    instrucciones_movimiento: Optional[str] = Form(None),
):
    try:
        with obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                # 1. Insertar en la tabla matriz 'actividades_materia'
                query_actividad = """
                    INSERT INTO public.actividades_materia (id_materia, titulo, descripcion, tipo, puntos_recompensa)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id_actividad;
                """
                cursor.execute(query_actividad, (id_materia, titulo, descripcion, tipo, puntos_recompensa))
                id_actividad = cursor.fetchone()[0]

                # 2. Insertar en la tabla específica según el tipo de actividad
                if tipo == 'memorama':
                    query_sub = """
                        INSERT INTO public.contenido_minijuego (actividad_id, titulo_elemento, imagen_url, dato_curioso)
                        VALUES (%s, %s, %s, %s);
                    """
                    cursor.execute(query_sub, (id_actividad, titulo, imagen_url, dato_curioso))
                    
                elif tipo == 'completar_espacio':
                    query_sub = """
                        INSERT INTO public.completar_espacio_actividad (id_actividad, frase, imagen_url, palabra_faltante)
                        VALUES (%s, %s, %s, %s);
                    """
                    cursor.execute(query_sub, (id_actividad, frase, imagen_url, palabra_faltante))
                    
                elif tipo == 'baile':
                    query_sub = """
                        INSERT INTO public.rutinas_baile (id_actividad, video_url, instrucciones_movimiento)
                        VALUES (%s, %s, %s);
                    """
                    cursor.execute(query_sub, (id_actividad, video_url, instrucciones_movimiento))

                # 3. Consultar a TODOS los usuarios con rol 'estudiante'
                cursor.execute("SELECT id_usuario FROM public.usuarios WHERE rol = 'estudiante';")
                estudiantes = cursor.fetchall()

                titulo_notif = f"¡Nueva actividad disponible: {titulo}!"
                mensaje_notif = f"Se ha agregado un nuevo reto de tipo {tipo}. ¡Entra a resolverlo y gana puntos!"

                # 4. Insertar la notificación masiva usando tu lógica de base de datos
                for estudiante in estudiantes:
                    id_estudiante = estudiante[0]
                    # Asegúrate de tener disponible tu función registrar_notificacion_db(conexion, id_estudiante, ...)
                    # registrar_notificacion_db(conexion, id_estudiante, titulo_notif, mensaje_notif, tipo='actividad')
                    
                    cursor.execute("""
                        INSERT INTO public.notificaciones (id_usuario, titulo, mensaje, tipo)
                        VALUES (%s, %s, %s, 'actividad');
                    """, (id_estudiante, titulo_notif, mensaje_notif))

                conexion.commit()
                return {"success": True, "mensaje": "¡Actividad creada y notificaciones enviadas a todos los estudiantes con éxito!"}

    except Exception as e:
        print(f"Error crítico al crear actividad: {e}")
        raise HTTPException(status_code=500, detail=str(e))