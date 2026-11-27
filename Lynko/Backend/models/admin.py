from config.database import obtener_conexion
from contextlib import closing
import traceback
from datetime import datetime, timedelta
from fastapi import HTTPException
from models.estudiantes import registrar_notificacion_db

# =========================================
# MODELO PURO (Acceso a Datos)
# =========================================

def obtener_metricas_globales_db():
    """
    1. Recupera métricas de efectividad por materia.
    Retorna lista de tuplas crudas
    """
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT m.nombre, COUNT(i.id_intento), COALESCE(ROUND(AVG(i.nota_final)::numeric, 1), 0), COUNT(CASE WHEN i.aprobado THEN 1 END)
                    FROM materias m 
                    LEFT JOIN examenes e ON m.id_materia = e.id_materia
                    LEFT JOIN intentos_examen i ON e.id_examen = i.id_examen 
                    GROUP BY m.nombre;
                """)
                return cursor.fetchall()
    except Exception as e:
        print(f"Error en obtener_metricas_globales_db: {e}")
        return []

def obtener_historial_examenes_db():
    """
    2. Recupera historial de mejores exámenes rendidos.
    Retorna lista de tuplas crudas.
    """
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT u.nombre, e.titulo, m.nombre, i.nota_final 
                    FROM intentos_examen i
                    JOIN usuarios u ON i.id_usuario = u.id_usuario 
                    JOIN examenes e ON i.id_examen = e.id_examen
                    JOIN materias m ON e.id_materia = m.id_materia 
                    ORDER BY i.nota_final DESC;
                """)
                return cursor.fetchall()
    except Exception as e:
        print(f"Error en obtener_historial_examenes_db: {e}")
        return []

def obtener_todos_los_estudiantes_db():
    """
    4. y 6. Retorna nómina completa de estudiantes con sus datos base.
    """
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT u.id_usuario, u.nombre, u.correo, u.puntaje_total, u.nivel, u.dias_racha
                    FROM usuarios u
                    WHERE u.rol = 'estudiante' 
                    ORDER BY u.puntaje_total ASC;
                """)
                return cursor.fetchall()
    except Exception as e:
        print(f"Error en obtener_todos_los_estudiantes_db: {e}")
        return []


def obtener_estudiante_por_id_db(id_estudiante):
    """Consulta los datos detallados de un estudiante específico por su ID."""
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                # Ajusta los campos según las columnas reales de tu tabla de usuarios/estudiantes
                cursor.execute("""
                    SELECT id_usuario, nombre, correo, puntaje_total, fecha_registro 
                    FROM usuarios 
                    WHERE id_usuario = %s;
                """, (id_estudiante,))
                return cursor.fetchone()
    except Exception as e:
        print(f"Error en obtener_estudiante_por_id_db: {e}")
        return None

def obtener_historial_estudiante_db(id_usuario: int):
    """
    Recupera el historial de actividades/preguntas respondidas por el estudiante
    haciendo JOIN entre respuestas_usuario, intentos_examen, preguntas y materias.
    """
    query = """
        SELECT 
            m.nombre AS materia,
            p.pregunta AS pregunta,
            r.es_correcta AS resultado,
            COALESCE(i.fecha_fin, i.fecha_inicio) AS fecha
        FROM respuestas_usuario r
        JOIN intentos_examen i ON r.id_intento = i.id_intento
        JOIN preguntas p ON r.id_pregunta = p.id_pregunta
        JOIN materias m ON p.id_materia = m.id_materia
        WHERE r.id_usuario = %s
        ORDER BY i.fecha_fin DESC NULLS LAST;
    """
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (id_usuario,))
                return cursor.fetchall()
    except Exception as e:
        print(f"Error en obtener_historial_estudiante_db: {e}")
        return []

def obtener_logros_estudiante_db(id_usuario: int):
    """
    Recupera las medallas y logros ganados haciendo JOIN 
    entre logros_usuario y la tabla logros.
    """
    query = """
        SELECT 
        lu.id_usuario,
        l.id_logro,
        l.nombre,
        l.descripcion,
        l.imagen_medalla AS icono,
        lu.fecha_desbloqueo
        FROM logros_usuario lu
        JOIN logros l ON lu.id_logro = l.id_logro
        WHERE lu.id_usuario = %s
        ORDER BY lu.fecha_desbloqueo DESC;
    """
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (id_usuario,))
                return cursor.fetchall()
    except Exception as e:
        print(f"Error en obtener_logros_estudiante_db: {e}")
        return []

def obtener_ranking_top_10_db():
    """
    7. Consulta los 10 mejores puntajes globales.
    """
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT nombre, nivel, puntaje_total 
                    FROM usuarios 
                    WHERE rol = 'estudiante' 
                    ORDER BY puntaje_total DESC LIMIT 10;
                """)
                return cursor.fetchall()
    except Exception as e:
        print(f"Error en obtener_ranking_top_10_db: {e}")
        return []

def obtener_listado_retos_con_metricas_db():
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        r.id_reto, 
                        r.titulo_general, 
                        r.puntos_recompensa_total,
                        r.fecha_inicio, 
                        r.fecha_fin,
                        COUNT(DISTINCT p.id_pregunta_reto) AS total_preguntas,
                        COUNT(DISTINCT pct.id_parte_cuento) AS total_partes
                    FROM retos_semanales r
                    LEFT JOIN partes_cuento_reto pct ON r.id_reto = pct.id_reto
                    LEFT JOIN preguntas_reto p ON r.id_reto = p.id_reto
                    GROUP BY r.id_reto, r.titulo_general, r.puntos_recompensa_total, r.fecha_inicio, r.fecha_fin
                    ORDER BY r.id_reto DESC;
                """)
                return cursor.fetchall()
    except Exception as e:
        print(f"Error en obtener_listado_retos_con_metricas_db: {e}")
        return []

def obtener_listado_retos_con_estadisticas_db() -> list:
    """
    Recupera todos los retos semanales con la cantidad de preguntas asociadas 
    de manera directa, utilizando un bloque 'with' 
    """
    retos = []
    query = """
        SELECT 
            r.id_reto, 
            r.titulo_general, 
            r.fecha_inicio, 
            r.fecha_fin,
            COUNT(DISTINCT p.id_pregunta_reto) AS total_preguntas
        FROM retos_semanales r
        LEFT JOIN preguntas_reto p ON r.id_reto = p.id_reto
        GROUP BY r.id_reto, r.titulo_general, r.fecha_inicio, r.fecha_fin
        ORDER BY r.id_reto DESC;
    """
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                for row in cursor.fetchall():
                    retos.append({
                        "id_reto": row[0],
                        "titulo": row[1],
                        "fecha_inicio": row[2],
                        "fecha_fin": row[3],
                        "total_preguntas": row[4] or 0
                    })
    except Exception as e:
        print(f"⚠️ Error en obtener_listado_retos_con_estadisticas_db: {e}")
        
    return retos

def obtener_catalogo_preguntas_detallado_db():
    """
    3. y 5. Recupera preguntas y sus opciones usando JSONAGG en BD.
    Retorna una lista de diccionarios (gracias a psycopg2.extras.RealDictCursor si se configura,
    o lo convertimos aquí manualmente para simplificar el esquema).
    """
    # Nota: Si usas un cursor normal, esto devolverá una tupla y el JSON vendrá como string.
    # Para MVC limpio, asumiremos que psycopg2 está configurado para devolver dicts o lo casteamos aquí.
    query = """
        SELECT p.id_pregunta, m.nombre AS materia, p.pregunta, p.nivel_dificultad, p.puntos_recompensa,
               COALESCE(
                   json_agg(
                       json_build_object('opcion', o.opcion, 'es_correcta', o.es_correcta)
                   ) FILTER (WHERE o.id_opcion IS NOT NULL), '[]'
               ) AS opciones
        FROM preguntas p
        JOIN materias m ON p.id_materia = m.id_materia
        LEFT JOIN opciones o ON p.id_pregunta = o.id_pregunta
        GROUP BY p.id_pregunta, m.nombre
        ORDER BY p.id_pregunta DESC;
    """
    try:
        with obtener_conexion() as conn:
            # Usamos RealDictCursor para obtener diccionarios directamente y facilitar la salida JSON
            import psycopg2.extras
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query)
                return cursor.fetchall() # Devuelve lista de diccionarios
    except Exception as e:
        print(f"Error en obtener_catalogo_preguntas_detallado_db: {e}")
        return []

def obtener_banco_retos_con_detalle_db():
    retos_dict = {}
    query = """
        SELECT 
            r.id_reto, r.titulo_general, r.descripcion, r.fecha_inicio, r.fecha_fin,
            p.id_pregunta_reto, p.pregunta, p.puntos_recompensa,
            o.id_opcion, o.opcion, o.es_correcta
        FROM retos_semanales r
        LEFT JOIN preguntas_reto p ON r.id_reto = p.id_reto
        LEFT JOIN opciones_reto o ON p.id_pregunta_reto = o.id_pregunta_reto
        ORDER BY r.id_reto DESC, p.id_pregunta_reto ASC;
    """
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                filas = cursor.fetchall()
                
                for fila in filas:
                    id_reto = fila[0]
                    if id_reto not in retos_dict:
                        retos_dict[id_reto] = {
                            "id_reto": id_reto,
                            "titulo": fila[1],
                            "descripcion": fila[2],
                            "fecha_inicio": fila[3],
                            "fecha_fin": fila[4],
                            "preguntas": {}
                        }
                    
                    id_preq = fila[5]
                    if id_preq and id_preq not in retos_dict[id_reto]["preguntas"]:
                        retos_dict[id_reto]["preguntas"][id_preq] = {
                            "id_pregunta": id_preq,
                            "pregunta": fila[6],
                            "puntos": fila[7],
                            "opciones": []
                        }
                    
                    id_opc = fila[8]
                    if id_opc:
                        retos_dict[id_reto]["preguntas"][id_preq]["opciones"].append({
                            "id_opcion": id_opc,
                            "opcion": fila[9],
                            "es_correcta": fila[10]
                        })
                        
        # Transformar los diccionarios anidados en listas para Jinja2
        resultado = []
        for reto in retos_dict.values():
            reto["preguntas"] = list(reto["preguntas"].values())
            resultado.append(reto)
            
        return resultado
    except Exception as e:
        print(f"Error al obtener banco de retos: {e}")
        return []

# =========================================
# ESCRITURA (Transaccional y Simple)
# =========================================

def crear_nueva_pregunta_completa_db(pregunta: str, id_materia: int, nivel: int, puntos: int, 
                                    opciones: list[dict]) -> tuple[bool, str]:
    """
    Inserta pregunta y sus opciones (lista de dicts: [{'opcion': '...', 'es_correcta': bool}, ...])
    de forma transaccional.
    """
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                # 1. Insertar Pregunta
                cursor.execute("""
                    INSERT INTO preguntas (id_materia, pregunta, nivel_dificultad, puntos_recompensa) 
                    VALUES (%s, %s, %s, %s) 
                    RETURNING id_pregunta;
                """, (id_materia, pregunta, nivel, puntos))
                
                res = cursor.fetchone()
                id_p = res[0]
                
                # 2. Insertar Opciones
                for opc in opciones:
                    cursor.execute(
                        "INSERT INTO opciones (id_pregunta, opcion, es_correcta) VALUES (%s, %s, %s);", 
                        (id_p, opc['opcion'], opc['es_correcta'])
                    )
                
                conn.commit()
                return True, "Pregunta añadida correctamente"
    except Exception as e:
        print(f"Error en crear_nueva_pregunta_completa_db: {e}")
        return False, "Error interno al guardar la pregunta"

def eliminar_fila_db(tabla: str, columna_id: str, valor_id: int) -> tuple[bool, str]:
    """
    Genérica para eliminar por ID de cualquier tabla (preguntas, usuarios, retos_semanales).
    """
    tablas_permitidas = ['preguntas', 'usuarios', 'retos_semanales']
    if tabla not in tablas_permitidas:
        return False, "Tabla no permitida para eliminación directa"

    query = f"DELETE FROM {tabla} WHERE {columna_id} = %s;"
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (valor_id,))
                conn.commit()
            return True, f"Registro eliminado de {tabla}"
    except Exception as e:
        print(f"Error al eliminar en {tabla}: {e}")
        return False, f"No se pudo eliminar el registro. Verifique dependencias."

def editar_datos_estudiante_db(id_usuario: int, nombre: str, correo: str, puntaje_total: int, nivel: int) -> tuple[bool, str]:
    """
    Actualiza la información principal del estudiante.
    """
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE usuarios 
                    SET nombre = %s, correo = %s, puntaje_total = %s, nivel = %s 
                    WHERE id_usuario = %s AND rol = 'estudiante';
                """, (nombre, correo, puntaje_total, nivel, id_usuario))
                conn.commit()
            return True, "Datos actualizados"
    except Exception as e:
        print(f"Error en editar_datos_estudiante_db: {e}")
        return False, "No se pudo actualizar"

def crear_nuevo_reto_completo_db(titulo: str, descripcion: str, link_audio: str, puntos_total: int, 
                                fecha_inicio: str, fecha_fin: str, preguntas: list[dict]) -> tuple[bool, str]:
    """
    Creación transaccional de un Reto Semanal completo con su audio general, partes, preguntas y opciones.
    """
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cursor:
                # 1. Insertar Reto (¡Incluyendo link_audio aquí!)
                cursor.execute("""
                    INSERT INTO retos_semanales (titulo_general, descripcion, link_audio, puntos_recompensa_total, fecha_inicio, fecha_fin)
                    VALUES (%s, %s, %s, %s, %s, %s) RETURNING id_reto;
                """, (titulo, descripcion, link_audio, puntos_total, fecha_inicio, fecha_fin))
                id_reto = cursor.fetchone()[0]

                # 2. Procesar partes, preguntas y opciones anidadas
                for item in preguntas:
                    # Crear Parte
                    cursor.execute("""
                        INSERT INTO partes_cuento_reto (id_reto, contenido_parte)
                        VALUES (%s, %s) RETURNING id_parte_cuento;
                    """, (id_reto, item['parte_cuento']))
                    id_parte = cursor.fetchone()[0]

                    # Crear Pregunta del reto
                    cursor.execute("""
                        INSERT INTO preguntas_reto (id_parte_cuento, pregunta, puntos_recompensa)
                        VALUES (%s, %s, %s) RETURNING id_pregunta_reto;
                    """, (id_parte, item['pregunta'], item['puntos']))
                    id_preg_reto = cursor.fetchone()[0]

                    # Crear Opciones del reto
                    for opc in item['opciones']:
                        cursor.execute("""
                            INSERT INTO opciones_reto (id_pregunta_reto, opcion, es_correcta)
                            VALUES (%s, %s, %s);
                        """, (id_preg_reto, opc['opcion'], opc['es_correcta']))

                conn.commit()
                return True, "Reto semanal creado con éxito"
    except Exception as e:
        # Nota: si 'conn' falla al abrirse, asegúrate de manejar el rollback de forma segura
        print(f"Error en crear_nuevo_reto_completo_db: {e}")
        return False, f"Error al crear reto: {e}"

def insertar_pregunta_reto_db(id_reto, pregunta, puntos, opciones_list, conexion_db):
    cursor = conexion_db.cursor()
    try:
        # 1. Insertar la pregunta principal vinculada al reto
        query_pregunta = """
            INSERT INTO preguntas_reto (id_reto, pregunta, puntos_recompensa)
            VALUES (%s, %s, %s)
            RETURNING id_pregunta_reto;
        """
        cursor.execute(query_pregunta, (id_reto, pregunta, puntos))
        id_pregunta = cursor.fetchone()[0]

        # 2. Insertar cada una de las opciones asociadas a la pregunta
        query_opcion = """
            INSERT INTO opciones_reto (id_pregunta_reto, opcion, es_correcta)
            VALUES (%s, %s, %s);
        """
        for op in opciones_list:
            cursor.execute(query_opcion, (id_pregunta, op["opcion"], op["es_correcta"]))

        # Confirmar los cambios definitivamente
        conexion_db.commit()
        return True, "Pregunta agregada con éxito"

    except Exception as e:
        conexion_db.rollback()
        traceback.print_exc() # Esto imprimirá el error real en tu consola negra de Python
        return False, str(e)
    finally:
        cursor.close()
        
        
def crear_actividad_y_notificar_db(
    id_materia: int,
    titulo: str,
    descripcion: str,
    tipo: str,
    puntos_recompensa: int,
    dato_curioso: str = None,
    imagen_url: str = None,
    frase: str = None,
    palabra_faltante: str = None,
    video_url: str = None,
    instrucciones_movimiento: str = None
):

    try:
        with obtener_conexion() as conexion:
            with conexion.cursor() as cursor:
                
                # 1. Insertar en la tabla matriz 'actividades_materia'
                query_actividad = """
                    INSERT INTO public.actividades_materia (id_materia, titulo, descripcion, tipo, puntos_recompensa)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id_actividad;
                """
                cursor.execute(query_actividad, (id_materia, titulo, descripcion, tipo, puntos_recompensa))
                id_actividad = cursor.fetchone()[0]

                # 2. Insertar en su tabla específica según el tipo de actividad
                if tipo == 'memorama':
                    query_sub = """
                        INSERT INTO public.contenido_minijuego (actividad_id, titulo_elemento, imagen_url, dato_curioso)
                        VALUES (%s, %s, %s, %s);
                    """
                    cursor.execute(query_sub, (id_actividad, titulo, imagen_url, dato_curioso))
                    
                elif tipo == 'completar_espacio':
                    query_sub = """
                        INSERT INTO public.completar_espacio_actividad (id_actividad, frase, imagen_url, palabra_faltante)
                        VALUES (%s, %s, %s, %s);
                    """
                    cursor.execute(query_sub, (id_actividad, frase, imagen_url, palabra_faltante))
                    
                elif tipo == 'baile':
                    query_sub = """
                        INSERT INTO public.rutinas_baile (id_actividad, video_url, instrucciones_movimiento)
                        VALUES (%s, %s, %s);
                    """
                    cursor.execute(query_sub, (id_actividad, video_url, instrucciones_movimiento))

                # 3. Consultar a TODOS los usuarios que sean estudiantes
                cursor.execute("SELECT id_usuario FROM public.usuarios WHERE rol = 'estudiante';")
                estudiantes = cursor.fetchall()

                titulo_notif = f"¡Nueva actividad disponible: {titulo}!"
                mensaje_notif = f"Se ha agregado un nuevo reto de tipo {tipo}. ¡Entra a resolverlo y gana puntos!"

                # 4. Despachar la notificación a cada estudiante usando tu función existente
                for estudiante in estudiantes:
                    id_estudiante = estudiante[0]
                    # Llamamos a tu función ya creada previamente
                    registrar_notificacion_db(conexion, id_estudiante, titulo_notif, mensaje_notif, tipo='actividad')

                conexion.commit()
                return {"success": True, "mensaje": "Actividad creada y notificaciones enviadas con éxito."}

    except Exception as e:
        print(f"Error al crear actividad: {e}")
        raise HTTPException(status_code=500, detail=str(e))