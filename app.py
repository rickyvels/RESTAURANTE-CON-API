# =====================================================================
#  RESTAURANTE - API (Flask + PostgreSQL)
#  ADAPTADO al esquema de la miss (tablas PRODUCTO, PEDIDO, CLIENTE, etc.)
#
#  Cada endpoint devuelve el SQL que ejecuto (campo "_sql") para que en
#  la demo se vea exactamente que consulta corrio (Consola SQL del panel).
#
#  MAPA RUBRICA -> ENDPOINT:
#    * CRUD simple + constraints     -> /api/productos  (PRODUCTO)
#    * CRUD complejo 3+ tablas + TX  -> POST /api/pedidos (PEDIDO+DETALLE_PEDIDO+PRODUCTO)
#    * Reporte GROUP BY/HAVING+export-> /api/reportes/ventas-por-sucursal
#    * NoSQL / JSONB                 -> /api/nosql/*  (PRODUCTO.datos_extra)
#    * Optimizacion / EXPLAIN        -> /api/optimizacion/*
# =====================================================================
import os
import io
import json
import csv

import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify, send_from_directory, Response
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
PORT = int(os.getenv("PORT", "3000"))

if DATABASE_URL and "supabase" in DATABASE_URL and "sslmode" not in DATABASE_URL:
    DATABASE_URL += ("&" if "?" in DATABASE_URL else "?") + "sslmode=require"

app = Flask(__name__, static_folder="public", static_url_path="")


def get_conn():
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
    return str(e).splitlines()[0] if str(e) else "Error desconocido."


def consultar(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or [])
            return cur.fetchall()
    finally:
        conn.close()


# =====================================================================
#  Frontend
# =====================================================================
@app.route("/")
def index():
    return send_from_directory("public", "index.html")


# =====================================================================
#  CATALOGOS (se devuelven con alias "id" y "nombre" para el frontend)
# =====================================================================
@app.route("/api/categorias")
def categorias():
    sql = "SELECT id_categoria AS id, nombre FROM categoria ORDER BY nombre"
    return jsonify(_sql=sql, data=consultar(sql))


@app.route("/api/clientes")
def clientes():
    sql = ("SELECT id_cliente AS id, nombre || ' ' || apellido AS nombre, email "
           "FROM cliente ORDER BY nombre")
    return jsonify(_sql=sql, data=consultar(sql))


@app.route("/api/mesas")
def mesas():
    sql = "SELECT id_mesa AS id, numero, capacidad, estado FROM mesa ORDER BY id_mesa"
    return jsonify(_sql=sql, data=consultar(sql))


@app.route("/api/empleados")
def empleados():
    sql = ("SELECT id_empleado AS id, nombre || ' ' || apellido AS nombre, rol "
           "FROM empleado ORDER BY nombre")
    return jsonify(_sql=sql, data=consultar(sql))


# =====================================================================
#  1) CRUD PRODUCTO  (CHECK / UNIQUE / NOT NULL en vivo)
# =====================================================================
@app.route("/api/productos", methods=["GET"])
def listar_productos():
    sql = """SELECT p.id_producto AS id, p.nombre, p.descripcion, p.precio, p.stock,
       c.nombre AS categoria, p.id_categoria AS categoria_id, p.datos_extra AS atributos
FROM producto p
LEFT JOIN categoria c ON c.id_categoria = p.id_categoria
ORDER BY p.id_producto"""
    try:
        return jsonify(_sql=sql.strip(), data=consultar(sql))
    except Exception as e:
        return jsonify(_sql=sql.strip(), error=explicar_error(e)), 500


@app.route("/api/productos", methods=["POST"])
def crear_producto():
    b = request.get_json(silent=True) or {}
    sql = """INSERT INTO producto (nombre, descripcion, precio, stock, id_categoria, datos_extra)
VALUES (%s, %s, %s, %s, %s, %s::jsonb)
RETURNING id_producto AS id, nombre, descripcion, precio, stock, id_categoria, datos_extra AS atributos"""
    params = [
        b.get("nombre"),
        b.get("descripcion") or None,
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
    sql = """UPDATE producto
SET nombre = %s, descripcion = %s, precio = %s, stock = %s, id_categoria = %s, datos_extra = %s::jsonb
WHERE id_producto = %s
RETURNING id_producto AS id, nombre, descripcion, precio, stock, id_categoria, datos_extra AS atributos"""
    params = [b.get("nombre"), b.get("descripcion") or None, b.get("precio"),
              b.get("stock"), b.get("categoria_id") or None,
              json.dumps(b.get("atributos") or {}), pid]
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
    sql = "DELETE FROM producto WHERE id_producto = %s RETURNING id_producto AS id, nombre"
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
#     Crear un pedido toca 3 tablas: PEDIDO + DETALLE_PEDIDO + PRODUCTO (stock)
#     Todo dentro de BEGIN ... COMMIT / ROLLBACK.
#     (PEDIDO exige id_cliente, id_empleado e id_mesa: son obligatorios.)
# =====================================================================
@app.route("/api/pedidos", methods=["POST"])
def crear_pedido():
    b = request.get_json(silent=True) or {}
    items = b.get("items")
    if not isinstance(items, list) or len(items) == 0:
        return jsonify(error="Debe agregar al menos un producto al pedido."), 400
    if not b.get("cliente_id") or not b.get("empleado_id") or not b.get("mesa_id"):
        return jsonify(error="El pedido necesita cliente, mesero y mesa (son obligatorios)."), 400

    pasos = []
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        pasos.append("BEGIN;")

        # 1) Cabecera del pedido
        cur.execute(
            """INSERT INTO PEDIDO (id_cliente, id_empleado, id_mesa, estado, total)
               VALUES (%s, %s, %s, 'Pendiente', 0) RETURNING id_pedido""",
            [b.get("cliente_id"), b.get("empleado_id"), b.get("mesa_id")],
        )
        pedido_id = cur.fetchone()["id_pedido"]
        pasos.append(
            f"-- cabecera\nINSERT INTO PEDIDO (id_cliente, id_empleado, id_mesa, estado, total) "
            f"VALUES ({b.get('cliente_id')}, {b.get('empleado_id')}, {b.get('mesa_id')}, 'Pendiente', 0);"
        )

        # 2) Por cada item: validar stock (FOR UPDATE), insertar detalle, descontar stock
        for it in items:
            cur.execute(
                "SELECT nombre, precio, stock FROM PRODUCTO WHERE id_producto = %s FOR UPDATE",
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

            subtotal = float(prod["precio"]) * int(it.get("cantidad"))
            cur.execute(
                """INSERT INTO DETALLE_PEDIDO (id_pedido, id_producto, cantidad, precio_unitario, subtotal)
                   VALUES (%s, %s, %s, %s, %s)""",
                [pedido_id, it.get("producto_id"), it.get("cantidad"), prod["precio"], subtotal],
            )
            pasos.append(
                f"-- linea\nINSERT INTO DETALLE_PEDIDO (id_pedido, id_producto, cantidad, precio_unitario, subtotal) "
                f"VALUES ({pedido_id}, {it.get('producto_id')}, {it.get('cantidad')}, {prod['precio']}, {subtotal});"
            )

            cur.execute(
                "UPDATE PRODUCTO SET stock = stock - %s WHERE id_producto = %s",
                [it.get("cantidad"), it.get("producto_id")],
            )
            pasos.append(
                f"-- descontar stock\nUPDATE PRODUCTO SET stock = stock - "
                f"{it.get('cantidad')} WHERE id_producto = {it.get('producto_id')};"
            )

        # 3) Recalcular total del pedido desde el detalle
        cur.execute(
            """UPDATE PEDIDO
               SET total = (SELECT COALESCE(SUM(subtotal),0) FROM DETALLE_PEDIDO WHERE id_pedido = %s)
               WHERE id_pedido = %s""",
            [pedido_id, pedido_id],
        )
        pasos.append(
            f"-- total\nUPDATE PEDIDO SET total = (SELECT SUM(subtotal) FROM DETALLE_PEDIDO "
            f"WHERE id_pedido = {pedido_id}) WHERE id_pedido = {pedido_id};"
        )

        conn.commit()
        pasos.append("COMMIT;")

        cur.execute("SELECT total FROM PEDIDO WHERE id_pedido = %s", [pedido_id])
        total = cur.fetchone()["total"]
        cur.close()
        return jsonify(_sql="\n".join(pasos), data={"id": pedido_id, "total": total}), 201
    except Exception as e:
        conn.rollback()
        pasos.append("ROLLBACK;  -- se revierte TODO")
        msg = str(e) if isinstance(e, ValueError) else explicar_error(e)
        return jsonify(_sql="\n".join(pasos), error=msg), 400
    finally:
        conn.close()


@app.route("/api/pedidos", methods=["GET"])
def listar_pedidos():
    sql = """SELECT p.id_pedido AS id, p.fecha_hora, p.estado, p.total,
       cl.nombre || ' ' || cl.apellido AS cliente,
       m.numero AS mesa,
       e.nombre || ' ' || e.apellido AS mesero
FROM PEDIDO p
LEFT JOIN CLIENTE  cl ON cl.id_cliente  = p.id_cliente
LEFT JOIN MESA     m  ON m.id_mesa       = p.id_mesa
LEFT JOIN EMPLEADO e  ON e.id_empleado   = p.id_empleado
ORDER BY p.id_pedido DESC"""
    return jsonify(_sql=sql.strip(), data=consultar(sql))


# =====================================================================
#  3) REPORTE: VENTAS POR SUCURSAL (GROUP BY / HAVING + JOIN 3 tablas)
#     Es el reporte de la miss (Restaurante_Reporte.sql), con exportacion.
#     formato = json (default) | csv | excel
# =====================================================================
SQL_REPORTE = """SELECT s.nombre                  AS sucursal,
       COUNT(DISTINCT p.id_pedido)     AS total_pedidos,
       COALESCE(SUM(p.total), 0)       AS total_ventas
FROM SUCURSAL s
LEFT JOIN MESA   m ON s.id_scrsal = m.id_scrsal
LEFT JOIN PEDIDO p ON m.id_mesa   = p.id_mesa
GROUP BY s.id_scrsal, s.nombre
HAVING COALESCE(SUM(p.total), 0) > %s
ORDER BY total_ventas DESC"""


@app.route("/api/reportes/ventas-por-sucursal")
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

    cab = ["sucursal", "total_pedidos", "total_ventas"]

    if formato == "csv":
        buf = io.StringIO()
        buf.write("\ufeff")  # BOM para acentos en Excel
        w = csv.writer(buf)
        w.writerow(["Sucursal", "Total pedidos", "Total ventas"])
        for r in rows:
            w.writerow([r[k] for k in cab])
        return Response(
            buf.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="ventas_por_sucursal.csv"'},
        )

    if formato == "excel":
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Ventas"
        ws.append(["Sucursal", "Total pedidos", "Total ventas"])
        for celda in ws[1]:
            celda.font = celda.font.copy(bold=True)
        for r in rows:
            ws.append([r["sucursal"], r["total_pedidos"], float(r["total_ventas"] or 0)])
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return Response(
            out.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="ventas_por_sucursal.xlsx"'},
        )

    return jsonify(error="Formato no soportado. Use json, csv o excel."), 400


# Reporte 2 (de la miss): productos mas vendidos
@app.route("/api/reportes/productos-mas-vendidos")
def reporte_productos():
    sql = """SELECT pr.nombre AS producto, SUM(dp.cantidad) AS unidades_vendidas
FROM PRODUCTO pr
JOIN DETALLE_PEDIDO dp ON pr.id_producto = dp.id_producto
GROUP BY pr.id_producto, pr.nombre
HAVING SUM(dp.cantidad) > 0
ORDER BY unidades_vendidas DESC"""
    return jsonify(_sql=sql.strip(), data=consultar(sql))


# =====================================================================
#  4) MODULO NoSQL / HIBRIDO (JSONB sobre PRODUCTO.datos_extra)
#     Operador ?  = "la clave/elemento existe en el JSON".
# =====================================================================
@app.route("/api/nosql/etiqueta")
def nosql_etiqueta():
    valor = request.args.get("valor", "")
    sql = """SELECT id_producto AS id, nombre, precio, datos_extra AS atributos
FROM PRODUCTO
WHERE datos_extra -> 'etiquetas' ? %s"""
    try:
        rows = consultar(sql, [valor])
        return jsonify(
            _sql=sql.strip(), _params=[valor],
            _explica='Tabla afectada: PRODUCTO (columna JSONB datos_extra). Busca en el arreglo "etiquetas".',
            data=rows,
        )
    except Exception as e:
        return jsonify(_sql=sql.strip(), error=explicar_error(e)), 400


@app.route("/api/nosql/alergeno")
def nosql_alergeno():
    valor = request.args.get("valor", "")
    sql = """SELECT id_producto AS id, nombre, precio, datos_extra AS atributos
FROM PRODUCTO
WHERE datos_extra -> 'alergenos' ? %s"""
    try:
        rows = consultar(sql, [valor])
        return jsonify(
            _sql=sql.strip(), _params=[valor],
            _explica='Busca dentro del arreglo JSON "alergenos" de la tabla PRODUCTO.',
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


if __name__ == "__main__":
    print(f"\n  Restaurante API + Web (Python/Flask) en  http://localhost:{PORT}\n")
    app.run(host="0.0.0.0", port=PORT, debug=False)
