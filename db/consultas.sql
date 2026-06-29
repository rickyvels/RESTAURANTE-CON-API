-- =====================================================================
--  CONSULTAS.SQL  -  Catalogo de las consultas que usa la pagina web.
--  (Esquema de la miss: PRODUCTO, PEDIDO, DETALLE_PEDIDO, datos_extra, etc.)
--
--  En la pagina, cada accion muestra abajo (Consola SQL) la consulta exacta
--  que se ejecuto. Esta es la "chuleta" por si la miss pregunta.
-- =====================================================================


-- #########################################################
-- # 1) CRUD de PRODUCTO  (Integridad: CHECK / UNIQUE / NOT NULL)
-- #    Pantalla "Carta (CRUD)"
-- #########################################################

-- [GET /api/productos]
SELECT p.id_producto AS id, p.nombre, p.descripcion, p.precio, p.stock,
       c.nombre AS categoria, p.id_categoria AS categoria_id, p.datos_extra AS atributos
FROM producto p
LEFT JOIN categoria c ON c.id_categoria = p.id_categoria
ORDER BY p.id_producto;

-- [POST /api/productos]  -> aqui se disparan UNIQUE(nombre), CHECK(precio>0),
--                           CHECK(stock>=0) y NOT NULL(nombre)
INSERT INTO producto (nombre, descripcion, precio, stock, id_categoria, datos_extra)
VALUES ($1, $2, $3, $4, $5, $6::jsonb)
RETURNING *;

-- [PUT /api/productos/:id]
UPDATE producto
SET nombre = $1, descripcion = $2, precio = $3, stock = $4, id_categoria = $5, datos_extra = $6::jsonb
WHERE id_producto = $7
RETURNING *;

-- [DELETE /api/productos/:id]
DELETE FROM producto WHERE id_producto = $1 RETURNING id_producto, nombre;


-- #########################################################
-- # 2) PEDIDO = CRUD complejo (3 tablas) + TRANSACCION ACID
-- #    Pantalla "Registrar venta"  -> [POST /api/pedidos]
-- #########################################################
BEGIN;

  -- cabecera
  INSERT INTO PEDIDO (id_cliente, id_empleado, id_mesa, estado, total)
  VALUES ($1, $2, $3, 'Pendiente', 0)
  RETURNING id_pedido;

  -- por cada producto: se bloquea la fila, se valida stock, se inserta detalle y se descuenta stock
  SELECT nombre, precio, stock FROM PRODUCTO WHERE id_producto = $1 FOR UPDATE;
  INSERT INTO DETALLE_PEDIDO (id_pedido, id_producto, cantidad, precio_unitario, subtotal)
  VALUES ($1, $2, $3, $4, $5);
  UPDATE PRODUCTO SET stock = stock - $1 WHERE id_producto = $2;

  -- recalcular total
  UPDATE PEDIDO
  SET total = (SELECT COALESCE(SUM(subtotal),0) FROM DETALLE_PEDIDO WHERE id_pedido = $1)
  WHERE id_pedido = $1;

COMMIT;
-- Si un producto no tiene stock suficiente:  ROLLBACK;  (no se guarda nada)

-- [GET /api/pedidos]  (JOIN de 4 tablas)
SELECT p.id_pedido AS id, p.fecha_hora, p.estado, p.total,
       cl.nombre || ' ' || cl.apellido AS cliente,
       m.numero AS mesa,
       e.nombre || ' ' || e.apellido AS mesero
FROM PEDIDO p
LEFT JOIN CLIENTE  cl ON cl.id_cliente  = p.id_cliente
LEFT JOIN MESA     m  ON m.id_mesa       = p.id_mesa
LEFT JOIN EMPLEADO e  ON e.id_empleado   = p.id_empleado
ORDER BY p.id_pedido DESC;


-- #########################################################
-- # 3) REPORTES  (GROUP BY / HAVING + JOIN + exportacion)
-- #    Pantalla "Reportes"
-- #########################################################

-- [GET /api/reportes/ventas-por-sucursal?min=...&formato=json|csv|excel]
SELECT s.nombre AS sucursal,
       COUNT(DISTINCT p.id_pedido) AS total_pedidos,
       COALESCE(SUM(p.total), 0)   AS total_ventas
FROM SUCURSAL s
LEFT JOIN MESA   m ON s.id_scrsal = m.id_scrsal
LEFT JOIN PEDIDO p ON m.id_mesa   = p.id_mesa
GROUP BY s.id_scrsal, s.nombre
HAVING COALESCE(SUM(p.total), 0) > $1
ORDER BY total_ventas DESC;

-- [GET /api/reportes/productos-mas-vendidos]
SELECT pr.nombre AS producto, SUM(dp.cantidad) AS unidades_vendidas
FROM PRODUCTO pr
JOIN DETALLE_PEDIDO dp ON pr.id_producto = dp.id_producto
GROUP BY pr.id_producto, pr.nombre
HAVING SUM(dp.cantidad) > 0
ORDER BY unidades_vendidas DESC;


-- #########################################################
-- # 4) NoSQL / JSONB  (PRODUCTO.datos_extra, operador ?)
-- #    Pantalla "Modulo NoSQL"
-- #########################################################

-- [GET /api/nosql/etiqueta?valor=sin gluten]
SELECT id_producto AS id, nombre, precio, datos_extra AS atributos
FROM PRODUCTO
WHERE datos_extra -> 'etiquetas' ? $1;

-- [GET /api/nosql/alergeno?valor=pescado]
SELECT id_producto AS id, nombre, precio, datos_extra AS atributos
FROM PRODUCTO
WHERE datos_extra -> 'alergenos' ? $1;


-- #########################################################
-- # 5) OPTIMIZACION / INDICES
-- #    Pantalla "Optimizacion"
-- #########################################################

-- [GET /api/optimizacion/indices]
SELECT indexname, tablename, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- [GET /api/optimizacion/explain]  -> plan del reporte de ventas por sucursal
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT s.nombre, COUNT(DISTINCT p.id_pedido), COALESCE(SUM(p.total),0)
FROM SUCURSAL s
LEFT JOIN MESA m ON s.id_scrsal = m.id_scrsal
LEFT JOIN PEDIDO p ON m.id_mesa = p.id_mesa
GROUP BY s.id_scrsal, s.nombre
HAVING COALESCE(SUM(p.total),0) > 0
ORDER BY 3 DESC;
