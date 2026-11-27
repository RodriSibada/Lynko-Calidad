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
    consultar_dashboard_estudiante_db,
    actualizar_perfil_estudiante_db,
    consultar_preguntas_ejemplo_landing_db,
    obtener_todos_logros_con_estado_db,
    obtener_reto_semanal_activo_db,
    obtener_contexto_base,
    guardar_intento_reto_db,
    verificar_y_guardar_respuesta_reto_db,
    finalizar_intento_reto_db,
    obtener_todos_los_avatares_db,
    actualizar_avatar_estudiante_db,
    buscar_usuario_por_correo_db,
    guardar_token_recuperacion_db,
    validar_y_obtener_por_token_db,
    actualizar_contrasena_db,
    calificar_y_guardar_examen_db,
    obtener_examen_para_estudiante_db,
    obtener_catalogo_examenes_estudiante_db,
    obtener_materias_con_actividades,
    completar_actividad_db,
    consultar_elementos_minijuego,
    registrar_notificacion_db,
    obtener_notificaciones_usuario_db,
    marcar_notificacion_como_leida_db,
    obtener_ejercicios_por_actividad,
    evaluar_respuesta_completar_db,
    obtener_detalle_materia_completo_db,
    consultar_dashboard_estudiante_db

)

router = APIRouter(tags=["Estudiantes"])

@router.post("/examen/{id_examen}/enviar")
async def enviar_respuestas_examen(request: Request, id_examen: int):
    try:
        form_data = await request.form()
        id_usuario_str = form_data.get("id_usuario")
        
        if not id_usuario_str:
            return JSONResponse(status_code=400, content={"error": "Falta id_usuario en el formulario"})
        
        id_usuario = int(id_usuario_str)
        
        # Procesar dinámicamente las respuestas del formulario de forma segura
        respuestas_usuario = {}
        for key, value in form_data.items():
            if key.startswith("pregunta"):
                if value and str(value).strip():
                    try:
                        numeros = re.findall(r'\d+', key)
                        if numeros:
                            id_pregunta = int(numeros[0])
                            respuestas_usuario[id_pregunta] = int(value)
                    except ValueError:
                        continue

        # Ejecutar la lógica conectando a la base de datos
        with obtener_conexion() as conexion:
            resultado = calificar_y_guardar_examen_db(id_usuario, id_examen, respuestas_usuario, conexion)
            return JSONResponse(status_code=200, content=resultado)

    except Exception as e:
        print(f"Error crítico en examen: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

    
@router.get("/resolver-examen/{id_materia}/{id_examen}/{id_usuario}", response_class=HTMLResponse)
def vista_resolver_examen_individual(id_materia: int, id_examen: int, request: Request, id_usuario: int):
    datos_base = obtener_contexto_base(id_usuario)
    
    with obtener_conexion() as conexion:
        examen = obtener_examen_para_estudiante_db(id_examen, conexion)
        if not examen:
            raise HTTPException(status_code=404, detail="Examen no encontrado")
            
        return templates.TemplateResponse(
            request=request, 
            name="Actividades.html", 
            context={
                "request": request, 
                "id_usuario": id_usuario, 
                **datos_base, 
                "examen": examen
            }
        )