# =====================================================================
#  RESTAURANTE - API (Flask + PostgreSQL)  [VERSION PYTHON]
#  Equivalente a la version Node, pero en Python.
#
#  Cada endpoint devuelve el SQL que ejecuto (campo "_sql") para que en
#  la demo se vea exactamente que consulta corrio.
#
#  MAPA RUBRICA -> ENDPOINT:
#    * CRUD simple + constraints     -> /api/productos (GET/POST/PUT/DELETE)
#    * CRUD complejo 3+ tablas + TX  -> POST /api/pedidos
#    * Reporte GROUP BY/HAVING+export-> /api/reportes/ventas-por-categoria
#    * NoSQL / JSONB                 -> /api/nosql/*
#    * Optimizacion / EXPLAIN        -> /api/optimizacion/*
# =====================================================================
import os
import io
import json
import csv

import psycopg as psycopg2
#import psycopg2.extras
from flask import Flask, request, jsonify, send_from_directory, Response
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
PORT = int(os.getenv("PORT", "3000"))

# Supabase exige SSL. En local no. Si la URL es de Supabase y no trae
# sslmode, se lo agregamos. (El codigo NO cambia entre local y Supabase.)
if DATABASE_URL and "supabase" in DATABASE_URL and "sslmode" not in DATABASE_URL:
    DATABASE_URL += ("&" if "?" in DATABASE_URL else "?") + "sslmode=require"

app = Flask(__name__, static_folder="public", static_url_path="")


def get_conn():
    """Abre una conexion nueva a PostgreSQL."""
    return psycopg2.connect(DATABASE_URL)


def explicar_error(e):
    """Traduce errores de constraints de PostgreSQL a mensajes claros en espanol."""
    code = getattr(e, "pgcode", None)
    diag = getattr(e, "diag", None)
    constraint = getattr(diag, "constraint_name", None) if diag else None
    column = getattr(diag, "column_name", None) if diag else None
    if code == "23505":
        return f"Violacion de UNIQUE: ya existe un registro con ese valor ({constraint})."
    if code == "23514":
        return f"Violacion de CHECK: el valor no cumple la regla ({constraint})."
    if code == "23502":
        return f'Violacion de NOT NULL: el campo "{column}" es obligatorio.'
    if code == "23503":
        return (f"Violacion de llave foranea: el registro relacionado no existe "
                f"o no se puede borrar ({constraint}).")
    # Mensaje limpio (primera linea) para cualquier otro error
    return str(e).splitlines()[0] if str(e) else "Error desconocido."


def consultar(sql, params=None):
    """Ejecuta un SELECT y devuelve lista de dicts."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or [])
            return cur.fetchall()
    finally:
        conn.close()


# =====================================================================
#  Servir el frontend (public/index.html en la raiz)
# =====================================================================
@app.route("/")
def index():
    return send_from_directory("public", "index.html")


# =====================================================================
#  CATALOGOS (para los <select> del formulario de pedidos)
# =====================================================================
@app.route("/api/categorias")
def categorias():
    sql = "SELECT id, nombre FROM categorias ORDER BY nombre"
    return jsonify(_sql=sql, data=consultar(sql))


@app.route("/api/clientes")
def clientes():
    sql = "SELECT id, nombre, email FROM clientes ORDER BY nombre"
    return jsonify(_sql=sql, data=consultar(sql))


@app.route("/api/mesas")
def mesas():
    sql = "SELECT id, numero, capacidad FROM mesas ORDER BY numero"
    return jsonify(_sql=sql, data=consultar(sql))


@app.route("/api/empleados")
def empleados():
    sql = "SELECT id, nombre, rol FROM empleados WHERE activo = TRUE ORDER BY nombre"
    return jsonify(_sql=sql, data=consultar(sql))


# =====================================================================
#  1) CRUD PRODUCTOS  (demostrar CHECK / UNIQUE / NOT NULL en vivo)
# =====================================================================
@app.route("/api/productos", methods=["GET"])
def listar_productos():
    sql = """SELECT p.id, p.nombre, p.precio, p.stock, p.disponible,
       c.nombre AS categoria, p.categoria_id, p.atributos
FROM productos p
LEFT JOIN categorias c ON c.id = p.categoria_id
ORDER BY p.id"""
    try:
        return jsonify(_sql=sql.strip(), data=consultar(sql))
    except Exception as e:
        return jsonify(_sql=sql.strip(), error=explicar_error(e)), 500


@app.route("/api/productos", methods=["POST"])
def crear_producto():
    b = request.get_json(silent=True) or {}
    sql = """INSERT INTO productos (nombre, precio, stock, categoria_id, atributos)
VALUES (%s, %s, %s, %s, %s::jsonb)
RETURNING *"""
    params = [
        b.get("nombre"),
        b.get("precio"),
        b.get("stock") if b.get("stock") is not None else 0,
        b.get("categoria_id") or None,
        json.dumps(b.get("atributos") or {}),
    ]
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        return jsonify(_sql=sql.strip(), _params=params, data=row), 201
    except Exception as e:
        conn.rollback()
        return jsonify(_sql=sql.strip(), _params=params, error=explicar_error(e)), 400
    finally:
        conn.close()


@app.route("/api/productos/<int:pid>", methods=["PUT"])
def editar_producto(pid):
    b = request.get_json(silent=True) or {}
    sql = """UPDATE productos
SET nombre = %s, precio = %s, stock = %s, categoria_id = %s, disponible = %s
WHERE id = %s
RETURNING *"""
    params = [b.get("nombre"), b.get("precio"), b.get("stock"),
              b.get("categoria_id") or None, b.get("disponible"), pid]
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        conn.commit()
        if row is None:
            return jsonify(error="No existe el producto."), 404
        return jsonify(_sql=sql.strip(), _params=params, data=row)
    except Exception as e:
        conn.rollback()
        return jsonify(_sql=sql.strip(), _params=params, error=explicar_error(e)), 400
    finally:
        conn.close()


@app.route("/api/productos/<int:pid>", methods=["DELETE"])
def borrar_producto(pid):
    sql = "DELETE FROM productos WHERE id = %s RETURNING id, nombre"
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, [pid])
            row = cur.fetchone()
        conn.commit()
        if row is None:
            return jsonify(error="No existe el producto."), 404
        return jsonify(_sql=sql, _params=[pid], data=row)
    except Exception as e:
        conn.rollback()
        return jsonify(_sql=sql, error=explicar_error(e)), 400
    finally:
        conn.close()


# =====================================================================
#  2) CRUD COMPLEJO + TRANSACCION ACID
#     Crear un pedido toca 3 tablas: pedidos + detalle_pedido + productos
#     (descuenta stock). Todo dentro de BEGIN ... COMMIT / ROLLBACK.
# =====================================================================
@app.route("/api/pedidos", methods=["POST"])
def crear_pedido():
    b = request.get_json(silent=True) or {}
    items = b.get("items")
    if not isinstance(items, list) or len(items) == 0:
        return jsonify(error="Debe enviar al menos un item."), 400

    pasos = []  # guardamos el SQL de cada paso para mostrarlo en la demo
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # psycopg2 ya abre una transaccion implicita; lo anotamos para la demo
        pasos.append("BEGIN;")

        # 1) Cabecera del pedido
        cur.execute(
            """INSERT INTO pedidos (cliente_id, mesa_id, empleado_id, estado, total)
               VALUES (%s, %s, %s, 'pendiente', 0) RETURNING id""",
            [b.get("cliente_id") or None, b.get("mesa_id") or None, b.get("empleado_id") or None],
        )
        pedido_id = cur.fetchone()["id"]
        pasos.append(
            f"-- cabecera\nINSERT INTO pedidos (...) VALUES "
            f"({b.get('cliente_id') or 'NULL'}, {b.get('mesa_id') or 'NULL'}, "
            f"{b.get('empleado_id') or 'NULL'}, 'pendiente', 0);"
        )

        # 2) Por cada item: validar stock, insertar detalle, descontar stock
        for it in items:
            cur.execute(
                "SELECT nombre, precio, stock FROM productos WHERE id = %s FOR UPDATE",
                [it.get("producto_id")],
            )
            prod = cur.fetchone()
            if prod is None:
                raise ValueError(f"Producto {it.get('producto_id')} no existe.")
            if prod["stock"] < it.get("cantidad", 0):
                raise ValueError(
                    f'Stock insuficiente de "{prod["nombre"]}" '
                    f'(hay {prod["stock"]}, pediste {it.get("cantidad")}). Se hace ROLLBACK.'
                )

            cur.execute(
                """INSERT INTO detalle_pedido (pedido_id, producto_id, cantidad, precio_unitario)
                   VALUES (%s, %s, %s, %s)""",
                [pedido_id, it.get("producto_id"), it.get("cantidad"), prod["precio"]],
            )
            pasos.append(
                f"-- linea\nINSERT INTO detalle_pedido (pedido_id, producto_id, cantidad, precio_unitario) "
                f"VALUES ({pedido_id}, {it.get('producto_id')}, {it.get('cantidad')}, {prod['precio']});"
            )

            cur.execute(
                "UPDATE productos SET stock = stock - %s WHERE id = %s",
                [it.get("cantidad"), it.get("producto_id")],
            )
            pasos.append(
                f"-- descontar stock\nUPDATE productos SET stock = stock - "
                f"{it.get('cantidad')} WHERE id = {it.get('producto_id')};"
            )

        # 3) Recalcular total del pedido desde el detalle
        cur.execute(
            """UPDATE pedidos
               SET total = (SELECT COALESCE(SUM(subtotal),0) FROM detalle_pedido WHERE pedido_id = %s)
               WHERE id = %s""",
            [pedido_id, pedido_id],
        )
        pasos.append(
            f"-- total\nUPDATE pedidos SET total = (SELECT SUM(subtotal) FROM detalle_pedido "
            f"WHERE pedido_id = {pedido_id}) WHERE id = {pedido_id};"
        )

        conn.commit()
        pasos.append("COMMIT;")

        cur.execute(
            """SELECT p.id, p.total, p.estado,
                      json_agg(json_build_object('producto', pr.nombre, 'cantidad', d.cantidad, 'subtotal', d.subtotal)) AS items
               FROM pedidos p
               JOIN detalle_pedido d ON d.pedido_id = p.id
               JOIN productos pr ON pr.id = d.producto_id
               WHERE p.id = %s GROUP BY p.id""",
            [pedido_id],
        )
        final = cur.fetchone()
        cur.close()
        return jsonify(_sql="\n".join(pasos), data=final), 201
    except Exception as e:
        conn.rollback()
        pasos.append("ROLLBACK;  -- se revierte TODO")
        msg = str(e) if isinstance(e, ValueError) else explicar_error(e)
        return jsonify(_sql="\n".join(pasos), error=msg), 400
    finally:
        conn.close()


@app.route("/api/pedidos", methods=["GET"])
def listar_pedidos():
    sql = """SELECT p.id, p.fecha, p.estado, p.total,
       cl.nombre AS cliente, m.numero AS mesa, e.nombre AS mesero
FROM pedidos p
LEFT JOIN clientes  cl ON cl.id = p.cliente_id
LEFT JOIN mesas     m  ON m.id  = p.mesa_id
LEFT JOIN empleados e  ON e.id  = p.empleado_id
ORDER BY p.id DESC"""
    return jsonify(_sql=sql.strip(), data=consultar(sql))


# =====================================================================
#  3) REPORTE: GROUP BY / HAVING + JOIN de 4 tablas + EXPORTACION
#     formato = json (default) | csv | excel
# =====================================================================
SQL_REPORTE = """SELECT c.nombre                AS categoria,
       COUNT(DISTINCT p.id)    AS num_pedidos,
       SUM(d.cantidad)         AS unidades_vendidas,
       SUM(d.subtotal)         AS ingresos
FROM pedidos p
JOIN detalle_pedido d ON d.pedido_id = p.id
JOIN productos     pr ON pr.id = d.producto_id
JOIN categorias    c  ON c.id = pr.categoria_id
WHERE p.estado IN ('pagado','servido')
GROUP BY c.nombre
HAVING SUM(d.subtotal) > %s
ORDER BY ingresos DESC"""


@app.route("/api/reportes/ventas-por-categoria")
def reporte_ventas():
    try:
        minimo = float(request.args.get("min", 0))
    except ValueError:
        minimo = 0
    formato = (request.args.get("formato", "json") or "json").lower()

    try:
        rows = consultar(SQL_REPORTE, [minimo])
    except Exception as e:
        return jsonify(_sql=SQL_REPORTE.strip(), error=explicar_error(e)), 500

    if formato == "json":
        return jsonify(_sql=SQL_REPORTE.strip(), _params=[minimo], data=rows)

    cab = ["categoria", "num_pedidos", "unidades_vendidas", "ingresos"]

    if formato == "csv":
        buf = io.StringIO()
        buf.write("\ufeff")  # BOM para que Excel abra bien los acentos
        w = csv.writer(buf)
        w.writerow(cab)
        for r in rows:
            w.writerow([r[k] for k in cab])
        return Response(
            buf.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="reporte_ventas.csv"'},
        )

    if formato == "excel":
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Ventas"
        encabezados = ["Categoria", "N. Pedidos", "Unidades", "Ingresos"]
        ws.append(encabezados)
        for celda in ws[1]:
            celda.font = celda.font.copy(bold=True)
        for r in rows:
            ws.append([r["categoria"], r["num_pedidos"], r["unidades_vendidas"], float(r["ingresos"] or 0)])
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return Response(
            out.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="reporte_ventas.xlsx"'},
        )

    return jsonify(error="Formato no soportado. Use json, csv o excel."), 400


# =====================================================================
#  4) MODULO NoSQL / HIBRIDO (JSONB sobre productos.atributos)
# =====================================================================
@app.route("/api/nosql/buscar")
def nosql_buscar():
    clave = request.args.get("clave", "")
    valor = request.args.get("valor", "")
    sql = """SELECT id, nombre, precio, atributos
               FROM productos
               WHERE atributos @> %s::jsonb"""
    # valor puede ser true/false/numero/texto -> lo normalizamos a JSON
    if valor in ("true", "false"):
        val_json = f'{{"{clave}": {valor}}}'
    else:
        try:
            num = float(valor)
            val_json = f'{{"{clave}": {int(num) if num.is_integer() else num}}}'
        except ValueError:
            val_json = f'{{"{clave}": "{valor}"}}'
    try:
        rows = consultar(sql, [val_json])
        return jsonify(
            _sql=sql.strip(), _params=[val_json],
            _explica='Tabla afectada: productos (columna JSONB atributos). Operador @> = "contiene".',
            data=rows,
        )
    except Exception as e:
        return jsonify(_sql=sql.strip(), error=explicar_error(e)), 400


@app.route("/api/nosql/alergeno")
def nosql_alergeno():
    alergeno = request.args.get("alergeno", "")
    sql = """SELECT id, nombre FROM productos
               WHERE atributos -> 'alergenos' @> %s::jsonb"""
    param = json.dumps([alergeno])
    try:
        rows = consultar(sql, [param])
        return jsonify(
            _sql=sql.strip(), _params=[param],
            _explica='Busca dentro del arreglo JSON "alergenos" de la tabla productos.',
            data=rows,
        )
    except Exception as e:
        return jsonify(_sql=sql.strip(), error=explicar_error(e)), 400


# =====================================================================
#  5) OPTIMIZACION / EXPLAIN
# =====================================================================
@app.route("/api/optimizacion/explain")
def optimizacion_explain():
    sql = "EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)\n" + SQL_REPORTE.replace("%s", "0")
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                plan = "\n".join(r[0] for r in cur.fetchall())
        finally:
            conn.close()
        return jsonify(_sql=sql.strip(), data=plan)
    except Exception as e:
        return jsonify(_sql=sql.strip(), error=explicar_error(e)), 500


@app.route("/api/optimizacion/indices")
def optimizacion_indices():
    sql = """SELECT indexname, tablename, indexdef
               FROM pg_indexes
               WHERE schemaname = 'public'
               ORDER BY tablename, indexname"""
    return jsonify(_sql=sql.strip(), data=consultar(sql))


# ---------------------------------------------------------------------
if __name__ == "__main__":
    print(f"\n  Restaurante API + Web (Python/Flask) corriendo en  http://localhost:{PORT}\n")
    app.run(host="0.0.0.0", port=PORT, debug=False)
