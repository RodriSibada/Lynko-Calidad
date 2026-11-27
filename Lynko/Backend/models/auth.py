import re
import secrets
from fastapi import APIRouter, HTTPException, status, Response
from pydantic import BaseModel
from config.database import obtener_conexion
from fastapi.responses import RedirectResponse
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
# Modelo Pydantic para recibir los datos desde el cliente web

router = APIRouter()

class LoginRequest(BaseModel):
    correo: str
    contrasena: str
router = APIRouter()

def enviar_correo_recuperacion(correo_destino: str, token: str):
    remitente = "lynkoaprendejugando@gmail.com"          # Cambia por tu correo de Gmail
    password_app = "sxbv gdgz pfle nrli" # Contraseña de aplicación de Gmail (16 dígitos)
    
    # Enlace que recibirá el usuario
    enlace = f"http://127.0.0.1:8000/login?token={token}"
    
    # Configurar el mensaje
    mensaje = MIMEMultipart("alternative")
    mensaje["Subject"] = "Recuperación de contraseña - Lynko"
    mensaje["From"] = remitente
    mensaje["To"] = correo_destino
    
    # Cuerpo del correo en HTML amigable
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #FFF5EE; margin: 0; padding: 0; color: #4A3B32;">
        
        <!-- Tabla contenedora principal para asegurar centrado en Gmail -->
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #FFF5EE; padding: 40px 0;">
          <tr>
            <td align="center">
              
              <!-- Tarjeta principal estilo ventana kawaii / navegador -->
              <table border="0" cellpadding="0" cellspacing="0" width="560" style="background-color: #FFFFFF; border: 3px solid #FFA07A; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 15px rgba(255, 160, 122, 0.2);">
                
                <!-- Barra superior simulando navegador (Barra de título) -->
                <tr>
                  <td style="background-color: #FFE5D0; padding: 12px 20px; border-bottom: 2px solid #FFDAB9;">
                    <table border="0" cellpadding="0" cellspacing="0" width="100%">
                      <tr>
                        <!-- Botoncitos de colores -->
                        <td align="left" style="width: 60px;">
                          <span style="height: 10px; width: 10px; background-color: #FF7F50; display: inline-block; border-radius: 50%; margin-right: 4px;"></span>
                          <span style="height: 10px; width: 10px; background-color: #FFB347; display: inline-block; border-radius: 50%; margin-right: 4px;"></span>
                          <span style="height: 10px; width: 10px; background-color: #98FB98; display: inline-block; border-radius: 50%;"></span>
                        </td>
                        <!-- URL simulada -->
                        <td align="right">
                          <span style="font-size: 12px; font-weight: bold; color: #D2691E; background-color: #FFFFFF; padding: 4px 12px; border-radius: 10px; border: 1px solid #FFDAB9;">
                            lynko.app/recuperar-password 🦊
                          </span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>

                <!-- Cabecera de bienvenida -->
                <tr>
                  <td align="center" style="padding: 35px 30px 15px 30px;">
                    <h2 style="color: #FF6B35; font-size: 26px; margin: 0 0 10px 0; font-weight: bold;">
                      ¡Hola desde Lynko! 🐾
                    </h2>
                    <span style="display: inline-block; background-color: #FFEBE5; color: #E85D04; font-size: 11px; padding: 5px 14px; border-radius: 12px; font-weight: bold; border: 1px dashed #FFA07A; text-transform: uppercase; letter-spacing: 1px;">
                      ✦ recuperación de cuenta ✦
                    </span>
                  </td>
                </tr>

                <!-- Cuerpo del mensaje -->
                <tr>
                  <td align="center" style="padding: 10px 40px 25px 40px;">
                    <p style="font-size: 15px; line-height: 1.6; color: #5C4033; margin: 0 0 25px 0;">
                      Hemos recibido una solicitud para restablecer la contraseña de tu cuenta. No te preocupes, ¡a todos nos pasa! Haz clic en el botoncito de abajo para continuar:
                    </p>

                    <!-- Botón principal tipo píldora -->
                    <table border="0" cellspacing="0" cellpadding="0">
                      <tr>
                        <td align="center" bgcolor="#FF6B35" style="border-radius: 25px; border: 2px solid #FFDAB9;">
                          <a href="{enlace}" target="_blank" style="font-size: 15px; font-weight: bold; color: #ffffff; text-decoration: none; padding: 14px 30px; border-radius: 25px; border: 1px solid #FF6B35; display: inline-block;">
                            ✨ Restablecer Contraseña
                          </a>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>

                <!-- Pie de tarjeta / Alertas -->
                <tr>
                  <td align="center" style="background-color: #FFF9F5; padding: 20px 30px; border-top: 2px dashed #FFE5D0;">
                    <p style="font-size: 12px; color: #A07855; margin: 0 0 6px 0;">
                      Si no solicitaste este cambio, puedes ignorar este mensaje con tranquilidad.
                    </p>
                    <p style="font-size: 12px; color: #E85D04; font-weight: bold; margin: 0;">
                      ⏰ Este enlace expirará en 30 minutos.
                    </p>
                  </td>
                </tr>

              </table>

              <!-- Firma inferior externa -->
              <table border="0" cellpadding="0" cellspacing="0" width="560">
                <tr>
                  <td align="center" style="padding-top: 15px;">
                    <p style="font-size: 11px; color: #B08D79; margin: 0;">
                      ( Hecho con amor y mucha ternura por el equipo de Lynko 🦊 )
                    </p>
                  </td>
                </tr>
              </table>

            </td>
          </tr>
        </table>

      </body>
    </html>
"""
    
    mensaje.attach(MIMEText(html, "html"))
    
    try:
        # Conexión al servidor SMTP de Gmail
        servidor = smtplib.SMTP("smtp.gmail.com", 587)
        servidor.starttls()
        servidor.login(remitente, password_app)
        servidor.sendmail(remitente, correo_destino, mensaje.as_string())
        servidor.quit()
        print(f"✅ Correo de recuperación enviado con éxito a {correo_destino}")
        return True
    except Exception as e:
        print(f"❌ Error al enviar el correo: {e}")
        return False

def login_usuario(correo: str, contrasena: str):
    try:
        with obtener_conexion() as conn:
            if conn:
                with conn.cursor() as cursor:
                    
                    # 1. Traer todos los campos necesarios en orden estricto
                    cursor.execute("""
                        SELECT id_usuario, correo, rol, activo, intentos_fallidos, "contraseña", dias_racha, ultima_conexion 
                        FROM public.usuarios 
                        WHERE correo = %s;
                    """, (correo,))
                    user = cursor.fetchone()
                    
                    if not user:
                        print(f"❌ Login fallido: El correo '{correo}' no existe en la base de datos.")
                        return None
                    
                    id_usuario, db_correo, db_rol, activo, intentos_fallidos, db_contrasena, dias_racha, ultima_conexion = user
                    
                    # 2. Validar bloqueo por seguridad (5 o más intentos fallidos o cuenta inactiva)
                    if intentos_fallidos >= 5 or not activo:
                        print(f"⚠️ Cuenta bloqueada o inactiva para el correo: {correo}")
                        return None
                    
                    # 3. Verificar contraseña
                    if contrasena != db_contrasena:
                        cursor.execute("""
                            UPDATE public.usuarios 
                            SET intentos_fallidos = intentos_fallidos + 1 
                            WHERE correo = %s;
                        """, (correo,))
                        conn.commit()
                        
                        cursor.execute("SELECT intentos_fallidos FROM public.usuarios WHERE correo = %s;", (correo,))
                        intentos_actualizados = cursor.fetchone()[0]
                        if intentos_actualizados >= 5:
                            cursor.execute("UPDATE public.usuarios SET activo = FALSE WHERE correo = %s;", (correo,))
                            conn.commit()
                            print(f"🚫 La cuenta {correo} ha sido bloqueada por exceder los intentos fallidos.")
                            
                        print(f"❌ Contraseña incorrecta para el usuario: {correo}")
                        return None
                    
                    # 4. LOGIN EXITOSO: REINICIAR INTENTOS Y ACTUALIZAR RACHA
                    hoy = datetime.now().date()
                    aumento_racha = False
                    
                    if ultima_conexion is None:
                        dias_racha = 1
                        aumento_racha = True
                    else:
                        if isinstance(ultima_conexion, datetime):
                            ultima_conexion = ultima_conexion.date()
                            
                        diferencia = (hoy - ultima_conexion).days
                        
                        if diferencia == 1:
                            dias_racha += 1
                            aumento_racha = True
                        elif diferencia > 1:
                            dias_racha = 1
                            aumento_racha = False

                    cursor.execute("""
                        UPDATE public.usuarios 
                        SET intentos_fallidos = 0, 
                            dias_racha = %s, 
                            ultima_conexion = %s 
                        WHERE id_usuario = %s;
                    """, (dias_racha, datetime.now(), id_usuario))
                    
                    if aumento_racha and dias_racha > 1:
                        cursor.execute("""
                            INSERT INTO public.notificaciones (id_usuario, titulo, mensaje, tipo, leida)
                            VALUES (%s, %s, %s, %s, FALSE)
                        """, (
                            id_usuario, 
                            "¡Racha Activa! 🔥", 
                            f"¡Increíble! Has alcanzado una racha de {dias_racha} días consecutivos estudiando.", 
                            "racha"
                        ))
                    
                    # 5. GENERAR Y GUARDAR EL TOKEN DE SESIÓN EN LA TABLA 'sesiones'
                    token_sesion = secrets.token_hex(32)
                    fecha_expiracion = datetime.now() + timedelta(hours=2) # Expira en 2 horas
                    
                    cursor.execute("""
                        INSERT INTO public.sesiones (id_usuario, token_sesion, fecha_expiracion)
                        VALUES (%s, %s, %s);
                    """, (id_usuario, token_sesion, fecha_expiracion))
                    
                    conn.commit()
                    
                    rol_limpio = str(db_rol).strip().lower()
                    
                    # Retornamos también el token de sesión generado
                    return (id_usuario, db_correo, rol_limpio, token_sesion)
                    
    except Exception as e:
        print(f"⚠️ Error crítico en la función login_usuario: {e}")
        return None

def registrar_nuevo_estudiante(nombre: str, correo: str, contrasena: str):
    if len(contrasena) < 8 or not re.search(r"[a-zA-Z]", contrasena) or not re.search(r"[0-9]", contrasena) or len(set(contrasena)) < 4:
        return False, "Contraseña insegura. Debe tener mínimo 8 caracteres con letras y números."

    try:
        with obtener_conexion() as conn:
            if conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO usuarios (nombre, correo, "contraseña", rol, puntaje_total, activo) 
                        VALUES (%s, %s, %s, 'estudiante', 0, TRUE) RETURNING id_usuario;
                    """, (nombre, correo, contrasena))
                    nuevo_id = cursor.fetchone()[0]
                    
                    try:
                        cursor.execute("INSERT INTO logros_usuario (id_usuario, id_logro) VALUES (%s, 1);", (nuevo_id,))
                    except Exception:
                        pass
                    
                    # ========================================================
                    # AGREGAR NOTIFICACIÓN DE BIENVENIDA Y MEDALLA (RF-38 / General)
                    # ========================================================
                    try:
                        cursor.execute("""
                            INSERT INTO public.notificaciones (id_usuario, titulo, mensaje, tipo, leida)
                            VALUES (%s, %s, %s, %s, FALSE)
                        """, (
                            nuevo_id, 
                            "¡Bienvenido a Lynko! 🎉", 
                            "Has recibido tu medalla 'Primeros pasos'. ¡Puedes verla en la sección de recompensas!", 
                            "insignia"
                        ))
                    except Exception as e:
                        print(f"⚠️ No se pudo crear la notificación de bienvenida: {e}")

                    conn.commit()
                    return True, nuevo_id
    except Exception as e:
        print(f"⚠️ Error al registrar modelo: {e}")
        return False, "El correo ya está registrado o hubo un problema en el servidor."

    return False, "Error de conexión con la base de datos."


def verificar_token_en_bd(token: str) -> bool:
    """Verifica si el token existe en la BD y aún no ha expirado."""
    # conexion = obtener_conexion()
    # cursor = conexion.cursor()
    try:
        # cursor.execute(
        #     "SELECT id_sesion FROM public.sesiones WHERE token_sesion = %s AND fecha_expiracion > CURRENT_TIMESTAMP",
        #     (token,)
        # )
        # resultado = cursor.fetchone()
        # return resultado is not None
        return True # Cambiar por tu lógica real de consulta
    except Exception as e:
        print(f"Error al verificar token: {e}")
        return False
    finally:
        # cursor.close()
        # conexion.close()
        pass

def eliminar_sesion_en_bd(token: str):
    """Elimina el token de la tabla sesiones al cerrar sesión."""
    # conexion = obtener_conexion()
    # cursor = conexion.cursor()
    try:
        # cursor.execute(
        #     "DELETE FROM public.sesiones WHERE token_sesion = %s",
        #     (token,)
        # )
        # conexion.commit()
        pass
    except Exception as e:
        print(f"Error al eliminar sesión: {e}")
    finally:
        # cursor.close()
        # conexion.close()
        pass