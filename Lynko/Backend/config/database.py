import psycopg2
from contextlib import contextmanager

@contextmanager
def obtener_conexion():
    conn = None
    try:
        conn = psycopg2.connect(
            dbname="lynko",
            user="postgres",
            password="1234",
            host="localhost",
            port="5432"
        )
        yield conn  
    except Exception as e:
        print(f"Error de conexión a PostgreSQL: {e}")
        raise e  
    finally:
        if conn:
            conn.close()  