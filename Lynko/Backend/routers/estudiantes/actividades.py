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
    completar_actividad_db
)

router = APIRouter(tags=["Estudiantes"])



@router.post("/completar-actividad/{id_usuario}/{actividad_id}")
async def completar_actividad(
    id_usuario: int,      # Viene de la URL
    actividad_id: int,    # Viene de la URL
    request: Request      # Para capturar los puntos si los envías por JSON/Form
):
    try:
        # 1. Obtenemos los puntos (por defecto 20 si no se envían en el body)
        puntos = 20
        try:
            body = await request.json()
            if isinstance(body, dict) and "puntos" in body:
                puntos = int(body["puntos"])
        except Exception:
            try:
                form_data = await request.form()
                if "puntos" in form_data:
                    puntos = int(form_data.get("puntos"))
            except Exception:
                pass

        # 2. Usamos tu gestor de contexto 'with' para manejar la conexión de forma limpia
        with obtener_conexion() as conexion:
            # 3. Llamamos a tu función pasándole los 4 argumentos requeridos
            exito, mensaje = completar_actividad_db(id_usuario, actividad_id, puntos, conexion)
            
            if not exito:
                return JSONResponse(
                    status_code=400, 
                    content={"status": "error", "mensaje": mensaje}
                )
                
        return {"status": "success", "mensaje": mensaje}
        
    except Exception as e:
        return JSONResponse(
            status_code=500, 
            content={"status": "error", "mensaje": str(e)}
        )

# ==========================================
# 1. RUTA PARA CARGAR EL JUEGO (O el modal)
# ==========================================
@router.get('/juego-memoria/{id_usuario}/{actividad_id}')
def cargar_juego_memoria(id_usuario: int, actividad_id: int):
    elementos = []
    
    # Usamos la conexión para traer los datos incluyendo el dato_curioso
    with obtener_conexion() as conexion:
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT id, titulo_elemento, imagen_url, dato_curioso FROM contenido_minijuego WHERE actividad_id = %s", 
            (actividad_id,)
        )
        resultados = cursor.fetchall()
        
        for fila in resultados:
            elementos.append({
                "id": fila[0],
                "titulo": fila[1],
                "imagen": fila[2],
                "dato_curioso": fila[3]  
            })
        cursor.close()
        
    # Renderizamos la plantilla pasando la lista 'elementos'
    return templates.TemplateResponse("tu_vista.html", {
        "request": request, 
        "id_usuario": id_usuario, 
        "elementos": elementos, 
        "actividad_id": actividad_id
    })

@router.get('/actividades/completar-espacio/{id_actividad}')
def obtener_ejercicios_completar_espacio(id_actividad: int, 
    id_usuario: int = Query(default=0)):
    ejercicios = []
    ya_completada = False
    puntos_recompensa = 20

    with obtener_conexion() as conexion:
        cursor = conexion.cursor()
        
        # 1. Verificar la actividad y obtener sus puntos
        cursor.execute(
            """
            SELECT puntos_recompensa 
            FROM public.actividades_materia 
            WHERE id_actividad = %s AND tipo = 'completar_espacio'
            """, 
            (id_actividad,)
        )
        actividad = cursor.fetchone()
        
        if not actividad:
            cursor.close()
            # Retornar una respuesta JSON 404 clara directamente
            return JSONResponse(
                status_code=404,
                content={"error": f"La actividad {id_actividad} no existe o no es de tipo 'completar_espacio'.", "ejercicios": []}
            )
        
        puntos_recompensa = actividad[0]

        # 2. Consultar si el estudiante ya completó la actividad
        if id_usuario > 0:
            cursor.execute(
                """
                SELECT completado 
                FROM public.estudiante_actividades 
                WHERE id_usuario = %s AND id_actividad = %s
                """, 
                (id_usuario, id_actividad)
            )
            progreso = cursor.fetchone()
            if progreso:
                ya_completada = progreso[0]

        # 3. Obtener los ejercicios asociados
        cursor.execute(
            """
            SELECT id_completar_espacio, frase, imagen_url 
            FROM public.completar_espacio_actividad 
            WHERE id_actividad = %s
            """, 
            (id_actividad,)
        )
        resultados = cursor.fetchall()
        
        for fila in resultados:
            ejercicios.append({
                "id_completar_espacio": fila[0],
                "frase": fila[1],
                "imagen_url": fila[2],
                "resuelto": False
            })
            
        cursor.close()

    return {
        "ya_completada": ya_completada,
        "puntos_recompensa": puntos_recompensa,
        "ejercicios": ejercicios
    }

# ==========================================
# 2. RUTA PARA COMPLETAR LA ACTIVIDAD Y SUMAR PUNTOS (POST)
# ==========================================
@router.post('/completar-minijuego')
async def completar_minijuego(data: dict = Body(...)):
    id_usuario = data.get("id_usuario")
    actividad_id = data.get("actividad_id")
    puntos = data.get("puntos", 50)
    
    if not id_usuario or not actividad_id:
        return JSONResponse(status_code=400, content={"status": "error", "mensaje": "Faltan datos obligatorios (id_usuario o actividad_id)"})
    
    try:
        with obtener_conexion() as conexion:
            exito, mensaje = completar_actividad_db(id_usuario, actividad_id, puntos, conexion)
            
            if not exito:
                return JSONResponse(status_code=400, content={"status": "error", "mensaje": mensaje})
                
        return {"status": "success", "mensaje": "¡Minijuego completado con éxito! Puntos y logros actualizados."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "mensaje": str(e)})
    
@router.post('/actividades/completar-espacio/evaluar')
def evaluar_respuesta_completar_espacio(datos: RespuestaEstudianteCompletar):
    es_correcta = False
    
    with obtener_conexion() as conexion:
        cursor = conexion.cursor()
        
        cursor.execute(
            """
            SELECT palabra_faltante 
            FROM public.completar_espacio_actividad 
            WHERE id_completar_espacio = %s
            """, 
            (datos.id_completar_espacio,)
        )
        registro = cursor.fetchone()
        cursor.close()
        
        if not registro:
            raise HTTPException(status_code=404, detail="Ejercicio no encontrado")

        palabra_correcta = registro[0].strip().lower()
        respuesta_estudiante = datos.respuesta_usuario.strip().lower()

        es_correcta = (palabra_correcta == respuesta_estudiante)

    if es_correcta:
        mensaje = "¡Excelente! La palabra es correcta. 🎉"
    else:
        mensaje = "Respuesta incorrecta. ¡Sigue intentándolo! 💪"

    return {
        "es_correcta": es_correcta,
        "mensaje": mensaje
    }
    