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
    obtener_notificaciones_usuario_db,
    marcar_notificacion_como_leida_db,
)

router = APIRouter(tags=["Estudiantes"])

@router.get("/api/notificaciones/{id_usuario}")
def obtener_notificaciones_ruta(id_usuario: int):
    """
    Ruta para obtener el historial de notificaciones en formato JSON 
    para pintarlas de forma dinámica en el modal.
    """
    with obtener_conexion() as conexion:
        if not conexion:
            raise HTTPException(status_code=500, detail="Error de conexión con la base de datos.")
        try:
            notificaciones = obtener_notificaciones_usuario_db(conexion, id_usuario)
            return {"status": "success", "notificaciones": notificaciones}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

@router.post("/api/notificaciones/marcar-leida/{id_notificacion}/{id_usuario}")
def marcar_leida_ruta(id_notificacion: int, id_usuario: int):
    """
    Ruta para actualizar el estado de una notificación específica a leída.
    """
    with obtener_conexion() as conexion:
        if not conexion:
            raise HTTPException(status_code=500, detail="Error de conexión con la base de datos.")
        try:
            marcar_notificacion_como_leida_db(conexion, id_notificacion, id_usuario)
            return {"status": "success", "mensaje": "Notificación marcada como leída"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))