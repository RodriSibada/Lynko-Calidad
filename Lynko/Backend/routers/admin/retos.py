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
    obtener_listado_retos_con_estadisticas_db,
    crear_nuevo_reto_completo_db,
    insertar_pregunta_reto_db,
    eliminar_fila_db
)

router = APIRouter(prefix="/admin", tags=["Administración"])

UPLOAD_DIR = "storage/audios"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/gestion-retos", response_class=HTMLResponse)
def vista_gestion_retos(request: Request, q: Optional[str] = Query(None)):
    try:
        # Usamos 'with' para que maneje la conexión y su cierre automáticamente
        with obtener_conexion() as conexion:
            lista_retos_raw = obtener_listado_retos_con_estadisticas_db() or []
        
        # El resto de tu código procesando 'lista_retos_raw'...
        lista_retos_procesada = []
        for r in lista_retos_raw:
            if isinstance(r, (tuple, list)):
                lista_retos_procesada.append({
                    "id_reto": r[0],
                    "titulo": r[1],
                    "puntos_recompensa_total": r[2],
                    "fecha_inicio": r[3],
                    "fecha_fin": r[4],
                    "total_partes": r[5] if len(r) > 5 else 0
                })
            elif isinstance(r, dict):
                lista_retos_procesada.append(r)
            else:
                lista_retos_procesada.append({
                    "id_reto": getattr(r, "id_reto", getattr(r, "id", 0)),
                    "titulo": getattr(r, "titulo", getattr(r, "titulo", "")),
                    "puntos_recompensa_total": getattr(r, "puntos_recompensa_total", 0),
                    "fecha_inicio": getattr(r, "fecha_inicio", ""),
                    "fecha_fin": getattr(r, "fecha_fin", ""),
                    "total_partes": getattr(r, "total_partes", 0),
                })
        
        lista_retos_raw = lista_retos_procesada

    except Exception as e:
        print(f"⚠️ Error al obtener retos: {e}")
        lista_retos_raw = []
    
    if q and q.strip():
        q_lower = q.strip().lower()
        lista_retos_raw = [r for r in lista_retos_raw if q_lower in str(r.get('titulo', '')).lower()]

    return templates.TemplateResponse(
        request=request, 
        name="banco_retos.html", 
        context={
            "request": request, 
            "listado_retos": lista_retos_raw, 
            "query_busqueda": q
        }
    )

@router.get("/retos/crear", response_class=HTMLResponse)
def vista_crear_reto(request: Request):
    """Renderiza formulario creación de retos."""
    return templates.TemplateResponse(request=request, name="admin_reto_semanal.html")


@router.post("/retos/crear")
async def crear_reto_con_audio_unico(request: Request):
    try:
        form_data = await request.form()
        
        titulo = form_data.get("titulo")
        descripcion = form_data.get("descripcion")
        puntos_total_raw = form_data.get("puntos_recompensa_total")
        fecha_inicio_raw = form_data.get("fecha_inicio")
        fecha_fin_raw = form_data.get("fecha_fin")
        archivo_audio = form_data.get("link_audio")

        if not all([titulo, puntos_total_raw, fecha_inicio_raw, fecha_fin_raw]) or not archivo_audio:
            return RedirectResponse(url="/admin/gestion-retos?msg=Faltan+campos+obligatorios+o+el+audio", status_code=303)

        # Conversiones
        puntos_total = int(puntos_total_raw)
        dt_inicio = datetime.fromisoformat(str(fecha_inicio_raw))
        dt_fin = datetime.fromisoformat(str(fecha_fin_raw))

        # Guardar archivo físicamente
        timestamp = int(datetime.now().timestamp())
        safe_filename = archivo_audio.filename.replace(' ', '_')
        nombre_archivo = f"{timestamp}_{safe_filename}"
        ruta_fisica = os.path.join(UPLOAD_DIR, nombre_archivo)
        
        content = await archivo_audio.read()
        with open(ruta_fisica, "wb") as buffer:
            buffer.write(content)
        
        link_audio_db = f"/{ruta_fisica.replace(os.sep, '/')}"

        # 📥 Llamada correcta a tu función transaccional (pasándole una lista vacía de preguntas por ahora si ya no usas el generador dinámico)
        preguntas_ejemplo = [] # O los datos estructurados que tengas
        exito, msg = crear_nuevo_reto_completo_db(
            titulo, descripcion, link_audio_db, puntos_total, dt_inicio, dt_fin, preguntas_ejemplo
        )
        
        status_url = "exito" if exito else "error"
        return RedirectResponse(url=f"/admin/gestion-retos?msg={msg}&status={status_url}", status_code=303)

    except Exception as e:
        print(f"⚠️ Error crítico al procesar formulario de reto: {e}")
        return RedirectResponse(url="/admin/gestion-retos?msg=Error+interno+al+procesar+form", status_code=303)
    
@router.get("/retos/borrar/{id_reto}")
def borrar_reto_semanal(id_reto: int):
    """DELEGACIÓN al modelo para borrar un reto."""
    exito, msg = eliminar_fila_db("retos_semanales", "id_reto", id_reto)
    return RedirectResponse(url=f"/admin/gestion-retos?msg={msg}", status_code=303)

@router.get("/retos/{id_reto}/agregar-pregunta", response_class=HTMLResponse)
def vista_agregar_pregunta_reto(id_reto: int, request: Request):
    """
    Renderiza el formulario HTML para agregar una nueva pregunta a un reto específico.
    """
    return templates.TemplateResponse(
        request=request, 
        name="crear_pregunta_reto.html", 
        context={
            "request": request,
            "id_reto": id_reto
        }
    )

@router.post("/admin/retos/{id_reto}/preguntas/crear")
def crear_pregunta_reto_global(id_reto: int, payload: PreguntaRetoCreate):
    try:
        with obtener_conexion() as conexion:
            exito, mensaje = insertar_pregunta_reto_db(
                id_reto=id_reto,
                pregunta=payload.pregunta,
                puntos=payload.puntos_recompensa,
                opciones_list=[op.dict() for op in payload.opciones],
                conexion_db=conexion
            )
            
            if not exito:
                return JSONResponse(status_code=400, content={"detail": mensaje})
                
        return JSONResponse(status_code=200, content={"mensaje": "Pregunta guardada con éxito"})

    except Exception as e:
        print(f"⚠️ Error crítico al crear pregunta: {e}")
        return JSONResponse(status_code=500, content={"detail": str(e)})