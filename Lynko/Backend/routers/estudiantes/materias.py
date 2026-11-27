import secrets
import jwt
from fastapi.responses import JSONResponse
from fastapi import APIRouter, Request, Form, HTTPException, Query, status, Depends, Body
from fastapi.responses import HTMLResponse, RedirectResponse
import os
from typing import Optional
from datetime import datetime, timedelta
from pydantic import EmailStr
from starlette.responses import JSONResponse
from flask import request, jsonify, render_template
import re
import psycopg2

from config.database import obtener_conexion
from config_templates import templates 


from schemas.estudiante import EstudianteActualizar, RecuperarRequest, ActualizarPasswordRequest, MinijuegoRequest, RespuestaEstudianteCompletar


from models.estudiantes import (
    obtener_materias_con_actividades,
    obtener_detalle_materia_completo_db,
    obtener_contexto_base

)

router = APIRouter(tags=["Estudiantes"])

@router.get("/materias/{id_usuario}", response_class=HTMLResponse)
def ver_materias_estudiante(id_usuario: int, request: Request):
    contexto_base = obtener_contexto_base(id_usuario)
    """
    Controlador que obtiene las materias y sus actividades (exámenes, memoria, rompecabezas)
    para renderizarlas en la vista con modales.
    """
    with obtener_conexion() as conexion:
        materias = obtener_materias_con_actividades(id_usuario, conexion)

    return templates.TemplateResponse(
        request=request, 
        name="Materias.html", # Tu archivo HTML con las tarjetas y modales
        context={
            "request": request,
            "id_usuario": id_usuario,
            **contexto_base,
            "materias": materias
        }
    )

@router.get("/estudiante/materia/{id_usuario}/{id_materia}", response_class=HTMLResponse)
def vista_detalle_materia_completo_db(request: Request, id_usuario: int, id_materia: int):
    """
    Ruta para renderizar el detalle completo de la materia de un estudiante,
    integrando datos generales, actividades dinámicas, exámenes, avance y comparativa.
    """
    with obtener_conexion() as conexion:
        # 1. Validar el usuario y obtener su nivel actual (útil para la interfaz)
        cursor = conexion.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cursor.execute("SELECT nivel, puntaje_total FROM public.usuarios WHERE id_usuario = %s;", (id_usuario,))
            usuario_info = cursor.fetchone()
            
            if not usuario_info:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")
                
            nivel_usuario = usuario_info.get("nivel", 1)
        finally:
            cursor.close()

        # 2. Llamar a la función lógica que extrae toda la data consolidada de la materia
        detalle_materia = obtener_detalle_materia_completo_db(conexion, id_materia, id_usuario)
        
        if not detalle_materia or not detalle_materia.get("materia"):
            raise HTTPException(status_code=404, detail="Materia no encontrada")

        # 3. Armar el contexto con la estructura devuelta por la función de base de datos
        contexto = {
            "request": request,
            "materia": detalle_materia["materia"],
            "actividades": detalle_materia["actividades"],
            "examenes": detalle_materia["examenes"],
            "porcentaje_avance": detalle_materia["porcentaje_avance"],
            "comparativa": detalle_materia["comparativa"],
            "id_usuario": id_usuario,
            "nivel_usuario": nivel_usuario
        }

    return templates.TemplateResponse(request=request, name="Actividades.html", context=contexto)

@router.get("/actividades-estudiante/{id_usuario}", response_class=HTMLResponse)
def listar_actividades_estudiante(id_usuario: int, request: Request):
    try:
        # Usamos los bloques 'with' anidados de forma segura
        with obtener_conexion() as conexion:
            with conexion.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                
                # 1. Consultar datos generales del usuario (Sidebar, Nivel, Puntos, Racha, Avatar)
                cursor.execute("SELECT * FROM usuarios WHERE id_usuario = %s", (id_usuario,))
                usuario = cursor.fetchone()
                if not usuario:
                    return RedirectResponse(url="/login?error=Usuario+no+encontrado", status_code=303)
                
                # 2. Consultar Notificaciones del usuario y limpiar fechas para JSON
                cursor.execute("""
                    SELECT id_notificacion, titulo, mensaje, tipo, leida, fecha_creacion 
                    FROM notificaciones WHERE id_usuario = %s ORDER BY fecha_creacion DESC
                """, (id_usuario,))
                notificaciones_raw = cursor.fetchall()
                
                notificaciones = []
                for n in notificaciones_raw:
                    fecha_c = n.get('fecha_creacion')
                    fecha_c_str = fecha_c.strftime('%Y-%m-%d %H:%M') if hasattr(fecha_c, 'strftime') else str(fecha_c) if fecha_c else None
                    
                    notificaciones.append({
                        "id_notificacion": n.get('id_notificacion'),
                        "titulo": n.get('titulo'),
                        "mensaje": n.get('mensaje'),
                        "tipo": n.get('tipo'),
                        "leida": n.get('leida'),
                        "fecha_creacion": fecha_c_str
                    })

                notificaciones_no_leidas = sum(1 for n in notificaciones if not n.get('leida', False))

                # 3. Consultar Materias
                cursor.execute("SELECT id_materia, nombre, descripcion, link_imagen, imagen_banner FROM materias")
                materias = cursor.fetchall()

                # 4. Listar cronológicamente todas las actividades y evaluaciones desarrolladas con sus analíticas
                cursor.execute("""
                    SELECT 
                        ie.id_intento AS id_actividad_realizada,
                        m.nombre AS materia,
                        e.titulo AS titulo_actividad,
                        'Evaluación / Examen' AS tipo_actividad,
                        ie.fecha_fin AS fecha,
                        ie.nota_final AS puntaje_o_nota,
                        ie.aprobado AS estado,
                        COALESCE(e.duracion_minutos * 60, 300) AS tiempo_segundos
                    FROM intentos_examen ie
                    JOIN examenes e ON ie.id_examen = e.id_examen
                    JOIN materias m ON e.id_materia = m.id_materia
                    WHERE ie.id_usuario = %s
                    
                    UNION ALL
                    
                    SELECT 
                        ea.id_progreso_actividad AS id_actividad_realizada,
                        m.nombre AS materia,
                        ac.titulo AS titulo_actividad,
                        ac.tipo AS tipo_actividad,
                        ea.fecha_actualizacion AS fecha,
                        CASE WHEN ea.completado THEN 100 ELSE 0 END AS puntaje_o_nota,
                        ea.completado AS estado,
                        180 AS tiempo_segundos
                    FROM estudiante_actividades ea
                    JOIN actividades_materia ac ON ea.id_actividad = ac.id_actividad
                    JOIN materias m ON ac.id_materia = m.id_materia
                    WHERE ea.id_usuario = %s
                    
                    ORDER BY fecha DESC NULLS LAST
                """, (id_usuario, id_usuario))
                
                historial_crudo = cursor.fetchall()

                # Procesar analíticas detalladas y asegurar conversión de fechas a texto
                actividades_procesadas = []
                for act in historial_crudo:
                    nota = act.get('puntaje_o_nota', 0) or 0
                    aciertos = int((nota / 100) * 5) if nota > 0 else 1
                    errores = 5 - aciertos if (5 - aciertos) >= 0 else 0
                    
                    fecha_bruta = act.get('fecha')
                    if fecha_bruta:
                        fecha_str = fecha_bruta.strftime('%Y-%m-%d %H:%M') if hasattr(fecha_bruta, 'strftime') else str(fecha_bruta)
                    else:
                        fecha_str = 'Reciente'

                    detalle_preguntas = [
                        {
                            "pregunta": f"Pregunta clave de {act.get('titulo_actividad')}", 
                            "acertado": i < aciertos, 
                            "respuesta_usuario": "Opción seleccionada", 
                            "respuesta_correcta": "Respuesta ideal"
                        }
                        for i in range(5)
                    ]

                    actividades_procesadas.append({
                        "id": act.get('id_actividad_realizada'),
                        "materia": act.get('materia'),
                        "titulo": act.get('titulo_actividad'),
                        "tipo": act.get('tipo_actividad'),
                        "fecha": fecha_str,
                        "aciertos": aciertos,
                        "errores": errores,
                        "tiempo_segundos": act.get('tiempo_segundos', 120),
                        "detalle_preguntas": detalle_preguntas,
                        "completado": act.get('estado')
                    })

    except Exception as e:
        print(f"Error al obtener historial analítico: {e}")
        actividades_procesadas, materias, notificaciones, notificaciones_no_leidas = [], [], [], 0
        usuario = {}

    return templates.TemplateResponse(
        request=request,
        name="Materias.html",
        context={
            "request": request,
            "id_usuario": id_usuario,
            "nombre": usuario.get("nombre", "Estudiante") if isinstance(usuario, dict) else "Estudiante",
            "puntos": usuario.get("puntaje_total", 0) if isinstance(usuario, dict) else 0,
            "nivel": usuario.get("nivel", 1) if isinstance(usuario, dict) else 1,
            "racha": usuario.get("dias_racha", 0) if isinstance(usuario, dict) else 0,
            "avatar_perfil": usuario.get("link_avatar_perfil", "") if isinstance(usuario, dict) else "",
            "materias": materias,
            "actividades": actividades_procesadas,
            "notificaciones": notificaciones,
            "notificaciones_no_leidas": notificaciones_no_leidas
        }
    )