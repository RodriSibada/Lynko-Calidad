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
    obtener_reto_semanal_activo_db,
    obtener_contexto_base,
    guardar_intento_reto_db,
    verificar_y_guardar_respuesta_reto_db,
    finalizar_intento_reto_db

)

router = APIRouter(tags=["Estudiantes"])

@router.get("/progreso-estudiante/{id_usuario}", response_class=HTMLResponse)
def vista_reto_semanal(id_usuario: int, request: Request):

    contexto_base = obtener_contexto_base(id_usuario)
    
    reto_raw, preguntas_raw = obtener_reto_semanal_activo_db(id_usuario)
    
    reto_formateado = None
    if reto_raw:
        reto_formateado = {
            "id_reto": reto_raw['id_reto'],
            "titulo": reto_raw['titulo_general'], 
            "descripcion": reto_raw['descripcion'],
            "puntos_recompensa_max": reto_raw['puntos_recompensa_total'],
            "completado": bool(reto_raw.get('ya_completado')),
            "link_audio": reto_raw['link_audio'],
            "preguntas": preguntas_raw 
        }

    contexto = {
        "request": request,
        "id_usuario": id_usuario,
        **contexto_base,
        "reto": reto_formateado,
        "mensaje": "¡Ya has completado el reto de esta semana!" if (reto_formateado and reto_formateado['completado']) else ""
    }

    return templates.TemplateResponse(
        request=request, 
        name="Reto_semanal.html", 
        context=contexto
    )

@router.post("/api/retos/{id_reto}/iniciar")
def api_iniciar_intento_reto(id_reto: int, id_usuario: int = Query(...)):

    try:
        id_intento = guardar_intento_reto_db(id_usuario, id_reto)
        return {"status": "success", "id_intento": id_intento}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/api/retos/respuesta")
def api_guardar_respuesta_reto(
    id_intento: int = Form(...),
    id_pregunta: int = Form(...),
    id_opcion: int = Form(...),
    id_usuario: int = Form(...)
):
    
    try:
        es_correcta, puntos = verificar_y_guardar_respuesta_reto_db(id_usuario, id_intento, id_pregunta, id_opcion)
        return {"status": "success", "es_correcta": es_correcta, "puntos": puntos}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/api/retos/{id_intento}/finalizar")
def api_finalizar_intento_reto(
    id_intento: int,
    data: dict = Body(...),
    id_usuario: int = Query(...) 
):
    
    try:
        puntaje = data.get("puntaje_total", 0)
        usuario_id = data.get("id_usuario")
        finalizar_intento_reto_db(id_intento, puntaje, usuario_id)
        return {"status": "success", "message": "Reto finalizado"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))