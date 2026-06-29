-- =====================================================================
--  Restaurante_Crud_CORREGIDO.sql
--  Operaciones CRUD que tocan varias tablas.
--
--  QUE SE ARREGLO respecto al original:
--   * Se reemplazo LASTVAL() por currval('<secuencia>'). LASTVAL() devuelve
--     el ultimo valor de CUALQUIER secuencia de la sesion, por eso despues de
--     insertar en DETALLE_COMPRA ya no apuntaba al id_compra correcto.
--     currval con el nombre exacto de la secuencia siempre da el id correcto.
--   * Numero de factura unico ('FAC-C01') para no chocar con transacciones.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) Registrar PAGO + FACTURA del pedido 5
-- ---------------------------------------------------------------------
INSERT INTO PAGO (monto, metodo, fcha_pago, estado, id_pedido)
VALUES (150.00, 'tarjeta debito', CURRENT_DATE, 'completado', 5);

INSERT INTO FACTURA (numero, fecha_emision, monto_total, id_pago)
VALUES ('FAC-C01', CURRENT_DATE, 150.00, currval('pago_id_pago_seq'));

UPDATE PEDIDO SET estado = 'Pagado' WHERE id_pedido = 5;

-- ---------------------------------------------------------------------
-- 2) Registrar COMPRA + DETALLE_COMPRA, sumar stock y recalcular total
--    (3 tablas: COMPRA, DETALLE_COMPRA, PRODUCTO)
-- ---------------------------------------------------------------------
INSERT INTO COMPRA (fecha, total, estado, id_scrsal, id_prvdor)
VALUES (CURRENT_DATE, 0, 'recibido', 1, 1);

INSERT INTO DETALLE_COMPRA (cantidad, subtotal, precio_unitario, id_producto, id_compra)
VALUES (36, 36 * 8.00, 8.00, 10, currval('compra_id_compra_seq'));

UPDATE PRODUCTO SET stock = stock + 36 WHERE id_producto = 10;

UPDATE COMPRA
SET total = (SELECT SUM(subtotal) FROM DETALLE_COMPRA
             WHERE id_compra = currval('compra_id_compra_seq'))
WHERE id_compra = currval('compra_id_compra_seq');
