# =====================================================================
#  Inicializa la base: crea tablas, carga datos y crea indices.
#  Uso:  python init_db.py
# =====================================================================
import os
import psycopg as psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and "supabase" in DATABASE_URL and "sslmode" not in DATABASE_URL:
    DATABASE_URL += ("&" if "?" in DATABASE_URL else "?") + "sslmode=require"

ARCHIVOS = ["01_schema.sql", "02_seed.sql", "03_indices.sql"]
AQUI = os.path.dirname(os.path.abspath(__file__))


def run():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            for f in ARCHIVOS:
                ruta = os.path.join(AQUI, "db", f)
                with open(ruta, "r", encoding="utf-8") as fh:
                    sql = fh.read()
                print(f"Ejecutando {f} ... ", end="", flush=True)
                cur.execute(sql)
                print("OK")
        conn.commit()
        print("\nBase de datos lista.")
    except Exception as e:
        conn.rollback()
        print("\nError inicializando la BD:", str(e).splitlines()[0])
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run()
