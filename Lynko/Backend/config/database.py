import os
from pathlib import Path
import psycopg2
from dotenv import load_dotenv
from contextlib import contextmanager

# Credenciales leídas de variables de entorno (archivo Backend/.env, no versionado)
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

@contextmanager
def obtener_conexion():
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "lynko"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )
        yield conn
    except Exception as e:
        print(f"Error de conexión a PostgreSQL: {e}")
        raise e
    finally:
        if conn:
            conn.close()
