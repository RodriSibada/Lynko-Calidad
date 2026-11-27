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
    obtener_todos_logros_con_estado_db,
    obtener_contexto_base,
    obtener_todos_los_avatares_db,
    actualizar_avatar_estudiante_db,
    consultar_dashboard_estudiante_db

)

router = APIRouter(tags=["Estudiantes"])

@router.get("/inicio-estudiante/{id_usuario}", response_class=HTMLResponse)
def dashboard_estudiante_principal(id_usuario: int, request: Request):
    print(f"🟢 1. Entró a la ruta /inicio-estudiante/ con ID: {id_usuario}")
    contexto_base = obtener_contexto_base(id_usuario)

    # Conexión directa para traer al usuario y sus datos de nivel y puntaje
    datos_usuario = None
    actividades_lista = []
    
    with obtener_conexion() as conexion:
        with conexion.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            # 1. Consultar datos del usuario
            cursor.execute("SELECT id_usuario, nombre, correo, puntaje_total, nivel, dias_racha FROM usuarios WHERE id_usuario = %s;", (id_usuario,))
            datos_usuario = cursor.fetchone()

            if datos_usuario:
                nivel_usuario = datos_usuario.get("nivel", 1)
                
                # 2. Consultar SOLO las actividades/exámenes que correspondan al nivel del estudiante
                # Cambia 'examenes' por el nombre de tu tabla de actividades si es diferente.
                # Si quieres que vea su nivel y los anteriores, usa: WHERE nivel <= %s
                cursor.execute(
                    "SELECT id_examen, titulo, descripcion, puntaje_minimo_aprobatorio FROM examenes WHERE nivel = %s;",
                    (nivel_usuario,)
                )
                actividades_raw = cursor.fetchall()
                
                # Transformar a lista de diccionarios para la plantilla
                for act in actividades_raw:
                    actividades_lista.append({
                        "id_examen": act.get("id_examen"),
                        "titulo": act.get("titulo"),
                        "descripcion": act.get("descripcion"),
                        "puntaje_minimo": act.get("puntaje_minimo")
                    })

    print(f"🟢 2. Datos directos de usuario obtenidos: {datos_usuario}")

    if not datos_usuario:
        print("❌ 4. El usuario no existe en la BD, redirigiendo...")
        return RedirectResponse(url="/login?error=Usuario+no+encontrado", status_code=303)

    # Contexto con las actividades filtradas por nivel
    contexto = {
        "request": request,
        "id_usuario": id_usuario,
        **contexto_base,
        "nombre": datos_usuario.get("nombre"),
        "puntos": datos_usuario.get("puntaje_total", 0),
        "nivel": datos_usuario.get("nivel", 1),
        "racha": datos_usuario.get("dias_racha", 0),
        "id_avatar_seleccionado": "",
        "progreso": {},
        "logros": [],
        "elementos": [],
        "actividades": actividades_lista, # <--- Aquí pasamos las actividades filtradas por su nivel
        "notificaciones": [],
        "notificaciones_no_leidas": 0,
        "imagenes": {
            "Matemáticas": "", 
            "Español": "", 
            "Biología": "", 
            "Bienestar": ""
        }
    }
    
    print("🟢 3. Renderizando plantilla final con éxito...")
    return templates.TemplateResponse(request=request, name="inicio_Lynko.html", context=contexto)

@router.get("/perfil-estudiante/{id_usuario}", response_class=HTMLResponse)
def vista_perfil(id_usuario: int, request: Request):
    print(f"🟢 Solicitando perfil para usuario ID: {id_usuario}")
    """Muestra datos detallados del perfil del estudiante y sus avatares."""
    
    # Obtenemos los datos con seguridad
    resultado = consultar_dashboard_estudiante_db(id_usuario)
    print(f"🔍 [DEBUG] Lo que devolvió la BD es: {resultado} (Tipo: {type(resultado)})")
    # Si por alguna razón extraña llega a venir mal, evitamos que explote
    if not resultado or not isinstance(resultado, tuple) or len(resultado) != 3:
        print("⚠️ Redirigiendo al login por datos inválidos o None")
        return RedirectResponse(url="/login?error=Error+en+base+de+datos", status_code=303)
    datos_usuario, progreso, logros = resultado
    
    if not datos_usuario:
        return RedirectResponse(url="/login?error=Usuario+no+encontrado", status_code=303)
    
    lista_avatares = obtener_todos_los_avatares_db()
    contexto_base = obtener_contexto_base(id_usuario)
    
    contexto = {
        "request": request,
        "id_usuario": id_usuario,
        "nombre": datos_usuario.get("nombre"),
        "correo": datos_usuario.get("correo"),
        "puntos": datos_usuario.get("puntaje_total"),
        "nivel": datos_usuario.get("nivel"),
        "racha": datos_usuario.get("dias_racha"),
        "avatar_perfil": datos_usuario.get("link_avatar_perfil"), 
        "avatar_actual": datos_usuario.get("link_imagen"), 
        "lista_avatares": lista_avatares,
        "progreso": progreso,
        "logros": logros,
        **contexto_base
    }
    
    return templates.TemplateResponse(
        request=request, 
        name="Perfil.html", 
        context=contexto
    )
    
@router.get("/ajustes-estudiante/{id_usuario}", response_class=HTMLResponse)
def vista_ajustes(id_usuario: int, request: Request):
    
    datos_user = obtener_contexto_base(id_usuario)
    return templates.TemplateResponse(
        request=request, name="Ajustes.html", 
        context={"request": request, "id_usuario": id_usuario, **datos_user}
    )


@router.post("/ajustes-estudiante/{id_usuario}/guardar")
async def guardar_ajustes_estudiante(
    id_usuario: int,
    request: Request,
    datos: EstudianteActualizar = Depends(EstudianteActualizar.as_form)
):
    try:
       
        nueva_pass = datos.contrasena if datos.contrasena and datos.contrasena.strip() != "" else None

        exito = actualizar_perfil_estudiante_db(
            id_usuario=id_usuario,
            nombre=datos.nombre,
            correo=datos.correo,
            contrasena_hash=nueva_pass 
        )

        if exito:
            return RedirectResponse(url=f"/perfil-estudiante/{id_usuario}?msg=¡Contraseña+y+datos+actualizados+correctamente!", status_code=303)
        else:
            return RedirectResponse(url=f"/ajustes-estudiante/{id_usuario}?error=No+se+pudo+actualizar", status_code=303)
            
    except Exception as e:
        print(f"⚠️ Error al guardar ajustes: {e}")
        return RedirectResponse(url=f"/ajustes-estudiante/{id_usuario}?error=Error+interno", status_code=303)


@router.post("/perfil/actualizar-avatar")
async def procesar_cambio_avatar(
    request: Request, 
    id_avatar: int = Form(...), 
    id_usuario: Optional[int] = Form(None)
):
    # Si no viene en el formulario, lo rescatamos de la sesión activa
    if not id_usuario:
        id_usuario = request.session.get("id_usuario")
        
    if not id_usuario:
        return RedirectResponse(url="/login?error=Sesion+expirada", status_code=303)
    
    # 1. Actualizamos el avatar en la base de datos
    exito = actualizar_avatar_estudiante_db(id_usuario, id_avatar)
    
    if exito:
        return RedirectResponse(url=f"/perfil-estudiante/{id_usuario}?msg=Avatar+actualizado+con+exito", status_code=303)
    else:
        return RedirectResponse(url=f"/perfil-estudiante/{id_usuario}?error=No+se+pudo+actualizar+el+avatar", status_code=303)

@router.get("/recompensas-estudiante/{id_usuario}", response_class=HTMLResponse)
def vista_recompensas(id_usuario: int, request: Request):
    """Muestra logros alcanzados y pendientes."""
    
    # Obtenemos el contexto base (que incluye racha, usuario, y las notificaciones si las centralizaste ahí)
    contexto_base = obtener_contexto_base(id_usuario) # o obtener_contexto_base(id_usuario) según tu archivo
    
    # Consultamos los logros del estudiante
    todos_logros = obtener_todos_logros_con_estado_db(id_usuario)
    
    # Separamos en dos listas para la presentación en Recompensas.html
    alcanzados = [l for l in todos_logros if l['obtenido']]
    pendientes = [l for l in todos_logros if not l['obtenido']]
    
    return templates.TemplateResponse(
        request=request, 
        name="Recompensas.html", 
        context={
            "request": request, 
            "id_usuario": id_usuario, 
            **contexto_base,
            "logros_alcanzados": alcanzados, 
            "logros_pendientes": pendientes
        }
    )