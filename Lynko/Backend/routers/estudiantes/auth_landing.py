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
    consultar_preguntas_ejemplo_landing_db,
)

router = APIRouter(tags=["Estudiantes"])

@router.get("/api/preguntas-landing", response_model=list)
def api_obtener_preguntas_landing():
    
    return consultar_preguntas_ejemplo_landing_db()

