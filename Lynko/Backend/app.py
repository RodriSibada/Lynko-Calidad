import os
import secrets
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, Form, Depends 
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
from config_templates import templates 
from config.database import obtener_conexion
from models.auth import login_usuario, registrar_nuevo_estudiante, verificar_token_en_bd, eliminar_sesion_en_bd, enviar_correo_recuperacion
from routers import estudiantes
from routers.admin import router as admin_router
from routers.estudiantes import router as estudiantes_router

# 1. PRIMERO inicializamos la aplicación de FastAPI
app = FastAPI(title="Lynko API - Ecosistema Backend", version="1.0.0")

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RecuperarRequest(BaseModel):
    correo: str

class ActualizarPasswordRequest(BaseModel):
    token: str
    nueva_contrasena: str

# Definición de rutas base de directorios
BASE_DIR = Path(__file__).resolve().parent  
STATIC_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "Frontend", "static"))
TEMPLATES_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "Frontend", "templates"))
STORAGE_PHYSICAL_DIR = os.path.abspath(os.path.join(BASE_DIR, "storage"))

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Montaje de archivos estáticos con validación de seguridad
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    print(f"✅ Carpeta static cargada correctamente desde: {STATIC_DIR}")
else:
    print(f"⚠️ Advertencia: No se encontró la carpeta static en: {STATIC_DIR}")

if os.path.exists(STORAGE_PHYSICAL_DIR):
    app.mount("/storage", StaticFiles(directory=STORAGE_PHYSICAL_DIR), name="storage")
    print(f"✅ Carpeta storage cargada correctamente desde: {STORAGE_PHYSICAL_DIR}")
else:
    print(f"⚠️ Advertencia: No se encontró la carpeta storage en: {STORAGE_PHYSICAL_DIR}")

# 2. INCLUSIÓN DE ROUTERS (Controladores unificados)
app.include_router(admin_router)
app.include_router(estudiantes.router)

# 3. MIDDLEWARE DE AUTENTICACIÓN 
def aplicar_anticache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.middleware("http")
async def middleware_autenticacion_global(request: Request, call_next):
    path = request.url.path

    rutas_publicas = ["/login", "/logout", "/registro", "/", "/favicon.ico"]
    
    if path in rutas_publicas or path.startswith("/static") or path.startswith("/api/"):
        return await call_next(request)

    session_cookie = request.cookies.get("usuario_session")

    if not session_cookie:
        response = RedirectResponse(url="/login?error=Debes+iniciar+sesion", status_code=303)
        return aplicar_anticache(response)

    try:
        id_u, rol, token = session_cookie.split(":")
        
        # Validamos en la tabla 'sesiones' de la BD si el token sigue activo
        if not verificar_token_en_bd(token):
            response = RedirectResponse(url="/login?error=Sesion+expirada+o+cerrada", status_code=303)
            response.delete_cookie("usuario_session")
            return aplicar_anticache(response)

        if path.startswith("/admin") and rol != "admin":
            response = RedirectResponse(url="/login?error=Acceso+denegado", status_code=303)
            return aplicar_anticache(response)
            
    except ValueError:
        response = RedirectResponse(url="/login?error=Sesion+invalida", status_code=303)
        response.delete_cookie("usuario_session")
        return aplicar_anticache(response)

    response = await call_next(request)
    return aplicar_anticache(response)

# 4. MANEJO DE ERRORES GLOBALES
@app.exception_handler(404)
async def error_404_personalizado(request: Request, exc: HTTPException):
    return RedirectResponse(url="/login?error=La+pagina+solicitada+no+existe", status_code=303)

@app.exception_handler(500)
async def error_500_personalizado(request: Request, exc: Exception):
    print(f"🔥 Error Crítico 500: {exc}")
    return HTMLResponse(
        content=f"<h2>⚠️ Error Interno en Lynko</h2><p>Inténtalo más tarde o contacta al soporte.</p>", 
        status_code=500
    )

# ===========================================================================
# RUTAS PÚBLICAS (Frontend Views)
# ===========================================================================

@app.get("/", response_class=HTMLResponse)
def index_landing(request: Request):
    return templates.TemplateResponse(request=request, name="landing.html")

@app.get("/login", response_class=HTMLResponse)
def vista_login(request: Request, error: Optional[str] = None, msg: Optional[str] = None):
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request, "error": error, "msg": msg})

@app.get("/olvide-contrasena", response_class=HTMLResponse)
def vista_olvide_contrasena(request: Request, msg: Optional[str] = None, error: Optional[str] = None):
    return templates.TemplateResponse(request=request, name="olvide_contrasena.html", context={"request": request, "msg": msg, "error": error})

@app.get("/registro", response_class=HTMLResponse)
def vista_registro(request: Request, error: Optional[str] = None):
    return templates.TemplateResponse(request=request, name="registro.html", context={"request": request, "error": error})

# ===========================================================================
# ENDPOINTS DE AUTENTICACIÓN (Procesamiento)
# ===========================================================================

@app.post("/login")
def procesar_login(correo: str = Form(...), contrasena: str = Form(...)):
    resultado_login = login_usuario(correo, contrasena)
    
    if resultado_login:
        id_u, _, rol_limpio, token_sesion = resultado_login
        
        url_redirect = "/admin" if rol_limpio == "admin" else f"/inicio-estudiante/{id_u}"
        
        response = RedirectResponse(url=url_redirect, status_code=303)
        
        # Guardamos en la cookie el id, rol y token de sesión único
        response.set_cookie(
            key="usuario_session", 
            value=f"{id_u}:{rol_limpio}:{token_sesion}",
            httponly=True, 
            samesite="lax", 
            secure=False    
        )
        return response

    return RedirectResponse(url="/login?error=Credenciales+incorrectas+o+cuenta+inactiva", status_code=303)

@app.post("/registro")
def procesar_registro(nombre: str = Form(...), correo: str = Form(...), contrasena: str = Form(...)):
    exito, resultado = registrar_nuevo_estudiante(nombre, correo, contrasena)
    
    if exito:
        return RedirectResponse(url=f"/inicio-estudiante/{resultado}", status_code=303)
    
    return RedirectResponse(url=f"/registro?error={resultado}", status_code=303)

@app.post("/api/auth/solicitar-recuperacion")
async def solicitar_recuperacion(datos: RecuperarRequest):
    try:
        with obtener_conexion() as conn:
            if not conn:
                raise HTTPException(status_code=500, detail="Error de conexión a la base de datos")
            
            with conn.cursor() as cursor:
                # 1. Verificar si el correo existe en la tabla usuarios
                cursor.execute('SELECT id_usuario FROM public.usuarios WHERE correo = %s;', (datos.correo,))
                user = cursor.fetchone()
                
                if not user:
                    # Por seguridad, respondemos genérico para no revelar qué correos existen
                    return {"mensaje": "Si el correo está registrado, se le ha enviado un mensaje."}
                
                id_u = user[0]
                token_recu = secrets.token_hex(32)
                expiracion = datetime.now() + timedelta(minutes=15)
                
                # 2. Guardar el token de recuperación en la BD
                cursor.execute("""
                    INSERT INTO public.recuperacion_contrasena (id_usuario, token_recuperacion, fecha_expiracion)
                    VALUES (%s, %s, %s);
                """, (id_u, token_recu, expiracion))
                conn.commit()
                
                # 3. Enviar el correo real a través de Gmail SMTP
                enviar_correo_recuperacion(datos.correo, token_recu)
                
        return {"mensaje": "Se le ha enviado un correo para restablecer su contraseña."}
    
    except Exception as e:
        print(f"Error en solicitud de recuperación: {e}")
        raise HTTPException(status_code=400, detail="No se pudo procesar la solicitud.")

                

@app.post("/cambiar-contrasena")
def procesar_cambiar_contrasena(token: str = Form(...), nueva_contrasena: str = Form(...)):
    with obtener_conexion() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id_usuario FROM public.recuperacion_contrasena 
                WHERE token_recuperacion = %s AND fecha_expiracion > CURRENT_TIMESTAMP AND utilizado = FALSE;
            """, (token,))
            res = cursor.fetchone()
            
            if not res:
                return RedirectResponse(url="/login?error=Token+expirado+o+invalido", status_code=303)
            
            id_u = res[0]
            
            # Actualizar la contraseña en texto plano respetando las comillas del esquema[cite: 2]
            cursor.execute("""
                UPDATE public.usuarios 
                SET "contraseña" = %s 
                WHERE id_usuario = %s;
            """, (nueva_contrasena, id_u))
            
            # Invalidar el token para que no se pueda reutilizar
            cursor.execute("""
                UPDATE public.recuperacion_contrasena 
                SET utilizado = TRUE 
                WHERE token_recuperacion = %s;
            """, (token,))
            
            conn.commit()
            
    return RedirectResponse(url="/login?msg=Contrasena+actualizada+con+exito", status_code=303)

@app.post("/api/auth/actualizar-password")
async def actualizar_password(datos: ActualizarPasswordRequest):
    try:
        with obtener_conexion() as conn:
            if not conn:
                raise HTTPException(status_code=500, detail="Error de conexión a la base de datos")
            
            with conn.cursor() as cursor:
                # 1. Validar que el token sea válido y no haya expirado
                cursor.execute("""
                    SELECT id_usuario FROM public.recuperacion_contrasena 
                    WHERE token_recuperacion = %s AND fecha_expiracion > CURRENT_TIMESTAMP AND utilizado = FALSE;
                """, (datos.token,))
                res = cursor.fetchone()
                
                if not res:
                    raise HTTPException(status_code=400, detail="El token es inválido o ha expirado.")
                
                id_u = res[0]
                
                # 2. Actualizar la contraseña en la tabla usuarios[cite: 3]
                cursor.execute("""
                    UPDATE public.usuarios 
                    SET "contraseña" = %s 
                    WHERE id_usuario = %s;
                """, (datos.nueva_contrasena, id_u))
                
                # 3. Marcar el token como utilizado
                cursor.execute("""
                    UPDATE public.recuperacion_contrasena 
                    SET utilizado = TRUE 
                    WHERE token_recuperacion = %s;
                """, (datos.token,))
                
                conn.commit()
                
        return {"mensaje": "Contraseña actualizada con éxito"}
    
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error al actualizar contraseña: {e}")
        raise HTTPException(status_code=400, detail="No se pudo actualizar la contraseña.")

@app.get("/logout")
@app.post("/logout")
def cerrar_sesion(request: Request):
    session_cookie = request.cookies.get("usuario_session")
    
    if session_cookie:
        try:
            _, _, token = session_cookie.split(":")
            # Borramos el token de la tabla 'sesiones' en PostgreSQL[cite: 1]
            eliminar_sesion_en_bd(token)
        except Exception:
            pass

    response = RedirectResponse(url="/login?error=Has+cerrado+sesion+correctamente", status_code=303)
    response.delete_cookie("usuario_session")
    return aplicar_anticache(response)