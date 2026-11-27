from config.database import obtener_conexion
from contextlib import closing
import psycopg2.extras
from datetime import datetime, timedelta
import secrets
from passlib.context import CryptContext
import unicodedata
from typing import List, Dict, Any
import traceback

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# =========================================
# MODELO PURO (Acceso a Datos)
# =========================================
print("🚨 ESTE ARCHIVO SÍ SE ESTÁ LEYENDO 🚨")
def buscar_estudiante_por_correo_db(conexion, correo: str):
    """Verifica si el correo existe en la base de datos."""
    with conexion.cursor() as cursor:
        cursor.execute("SELECT id_usuario FROM usuarios WHERE correo = %s;", (correo,))
        return cursor.fetchone()

def guardar_token_recuperacion_db(conexion, id_usuario, token_recuperacion, expiracion):
    with conexion.cursor() as cursor:
        cursor.execute("""
            UPDATE usuarios 
            SET token_recuperacion = %s, token_expiracion = %s 
            WHERE id_usuario = %s;
        """, (token_recuperacion, expiracion, id_usuario))
        conexion.commit()

def validar_y_obtener_por_token_db(conexion, token: str):
    """Busca el estudiante por su token y valida si aún no ha expirado."""
    with conexion.cursor() as cursor:
        cursor.execute("""
            SELECT id_estudiante, token_expiracion 
            FROM estudiantes 
            WHERE token_recuperacion = %s;
        """, (token,))
        resultado = cursor.fetchone()
        
        if not resultado:
            return None
            
        id_estudiante = resultado[0] if isinstance(resultado, tuple) else resultado["id_estudiante"]
        expiracion = resultado[1] if isinstance(resultado, tuple) else resultado["token_expiracion"]
        
        if datetime.now() > expiracion:
            return "expirado"
            
        return id_estudiante

def actualizar_contrasena_db(conexion, id_estudiante: int, nueva_contrasena: str):
    """Cifra la nueva contraseña, la actualiza y limpia los campos del token."""
    hashed_password = pwd_context.hash(nueva_contrasena)
    with conexion.cursor() as cursor:
        cursor.execute("""
            UPDATE estudiantes 
            SET contrasena = %s, token_recuperacion = NULL, token_expiracion = NULL 
            WHERE id_estudiante = %s;
        """, (hashed_password, id_estudiante))
        conexion.commit()

# =========================================
# MODELO PURO (Acceso a Datos)
# =========================================

def consultar_dashboard_estudiante_db(id_usuario: int):
    print(f"🔍 [DB DEBUG] Iniciando consulta para ID: {id_usuario}")
    conn = None
    try:
        conn = obtener_conexion()
        if not conn:
            print("❌ [DB DEBUG] obtener_conexion() retornó None o vacío.")
            return None, {}, []
            
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # 1. Datos usuario
        print("🔍 [DB DEBUG] Paso 1: Ejecutando consulta de usuario...")
        cursor.execute("""
            SELECT 
                u.id_usuario, 
                u.nombre, 
                u.correo, 
                u.puntaje_total, 
                u.nivel, 
                u.dias_racha, 
                u.id_avatar_seleccionado,
                a.link_avatar_perfil,
                a.link_imagen
            FROM usuarios u
            LEFT JOIN avatares a ON u.id_avatar_seleccionado = a.id_avatar
            WHERE u.id_usuario = %s;
        """, (id_usuario,))
        datos_usuario = cursor.fetchone()
        
        if not datos_usuario:
            print(f"❌ [DB DEBUG] El usuario con ID {id_usuario} NO existe en la tabla usuarios.")
            cursor.close()
            conn.close()
            return None, {}, []

        # 2. Progreso
        print("🔍 [DB DEBUG] Paso 2: Ejecutando consulta de progreso...")
        cursor.execute("""
            SELECT ea.id_actividad, ea.completado, ea.intentos, am.titulo, am.tipo, am.puntos_recompensa
            FROM estudiante_actividades ea
            JOIN actividades_materia am ON ea.id_actividad = am.id_actividad
            WHERE ea.id_usuario = %s;
        """, (id_usuario,))
        filas_progreso = cursor.fetchall()
        progreso = {row["id_actividad"]: row for row in filas_progreso} if filas_progreso else {}

        # 3. Logros
        print("🔍 [DB DEBUG] Paso 3: Ejecutando consulta de logros...")
        cursor.execute("""
            SELECT l.id_logro, l.nombre, l.descripcion, l.imagen_medalla, lu.fecha_desbloqueo
            FROM logros_usuario lu
            JOIN logros l ON lu.id_logro = l.id_logro
            WHERE lu.id_usuario = %s;
        """, (id_usuario,))
        logros = cursor.fetchall() or []

        cursor.close()
        conn.close()
        print("✅ [DB DEBUG] ¡Todo OK! Retornando datos correctamente.")
        return datos_usuario, progreso, logros

    except Exception as e:
        print(f"🔥 [DB DEBUG EXCEPCIÓN CRÍTICA]: {e}")
        traceback.print_exc()
        if conn:
            try:
                conn.close()
            except:
                pass
        return None, {}, []

def registrar_sesion_db(id_usuario: int, token: str, horas_validez: int = 24):
    """Registra una sesión en la BD."""
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO sesiones (id_usuario, token_sesion, fecha_creacion, fecha_expiracion)
                    VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '%s hours');
                """, (id_usuario, token, horas_validez))
                conn.commit()
    except Exception as e:
        print(f"⚠️ Error al registrar sesión en BD: {e}")

def verificar_y_actualizar_racha_login(conexion, id_usuario: int):
    """
    Verifica la racha del usuario al iniciar sesión. 
    Si es un día nuevo consecutivo, aumenta la racha y genera la notificación.
    """
    with conexion.cursor() as cursor:
        # 1. Consultar racha actual y última conexión
        cursor.execute(
            "SELECT dias_racha, ultima_conexion FROM usuarios WHERE id_usuario = %s", 
            (id_usuario,)
        )
        usuario = cursor.fetchone()
        
        if not usuario:
            return
            
        racha_actual = usuario[0] if usuario[0] is not None else 0
        ultima_conexion = usuario[1]
        hoy = datetime.now().date()
        
        actualizar = False
        aumento_racha = False
        
        if ultima_conexion is None:
            # Primera vez conectándose en la historia
            racha_actual = 1
            aumento_racha = True
            actualizar = True
        else:
            if isinstance(ultima_conexion, datetime):
                ultima_conexion = ultima_conexion.date()
                
            diferencia = (hoy - ultima_conexion).days
            
            if diferencia == 1:
                # Se conectó ayer: ¡La racha sube un día!
                racha_actual += 1
                aumento_racha = True
                actualizar = True
            elif diferencia > 1:
                # Pasaron más de un día sin entrar: Se reinicia la racha a 1
                racha_actual = 1
                aumento_racha = False
                actualizar = True
            # Si diferencia == 0, significa que YA se había conectado hoy. 
            # No hacemos nada para que no sume doble el mismo día.

        # 2. Si hubo cambios, actualizamos la base de datos
        if actualizar:
            cursor.execute(
                """
                UPDATE usuarios 
                SET dias_racha = %s, ultima_conexion = %s 
                WHERE id_usuario = %s
                """,
                (racha_actual, datetime.now(), id_usuario)
            )
            
            # 3. Si la racha aumentó y es mayor a 1, disparamos la notificación automática (RF-37)
            if aumento_racha and racha_actual > 1:
                cursor.execute(
                    """
                    INSERT INTO public.notificaciones (id_usuario, titulo, mensaje, tipo, leida)
                    VALUES (%s, %s, %s, %s, FALSE)
                    """,
                    (
                        id_usuario, 
                        "¡Racha Activa! 🔥", 
                        f"¡Increíble! Has alcanzado una racha de {racha_actual} días consecutivos estudiando.", 
                        "racha"
                    )
                )
            
            conexion.commit()

def actualizar_perfil_estudiante_db(id_usuario: int, nombre: str, correo: str, contrasena_hash: str):
    """Actualiza los datos del perfil en la BD."""
    query = """
        UPDATE usuarios 
        SET nombre = %s, correo = %s, "contraseña" = %s 
        WHERE id_usuario = %s AND rol = 'estudiante';
    """
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (nombre, correo, contrasena_hash, id_usuario))
                conn.commit()
                return cursor.rowcount > 0 # Retorna True si se actualizó alguna fila
    except Exception as e:
        print(f"⚠️ Error al actualizar perfil en BD: {e}")
        return False

def consultar_preguntas_ejemplo_landing_db() -> list:
    """
    Consulta una pregunta aleatoria por materia para la landing page.
    Retorna lista de diccionarios (usando RealDictCursor).
    """
    try:
        with obtener_conexion() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                # DISTINCT ON asegura una pregunta por materia. Orden aleatorio.
                query = """
                    SELECT DISTINCT ON (p.id_materia) 
                        p.id_pregunta, m.nombre AS materia, p.pregunta, p.puntos_recompensa
                    FROM preguntas p
                    JOIN materias m ON p.id_materia = m.id_materia
                    ORDER BY p.id_materia, RANDOM();
                """
                cursor.execute(query)
                preguntas = cursor.fetchall()

                # Adjuntar opciones para cada pregunta
                for preg in preguntas:
                    cursor.execute("""
                        SELECT opcion, es_correcta
                        FROM opciones
                        WHERE id_pregunta = %s
                        ORDER BY RANDOM();
                    """, (preg['id_pregunta'],))
                    preg['opciones'] = cursor.fetchall()
                
                return preguntas
    except Exception as e:
        print(f"⚠️ Error al consultar preguntas landing en BD: {e}")
        return []

def obtener_todos_logros_con_estado_db(id_usuario: int) -> list:
    """
    Retorna todos los logros del sistema y marca con 'obtenido'=True los del usuario.
    Retorna lista de diccionarios (usando RealDictCursor).
    """
    query = """
        SELECT l.id_logro, l.nombre, l.descripcion, l.imagen_medalla,
               (lu.id_usuario IS NOT NULL) AS obtenido
        FROM logros l
        LEFT JOIN logros_usuario lu ON l.id_logro = lu.id_logro AND lu.id_usuario = %s
        ORDER BY l.id_logro ASC;
    """
    try:
        with obtener_conexion() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, (id_usuario,))
                return cursor.fetchall()
    except Exception as e:
        print(f"⚠️ Error al obtener todos los logros en BD: {e}")
        return []

def obtener_catalogo_examenes_estudiante_db() -> list:
 
    query = """
        SELECT e.id_examen, e.titulo, e.descripcion, m.nombre AS nombre_materia
        FROM examenes e
        JOIN materias m ON e.id_materia = m.id_materia
        ORDER BY e.fecha_creacion DESC;
    """
    try:
        with obtener_conexion() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query)
                return cursor.fetchall()
    except Exception as e:
        print(f"⚠️ Error al obtener exámenes en BD: {e}")
        return []

def consultar_dashboard_estudiante_db(id_usuario):
    try:
        with obtener_conexion() as conn:
            if not conn: 
                return None, {}, []
            
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                
                # 1. Datos del usuario incluyendo el avatar seleccionado
                cursor.execute("""
                    SELECT u.id_usuario, u.nombre, u.correo, u.puntaje_total, u.nivel, u.dias_racha, 
                    a.link_imagen, a.link_avatar_perfil 
                    FROM usuarios u
                    LEFT JOIN avatares a ON u.id_avatar_seleccionado = a.id_avatar
                    WHERE u.id_usuario = %s AND u.activo = TRUE;
                """, (id_usuario,))
                datos_usuario = cursor.fetchone() 

                if not datos_usuario:
                    return None, {}, []

                # 2. CALCULAR EL PROGRESO REAL POR MATERIA EN FORMA DE DICCIONARIO
                cursor.execute("SELECT id_materia, nombre FROM materias;")
                materias = cursor.fetchall()
                
                progreso_dict = {}
                for materia in materias:
                    id_mat = materia["id_materia"]
                    nombre_mat = materia["nombre"]
                    
                    try:
                        cursor.execute("SELECT COUNT(*) as total FROM actividades_materia WHERE id_materia = %s;", (id_mat,))
                        res_total = cursor.fetchone()
                        total_actividades = res_total["total"] if res_total else 0
                        
                        if total_actividades > 0:
                            cursor.execute("""
                                SELECT COUNT(ea.id_actividad) as completadas 
                                FROM estudiante_actividades ea
                                JOIN actividades_materia am ON ea.id_actividad = am.id_actividad
                                WHERE ea.id_usuario = %s AND am.id_materia = %s AND ea.completado = TRUE;
                            """, (id_usuario, id_mat))
                            res_completadas = cursor.fetchone()
                            completadas = res_completadas["completadas"] if res_completadas else 0
                            
                            porcentaje = int((completadas / total_actividades) * 100)
                        else:
                            porcentaje = 0
                    except Exception as sub_e:
                        print(f"⚠️ Error calculando materia {nombre_mat}: {sub_e}")
                        porcentaje = 0
                        
                    progreso_dict[nombre_mat] = porcentaje

                # 3. Obtener los logros desbloqueados por el usuario
                cursor.execute("""
                    SELECT l.id_logro, l.nombre, l.descripcion, l.imagen_medalla, lu.fecha_desbloqueo
                    FROM logros_usuario lu
                    JOIN logros l ON lu.id_logro = l.id_logro
                    WHERE lu.id_usuario = %s;
                """, (id_usuario,))
                logros = cursor.fetchall() or []

                # 🚀 ¡ESTO ERA LO QUE FALTABA! Retornar los 3 valores al terminar con éxito
                return datos_usuario, progreso_dict, logros

    except Exception as e:
        print(f"⚠️ Error al consultar dashboard de estudiante en BD: {e}")
        return None, {}, []

def obtener_contexto_base(id_usuario: int):
    try:
        with obtener_conexion() as conexion:
            with conexion.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                
                # 1. Obtener datos del usuario incluyendo racha, nivel, puntos y avatar
                query_usuario = """
                    SELECT u.nombre, u.nivel, u.puntaje_total, u.dias_racha, a.link_avatar_perfil 
                    FROM usuarios u
                    LEFT JOIN avatares a ON u.id_avatar_seleccionado = a.id_avatar
                    WHERE u.id_usuario = %s;
                """
                cursor.execute(query_usuario, (id_usuario,))
                usuario = cursor.fetchone()

                # 2. Consultar las notificaciones del usuario de forma segura
                query_notif = """
                    SELECT id_notificacion, titulo, mensaje, tipo, leida, fecha_creacion 
                    FROM notificaciones 
                    WHERE id_usuario = %s 
                    ORDER BY fecha_creacion DESC
                """
                cursor.execute(query_notif, (id_usuario,))
                filas_notificaciones = cursor.fetchall()

                notificaciones_lista = []
                for f in filas_notificaciones:
                    # Convertimos el datetime a string de forma segura para el JSON del frontend
                    fecha_val = f.get("fecha_creacion")
                    fecha_str = fecha_val.isoformat() if fecha_val else ""

                    notificaciones_lista.append({
                        "id_notificacion": f.get("id_notificacion"),
                        "titulo": f.get("titulo"),
                        "mensaje": f.get("mensaje"),
                        "tipo": f.get("tipo"),
                        "leida": f.get("leida"),
                        "fecha_creacion": fecha_str
                    })

                notificaciones_no_leidas = sum(1 for n in notificaciones_lista if not n["leida"])

                if usuario:
                    return {
                        "nombre": usuario.get("nombre"),
                        "nivel": usuario.get("nivel", 1),
                        "puntos": usuario.get("puntaje_total", 0),
                        "racha": usuario.get("dias_racha", 0),
                        "avatar_perfil": usuario.get("link_avatar_perfil"),
                        "notificaciones": notificaciones_lista,
                        "notificaciones_no_leidas": notificaciones_no_leidas
                    }
    except Exception as e:
        print(f"Error en contexto base: {e}")
    
    return {
        "nombre": "", 
        "nivel": 1, 
        "puntos": 0, 
        "racha": 0,
        "avatar_perfil": None,
        "notificaciones": [],
        "notificaciones_no_leidas": 0
    }
    
def obtener_todos_los_avatares_db() -> list:
    """
    Obtiene la lista completa de avatares disponibles usando un bloque 'with' seguro.
    """
    lista_avatares = []
    query = "SELECT id_avatar, nombre_avatar, link_imagen, link_avatar_perfil FROM avatares ORDER BY id_avatar ASC;"
    
    try:
        # El with maneja la apertura y cierre automático de la conexión
        with obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(query)
                registros = cursor.fetchall()
                
                for reg in registros:
                    lista_avatares.append({
                        "id_avatar": reg[0],
                        "nombre_avatar": reg[1],
                        "link_imagen": reg[2]
                    })
    except Exception as e:
        print(f"⚠️ Error al obtener avatares: {e}")
        
    return lista_avatares

def actualizar_avatar_estudiante_db(id_usuario: int, id_avatar: int) -> bool:
    """
    Actualiza el avatar predeterminado seleccionado por el estudiante de forma segura.
    """
    query = """
        UPDATE usuarios 
        SET id_avatar_seleccionado = %s 
        WHERE id_usuario = %s;
    """
    try:
        with obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                cursor.execute(query, (id_avatar, id_usuario))
                conexion.commit()
                return cursor.rowcount > 0
    except Exception as e:
        print(f"⚠️ Error al actualizar el avatar: {e}")
        return False

# --- LÓGICA DE RETOS SEMANALES (Mismo archivo, funciones separadas) ---

def obtener_reto_semanal_activo_db(id_usuario: int):
    """
    BD: Retorna el reto activo y el estado de completado del usuario (si existe intento).
    """
    query_reto = """
        SELECT r.id_reto, r.titulo_general, r.descripcion, r.puntos_recompensa_total, r.link_audio,
               (SELECT completado FROM intentos_reto WHERE id_usuario = %s AND id_reto = r.id_reto LIMIT 1) AS ya_completado
        FROM retos_semanales r
        WHERE CURRENT_TIMESTAMP BETWEEN r.fecha_inicio AND r.fecha_fin
        AND r.es_visible = TRUE
        ORDER BY r.id_reto DESC
        LIMIT 1;
    """
    try:
        with obtener_conexion() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query_reto, (id_usuario,))
                reto = cursor.fetchone()
                
                if not reto: return None, []

                
                cursor.execute("""
                    SELECT id_pregunta_reto, pregunta, puntos_recompensa
                    FROM preguntas_reto 
                    WHERE id_reto = %s
                    ;
                """, (reto['id_reto'],))
                preguntas = cursor.fetchall()

                
                for preg in preguntas:
                    cursor.execute("""
                        SELECT id_opcion_reto, opcion, es_correcta
                        FROM opciones_reto
                        WHERE id_pregunta_reto = %s
                        ORDER BY RANDOM();
                    """, (preg['id_pregunta_reto'],))
                    preg['opciones'] = cursor.fetchall()
                
                return reto, preguntas

    except Exception as e:
        print(f"⚠️ Error al obtener reto semanal activo en BD: {e}")
        return None, []

def guardar_intento_reto_db(id_usuario: int, id_reto: int) -> int:
    
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO intentos_reto (id_usuario, id_reto, puntaje_obtenido, completado, fecha_intento)
                    VALUES (%s, %s, 0, false, CURRENT_TIMESTAMP)
                    RETURNING id_intento_reto;
                """, (id_usuario, id_reto))
                conn.commit()
                return cursor.fetchone()[0]
    except Exception as e:
        print(f"⚠️ Error al crear intento de reto en BD: {e}")
        raise e

def verificar_y_guardar_respuesta_reto_db(id_usuario: int, id_intento: int, id_pregunta: int, id_opcion: int) -> tuple[bool, int]:
  
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                
                cursor.execute("""
                    SELECT o.es_correcta, p.puntos_recompensa
                    FROM opciones_reto o
                    JOIN preguntas_reto p ON o.id_pregunta_reto = p.id_pregunta_reto
                    WHERE o.id_opcion_reto = %s AND p.id_pregunta_reto = %s;
                """, (id_opcion, id_pregunta))
                
                validacion = cursor.fetchone()
                if not validacion: return False, 0
                
                es_correcta, puntos = validacion
                
                
                cursor.execute("""
                    INSERT INTO respuestas_usuario_reto 
                    (id_usuario, id_intento_reto, id_pregunta_reto, id_opcion_reto_seleccionada, es_correcta)
                    VALUES (%s, %s, %s, %s, %s);
                """, (id_usuario, id_intento, id_pregunta, id_opcion, es_correcta))
                conn.commit()
                
                return es_correcta, puntos
                
    except Exception as e:
        print(f"⚠️ Error al guardar respuesta de reto en BD: {e}")
        return False, 0

def finalizar_intento_reto_db(id_intento: int, puntaje_total: int, id_usuario: int):
    """Actualiza el intento a completado y suma puntos al usuario (si > 0)."""
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE intentos_reto
                    SET puntaje_obtenido = %s, completado = true
                    WHERE id_intento_reto = %s;
                """, (puntaje_total, id_intento))
                
                if puntaje_total > 0:
                    cursor.execute("""
                        UPDATE usuarios SET puntaje_total = COALESCE(puntaje_total, 0) + %s
                        WHERE id_usuario = %s;
                    """, (puntaje_total, id_usuario))
                conn.commit()
    except Exception as e:
        print(f"⚠️ Error al finalizar intento de reto en BD: {e}")
        raise e

# --- Recuperar con correo ---

def buscar_usuario_por_correo_db(conexion, correo: str):
    cursor = conexion.cursor()
    cursor.execute("SELECT id_usuario, nombre, correo FROM public.usuarios WHERE correo = %s", (correo,))
    usuario = cursor.fetchone()
    cursor.close()
    return usuario

def guardar_token_recuperacion_db(conexion, id_usuario: int, token_jwt: str, expiracion: datetime):
    """Guarda el token JWT de recuperación y su expiración en la base de datos."""
    cursor = conexion.cursor()
    try:
        cursor.execute(
            """
            UPDATE usuarios 
            SET token_recuperacion = %s, token_expiracion = %s 
            WHERE id_usuario = %s;
            """,
            (token_jwt, expiracion, id_usuario)
        )
        conexion.commit()
    finally:
        cursor.close()

def validar_y_obtener_por_token_db(conexion, token):
    cursor = conexion.cursor()
    cursor.execute("""
        SELECT id_usuario FROM usuarios 
        WHERE token_recuperacion = %s AND token_expiracion > NOW();
    """, (token,))
    resultado = cursor.fetchone()
    cursor.close()
    return resultado

def actualizar_contrasena_db(conexion, id_usuario: int, nueva_contrasena: str):
    cursor = conexion.cursor()
    # Si guardas las contraseñas con hash (como bcrypt), asegúrate de pasarlas encriptadas. 
    # Si las guardas en texto plano (según tu lógica actual), pásala directamente:
    cursor.execute(
        'UPDATE public.usuarios SET "contraseña" = %s WHERE id_usuario = %s',
        (nueva_contrasena, id_usuario)
    )
    conexion.commit()
    cursor.close()


#--- Nose ---

def obtener_detalle_materia_completo_db(conexion_db, id_materia: int, id_usuario: int):
    """
    Obtiene el detalle completo de una materia, incluyendo:
    - Datos generales de la materia (id_materia, nombre, descripcion, icono, link_imagen, imagen_banner)
    - Lista de actividades con su estado de progreso (completado, intentos)
    - Carga dinámica de sub-elementos según el tipo de actividad ('completar_espacio', 'memoria', 'minijuego', 'baile')[cite: 5, 6, 7, 8]
    - Exámenes relacionados con sus preguntas y opciones reales (tablas: preguntas_examen y opciones_examen)[cite: 5, 6, 7, 8]
    - Porcentaje de avance y comparativa con el mes pasado[cite: 5, 6, 7, 8]
    """
    cursor = conexion_db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        # 1. Obtener información principal de la materia[cite: 5, 6, 7, 8]
        cursor.execute("""
            SELECT id_materia, nombre, descripcion, icono, link_imagen, imagen_banner 
            FROM public.materias 
            WHERE id_materia = %s;
        """, (id_materia,))
        materia = cursor.fetchone()
        
        if not materia:
            return None

        # 2. Consultar las actividades de la materia[cite: 5, 6, 7, 8]
        cursor.execute("""
            SELECT 
                a.id_actividad, 
                a.id_materia, 
                a.titulo, 
                a.descripcion, 
                a.tipo, 
                a.puntos_recompensa,
                COALESCE(e.completado, FALSE) AS completado,
                COALESCE(e.intentos, 0) AS intentos
            FROM public.actividades_materia a
            LEFT JOIN public.estudiante_actividades e 
                ON a.id_actividad = e.id_actividad AND e.id_usuario = %s
            WHERE a.id_materia = %s
            ORDER BY a.id_actividad ASC;
        """, (id_usuario, id_materia))
        actividades_raw = cursor.fetchall()

        actividades_lista = []
        for act in actividades_raw:
            actividad_dict = dict(act)
            tipo_act = actividad_dict['tipo']
            id_act = actividad_dict['id_actividad']

            # 3. Cargar dinámicamente según el tipo de actividad[cite: 5, 6, 7, 8]
            if tipo_act == 'completar_espacio':
                cursor.execute("""
                    SELECT id_completar_espacio, frase, imagen_url, palabra_faltante 
                    FROM public.completar_espacio_actividad 
                    WHERE id_actividad = %s 
                    ORDER BY id_completar_espacio ASC;
                """, (id_act,))
                actividad_dict['ejercicios'] = cursor.fetchall()

            elif tipo_act == 'memoria' or tipo_act == 'minijuego':
                cursor.execute("""
                    SELECT id, titulo_elemento, imagen_url, dato_curioso 
                    FROM public.contenido_minijuego 
                    WHERE actividad_id = %s;
                """, (id_act,))
                actividad_dict['elementos_memoria'] = cursor.fetchall()

            elif tipo_act == 'baile':
                cursor.execute("""
                    SELECT video_url, instrucciones_movimiento 
                    FROM public.rutinas_baile 
                    WHERE id_actividad = %s;
                """, (id_act,))
                datos_baile = cursor.fetchone()
                actividad_dict['datos_baile'] = datos_baile if datos_baile else {"video_url": ""}

            actividades_lista.append(actividad_dict)

        # 4. Consultar los exámenes asociados a esta materia y sus preguntas y opciones reales[cite: 5, 6, 7, 8]
        cursor.execute("""
            SELECT 
                id_examen, 
                id_materia, 
                titulo, 
                descripcion, 
                duracion_minutos, 
                puntaje_minimo_aprobatorio 
            FROM public.examenes 
            WHERE id_materia = %s;
        """, (id_materia,))
        examenes_raw = cursor.fetchall()

        examenes_lista = []
        for ex in examenes_raw:
            examen_dict = dict(ex)
            id_ex = examen_dict['id_examen']

            # Consultar preguntas usando la tabla real 'preguntas_examen'[cite: 5, 6, 7, 8]
            cursor.execute("""
                SELECT id_pregunta, pregunta, puntos_recompensa 
                FROM public.preguntas_examen
                WHERE id_examen = %s;
            """, (id_ex,))
            preguntas_raw = cursor.fetchall()

            preguntas_lista = []
            for p in preguntas_raw:
                id_preg = p['id_pregunta']
                
                # Consultar opciones usando la tabla real 'opciones_examen'[cite: 5, 6, 7, 8]
                cursor.execute("""
                    SELECT id_opcion, opcion 
                    FROM public.opciones_examen 
                    WHERE id_pregunta = %s;
                """, (id_preg,))
                opciones_raw = cursor.fetchall()
                
                opciones_lista = [{"id_opcion": o['id_opcion'], "opcion": o['opcion']} for o in opciones_raw]
                
                preguntas_lista.append({
                    "id_pregunta": id_preg,
                    "pregunta": p['pregunta'],
                    "puntos": p['puntos_recompensa'],
                    "opciones": opciones_lista
                })

            examen_dict['preguntas'] = preguntas_lista
            examen_dict['puntaje_minimo'] = examen_dict['puntaje_minimo_aprobatorio']
            
            examenes_lista.append(examen_dict)

        # 5. Calcular porcentaje de avance dinámico[cite: 5, 6, 7, 8]
        total_actividades = len(actividades_lista)
        completadas = sum(1 for act in actividades_lista if act['completado'])
        porcentaje_avance = int((completadas / total_actividades * 100)) if total_actividades > 0 else 0
        
        # 6. Calcular comparativa con el periodo pasado[cite: 5, 6, 7, 8]
        cursor.execute("""
            SELECT COUNT(*) AS completadas_pasado
            FROM public.estudiante_actividades e
            JOIN public.actividades_materia a ON e.id_actividad = a.id_actividad
            WHERE e.id_usuario = %s 
              AND a.id_materia = %s 
              AND e.completado = TRUE
              AND e.fecha_actualizacion < DATE_TRUNC('month', CURRENT_DATE);
        """, (id_usuario, id_materia))
        
        resultado_pasado = cursor.fetchone()
        completadas_pasado = resultado_pasado['completadas_pasado'] if resultado_pasado else 0
        
        porcentaje_pasado = int((completadas_pasado / total_actividades * 100)) if total_actividades > 0 else 0
        diferencia = porcentaje_avance - porcentaje_pasado

        comparativa = {
            "porcentaje_anterior": porcentaje_pasado,
            "diferencia": diferencia,
            "texto": f"Has mejorado un {diferencia}% respecto al mes pasado" if diferencia >= 0 else f"Bajaste un {abs(diferencia)}% respecto al mes pasado"
        }

        return {
            "materia": materia,
            "actividades": actividades_lista,
            "examenes": examenes_lista,
            "porcentaje_avance": porcentaje_avance,
            "comparativa": comparativa
        }

    except Exception as e:
        print(f"⚠️ Error al consultar el detalle completo de la materia: {e}")
        return None
    finally:
        cursor.close()
# --- Examenes ---

def obtener_examen_para_estudiante_db(id_examen, conexion_db):
    """Obtiene los datos del examen, sus preguntas y opciones usando tu esquema real."""
    with conexion_db.cursor() as cursor:
        # 1. Datos generales del examen
        cursor.execute("""
            SELECT id_examen, titulo, descripcion, duracion_minutos, puntaje_minimo_aprobatorio 
            FROM examenes WHERE id_examen = %s;
        """, (id_examen,))
        examen = cursor.fetchone()
        if not examen:
            return None

        # 2. Obtener las preguntas mediante la tabla puente 'preguntas_examen'
        cursor.execute("""
            SELECT p.id_pregunta, p.pregunta, p.puntos_recompensa 
            FROM preguntas p
            JOIN preguntas_examen pe ON p.id_pregunta = pe.id_pregunta
            WHERE pe.id_examen = %s;
        """, (id_examen,))
        preguntas_raw = cursor.fetchall()

        preguntas_lista = []
        for p in preguntas_raw:
            id_preg = p[0]
            
            # 3. Obtener las opciones de cada pregunta
            cursor.execute("""
                SELECT id_opcion, opcion 
                FROM opciones 
                WHERE id_pregunta = %s;
            """, (id_preg,))
            opciones_raw = cursor.fetchall()
            
            opciones_lista = [{"id_opcion": o[0], "opcion": o[1]} for o in opciones_raw]
            
            preguntas_lista.append({
                "id_pregunta": id_preg,
                "pregunta": p[1],
                "puntos": p[2],
                "opciones": opciones_lista
            })

        return {
            "id_examen": examen[0],
            "titulo": examen[1],
            "descripcion": examen[2],
            "duracion_minutos": examen[3],
            "puntaje_minimo": examen[4],
            "preguntas": preguntas_lista
        }

def calificar_y_guardar_examen_db(id_usuario, id_examen, respuestas_usuario, conexion_db):
    """
    Evalúa las respuestas enviadas por el estudiante, calcula el puntaje,
    registra el intento, otorga puntos si aprueba y genera la notificación respectiva.
    """
    with conexion_db.cursor() as cursor:
        try:
            # 1. Obtener las preguntas y los puntos totales posibles
            cursor.execute(
                "SELECT id_pregunta, puntos_recompensa FROM preguntas_examen WHERE id_examen = %s;", 
                (id_examen,)
            )
            preguntas = cursor.fetchall()
            
            if not preguntas:
                return {"error": "El examen no tiene preguntas registradas."}

            puntos_totales_posibles = sum(p[1] for p in preguntas)
            puntaje_obtenido = 0

            # Mapeo y validación de respuestas correctas
            for id_preg, puntos in preguntas:
                cursor.execute(
                    "SELECT id_opcion FROM opciones WHERE id_pregunta = %s AND es_correcta = TRUE;", 
                    (id_preg,)
                )
                opcion_correcta_db = cursor.fetchone()
                
                if opcion_correcta_db and id_preg in respuestas_usuario:
                    opcion_seleccionada = int(respuestas_usuario[id_preg])
                    if opcion_seleccionada == opcion_correcta_db[0]:
                        puntaje_obtenido += puntos

            # Calcular nota final en escala de 0 a 100
            if puntos_totales_posibles > 0:
                nota_final = int((puntaje_obtenido / puntos_totales_posibles) * 100)
            else:
                nota_final = 0

            # Obtener puntaje mínimo aprobatorio del examen
            cursor.execute(
                "SELECT puntaje_minimo_aprobatorio FROM examenes WHERE id_examen = %s;", 
                (id_examen,)
            )
            resultado_minimo = cursor.fetchone()
            minimo_aprobatorio = resultado_minimo[0] if resultado_minimo else 60

            aprobado = nota_final >= minimo_aprobatorio

            # 2. Registrar el intento en la tabla intentos_examen
            cursor.execute("""
                INSERT INTO intentos_examen (id_usuario, id_examen, nota_final, aprobado, fecha_fin)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                RETURNING id_intento;
            """, (id_usuario, id_examen, nota_final, aprobado))
            id_intento = cursor.fetchone()[0]

            # 3. Si aprueba, sumar puntos al usuario y registrar en historial
            puntos_a_ganar = 0
            if aprobado and puntaje_obtenido > 0:
                puntos_a_ganar = puntaje_obtenido
                cursor.execute("""
                    UPDATE usuarios
                    SET puntaje_total = puntaje_total + %s
                    WHERE id_usuario = %s;
                """, (puntos_a_ganar, id_usuario))

                cursor.execute("""
                    INSERT INTO historial_puntos (id_usuario, puntos_variacion, motivo)
                    VALUES (%s, %s, %s);
                """, (id_usuario, puntos_a_ganar, f"Aprobación de examen ID {id_examen} (Nota: {nota_final}%)"))

            # 4. Definir los textos de la alerta según el resultado
            if aprobado:
                titulo_alerta = "¡Examen Aprobado! 🎉"
                mensaje_alerta = f"Has aprobado el examen con una nota de {nota_final}%. ¡Ganaste {puntos_a_ganar} puntos de experiencia!"
                tipo_alerta = "actividad"
            else:
                titulo_alerta = "Resultado de Examen 📚"
                mensaje_alerta = f"Presentaste el examen y obtuviste {nota_final}%. ¡Sigue practicando para alcanzar el mínimo aprobatorio ({minimo_aprobatorio}%)!"
                tipo_alerta = "actividad"

            # Insertamos la notificación usando la misma conexión de base de datos
            cursor.execute("""
                INSERT INTO public.notificaciones (id_usuario, titulo, mensaje, tipo, leida)
                VALUES (%s, %s, %s, %s, FALSE);
            """, (id_usuario, titulo_alerta, mensaje_alerta, tipo_alerta))

            conexion_db.commit()
            return {
                "id_intento": id_intento,
                "nota_final": nota_final,
                "aprobado": aprobado,
                "puntos_ganados": puntos_a_ganar
            }

        except Exception as e:
            conexion_db.rollback()
            raise e

# --- ACTIVIDADES Y JUEGOS LUDICOS ---

def obtener_materias_con_actividades(id_usuario: int, conexion_db):
    """Devuelve las materias y sus actividades asociadas, incluyendo ejercicios de completar espacios."""
    cursor = conexion_db.cursor()
    try:
        # 1. Obtener todas las materias
        cursor.execute("SELECT id_materia, nombre, descripcion, link_imagen FROM public.materias;")
        materias_rows = cursor.fetchall()
        
        materias_lista = []
        for m in materias_rows:
            id_materia = m[0]
            
            # 2. Obtener las actividades de esta materia
            cursor.execute("""
                SELECT id_actividad, titulo, descripcion, tipo, puntos_recompensa 
                FROM public.actividades_materia 
                WHERE id_materia = %s;
            """, (id_materia,))
            actividades_rows = cursor.fetchall()
            
            actividades_lista = []
            for act in actividades_rows:
                id_act = act[0]
                tipo_act = act[3] # Ej: 'completar_espacio', 'examen', 'memoria', etc.
                
                # Verificar si el estudiante ya completó esta actividad
                cursor.execute("""
                    SELECT completado FROM public.estudiante_actividades 
                    WHERE id_usuario = %s AND id_actividad = %s;
                """, (id_usuario, id_act))
                progreso = cursor.fetchone()
                
                # Cargar ejercicios específicos si es del tipo 'completar_espacio'
                ejercicios = []
                if tipo_act == 'completar_espacio':
                    cursor.execute("""
                        SELECT id_completar_espacio, frase, imagen_url, palabra_faltante
                        FROM public.completar_espacio_actividad
                        WHERE id_actividad = %s
                        ORDER BY id_completar_espacio ASC;
                    """, (id_act,))
                    ejercicios_rows = cursor.fetchall()
                    for ej in ejercicios_rows:
                        ejercicios.append({
                            "id_completar_espacio": ej[0],
                            "frase": ej[1],
                            "imagen_url": ej[2],
                            "palabra_faltante": ej[3]
                        })

                # Cargar datos específicos si es del tipo 'baile' (Just Dance)
                datos_baile = None
                if tipo_act == 'baile':
                    cursor.execute("""
                        SELECT id_rutina, video_url, instrucciones_movimiento
                        FROM public.rutinas_baile
                        WHERE id_actividad = %s;
                    """, (id_act,))
                    rutina_row = cursor.fetchone()
                    if rutina_row:
                        datos_baile = {
                            "id_rutina": rutina_row[0],
                            "video_url": rutina_row[1],
                            "instrucciones_movimiento": rutina_row[2]
                        }
                
                actividades_lista.append({
                    "id_actividad": id_act,
                    "titulo": act[1],
                    "descripcion": act[2],
                    "tipo": tipo_act, 
                    "puntos_recompensa": act[4],
                    "completado": progreso[0] if progreso else False,
                    "ejercicios": ejercicios,  # Lista para completar espacios
                    "datos_baile": datos_baile   # Datos para la actividad de baile estilo Just Dance
                })
                
            cursor.execute("""
                           SELECT id_examen, titulo, descripcion, duracion_minutos, puntaje_minimo_aprobatorio 
                           FROM public.examenes 
                           WHERE id_materia = %s;
                           """, (id_materia,))
            examenes_rows = cursor.fetchall()
            examenes_lista = []
            for ex in examenes_rows:
                examenes_lista.append({
                    "id_examen": ex[0],
                    "titulo": ex[1],
                    "descripcion": ex[2],
                    "duracion_minutos": ex[3],
                    "puntaje_minimo_aprobatorio": ex[4]
                    })
            
            materias_lista.append({
                "id_materia": id_materia,
                "nombre": m[1],
                "descripcion": m[2],
                "link_imagen": m[3],
                "actividades": actividades_lista,
                "examenes": examenes_lista
            })
            
        return materias_lista
    except Exception as e:
        print(f"Error al obtener materias: {e}")
        return []
    finally:
        cursor.close()

def completar_actividad_db(id_usuario: int, id_actividad: int, puntos: int, conexion_db):
    """Registra la actividad como completada, suma puntos y otorga un logro automático."""
    cursor = conexion_db.cursor()
    try:
        # 1. Registrar o actualizar el progreso
        cursor.execute("""
            INSERT INTO public.estudiante_actividades (id_usuario, id_actividad, completado, intentos)
            VALUES (%s, %s, TRUE, 1)
            ON CONFLICT (id_usuario, id_actividad) 
            DO UPDATE SET completado = TRUE, intentos = estudiante_actividades.intentos + 1;
        """, (id_usuario, id_actividad))

        # 2. Sumar puntos totales al usuario
        cursor.execute("""
            UPDATE public.usuarios 
            SET puntaje_total = COALESCE(puntaje_total, 0) + %s 
            WHERE id_usuario = %s;
        """, (puntos, id_usuario))

        # 3. Otorgar Logro automático (Ej: Logro ID 2 por fijar conceptos con minijuegos)
        cursor.execute("""
            INSERT INTO public.logros_usuario (id_usuario, id_logro, fecha_desbloqueo)
            VALUES (%s, 2, CURRENT_TIMESTAMP)
            ON CONFLICT (id_usuario, id_logro) DO NOTHING;
        """, (id_usuario,))

        conexion_db.commit()
        return True, "¡Actividad completada con éxito! Puntos y logro desbloqueados."
    except Exception as e:
        conexion_db.rollback()
        return False, str(e)
    finally:
        cursor.close()


def consultar_elementos_minijuego():
    elementos = []
    # Usamos el context manager 'with' como está configurado en tu proyecto
    with obtener_conexion() as conexion:
        cursor = conexion.cursor()
        cursor.execute("SELECT id, titulo_elemento, imagen_url, dato_curioso FROM contenido_minijuego")
        resultados = cursor.fetchall()
        for fila in resultados:
            elementos.append({
                "id": fila[0],
                "titulo": fila[1],
                "imagen": fila[2],
                "dato_curioso": fila[3]
            })
        cursor.close()
    return elementos

def normalizar_texto(texto: str) -> str:
    """Convierte el texto a minúsculas, remueve espacios y acentos."""
    if not texto:
        return ""
    texto = texto.strip().lower()
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )


def obtener_ejercicios_por_actividad(id_actividad: int, conexion_db):
    """Obtiene los ejercicios de tipo completar espacio para una actividad dada."""
    cursor = conexion_db.cursor()
    try:
        query = """
            SELECT id_completar_espacio, frase, imagen_url, palabra_faltante
            FROM public.completar_espacio_actividad
            WHERE id_actividad = %s
            ORDER BY id_completar_espacio ASC;
        """
        cursor.execute(query, (id_actividad,))
        rows = cursor.fetchall()

        ejercicios = [
            {
                "id_completar_espacio": row[0],
                "frase": row[1],
                "imagen_url": row[2],
                "palabra_faltante": row[3]
            }
            for row in rows
        ]
        return ejercicios
    except Exception as e:
        print(f"Error al consultar ejercicios: {e}")
        return []
    finally:
        cursor.close()


def evaluar_respuesta_completar_db(id_completar_espacio: int, respuesta_usuario: str, conexion_db=None) -> Dict[str, Any]:
    """Evalúa un único campo/ejercicio ingresado por el usuario."""
    query = """
        SELECT palabra_faltante 
        FROM public.completar_espacio_actividad 
        WHERE id_completar_espacio = %s;
    """
    try:
        # Permite recibir conexion_db o abrir una nueva con obtener_conexion()
        conn = conexion_db if conexion_db else obtener_conexion()
        if not conn:
            return {"es_correcta": False, "mensaje": "Error de conexión."}
            
        cursor = conn.cursor()
        cursor.execute(query, (id_completar_espacio,))
        resultado = cursor.fetchone()
        cursor.close()

        if not resultado:
            return {"es_correcta": False, "mensaje": "Ejercicio no encontrado."}

        palabra_correcta = str(resultado[0]).strip()
        respuesta_limpia = str(respuesta_usuario).strip().lower()
        palabra_correcta_min = palabra_correcta.lower()

        # 1. Coincidencia Exacta
        if respuesta_limpia == palabra_correcta_min:
            return {
                "es_correcta": True,
                "mensaje": "¡Excelente! La respuesta es correcta."
            }

        # 2. Coincidencia sin tildes (Ortografía)
        if normalizar_texto(respuesta_limpia) == normalizar_texto(palabra_correcta_min):
            return {
                "es_correcta": False,
                "error_ortografia": True,
                "mensaje": f"¡Casi! Revisa la tilde. La palabra correcta es '{palabra_correcta}'."
            }

        # 3. Respuesta incorrecta
        return {
            "es_correcta": False,
            "error_ortografia": False,
            "mensaje": "Respuesta incorrecta. ¡Inténtalo de nuevo!"
        }
    except Exception as e:
        print(f"⚠️ Error al evaluar respuesta: {e}")
        return {"es_correcta": False, "mensaje": "Ocurrió un error al evaluar."}
    
# --- Notificaciones ---

def registrar_notificacion_db(conexion_db, id_usuario: int, titulo: str, mensaje: str, tipo: str = 'general'):
    """
    Inserta una nueva notificación/alerta para un usuario específico.
    Tipos recomendados: 'racha', 'insignia', 'nivel', 'actividad'
    """
    with conexion_db.cursor() as cursor:
        query = """
            INSERT INTO public.notificaciones (id_usuario, titulo, mensaje, tipo, leida)
            VALUES (%s, %s, %s, %s, FALSE)
            RETURNING id_notificacion;
        """
        cursor.execute(query, (id_usuario, titulo, mensaje, tipo))
        conexion_db.commit()
        resultado = cursor.fetchone()
        return resultado[0] if resultado else None


def obtener_notificaciones_usuario_db(conexion_db, id_usuario: int):
    """
    Obtiene el historial de notificaciones de un usuario, 
    ordenadas de la más reciente a la más antigua para el menú/modal.
    """
    with conexion_db.cursor() as cursor:
        query = """
            SELECT id_notificacion, titulo, mensaje, tipo, leida, fecha_creacion
            FROM public.notificaciones
            WHERE id_usuario = %s
            ORDER BY fecha_creacion DESC;
        """
        cursor.execute(query, (id_usuario,))
        columnas = [desc[0] for desc in cursor.description]
        return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


def marcar_notificacion_como_leida_db(conexion_db, id_notificacion: int, id_usuario: int):
    """
    Actualiza el estado de una notificación a 'leida = TRUE' 
    garantizando que pertenezca al usuario en sesión.
    """
    with conexion_db.cursor() as cursor:
        query = """
            UPDATE public.notificaciones
            SET leida = TRUE
            WHERE id_notificacion = %s AND id_usuario = %s;
        """
        cursor.execute(query, (id_notificacion, id_usuario))
        conexion_db.commit()
        
def actualizar_puntos_y_nivel(id_usuario: int, puntos_ganados: int):
    with obtener_conexion() as conexion:
        with conexion.cursor() as cursor:
            # 1. Sumar los puntos al usuario
            cursor.execute(
                "UPDATE usuarios SET puntos = puntos + %s WHERE id_usuario = %s",
                (puntos_ganados, id_usuario)
            )
            
            # 2. Consultar los puntos y nivel actuales
            cursor.execute("SELECT puntos, nivel FROM usuarios WHERE id_usuario = %s", (id_usuario,))
            resultado = cursor.fetchone()
            puntos_actuales = resultado[0]
            nivel_actual = resultado[1]
            
            # 3. Definir la regla de niveles según los puntajes mínimos
            nuevo_nivel = nivel_actual
            if puntos_actuales >= 500 and puntos_actuales < 1000:
                nuevo_nivel = 1
            elif puntos_actuales >= 1000 and puntos_actuales < 2000:
                nuevo_nivel = 2
            elif puntos_actuales >= 2000:
                nuevo_nivel = 3
                
            # 4. Si subió de nivel, actualizarlo en la BD
            if nuevo_nivel != nivel_actual:
                cursor.execute(
                    "UPDATE usuarios SET nivel = %s WHERE id_usuario = %s",
                    (nuevo_nivel, id_usuario)
                )
                # Opcional: Aquí puedes llamar a tu función de crear notificación de subida de nivel
                
        conexion.commit()
        
