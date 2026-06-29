-- =====================================================================
--  Restaurante_Transacciones_CORREGIDO.sql
--  Transacciones ACID (BEGIN ... COMMIT / ROLLBACK).
--
--  QUE SE ARREGLO respecto al original:
--   * Ya NO se pone id_pedido = 1 a mano. id_pedido es SERIAL, asi que el
--     pedido nuevo no es el 1. Se usa currval('pedido_id_pedido_seq') que
--     devuelve el id que ACABA de generar esta misma sesion para ESA
--     secuencia (a diferencia de LASTVAL(), que toma cualquier secuencia).
--   * Numero de factura unico ('FAC-T01') para no chocar con el CRUD.
-- =====================================================================


-- ---------------------------------------------------------------------
-- TRANSACCION 1: REGISTRAR UN PEDIDO  (3 tablas: PEDIDO, DETALLE_PEDIDO, PRODUCTO)
-- ---------------------------------------------------------------------
BEGIN;

INSERT INTO PEDIDO (id_cliente, id_empleado, id_mesa, estado, total)
VALUES (1, 2, 3, 'Pendiente', 0);

INSERT INTO DETALLE_PEDIDO (id_pedido, id_producto, cantidad, precio_unitario, subtotal)
VALUES (currval('pedido_id_pedido_seq'), 10, 2, 15.00, 30.00);

UPDATE PRODUCTO SET stock = stock - 2 WHERE id_producto = 10;
UPDATE MESA     SET estado = 'Ocupada' WHERE id_mesa = 3;

UPDATE PEDIDO
SET total = (SELECT COALESCE(SUM(subtotal), 0) FROM DETALLE_PEDIDO
             WHERE id_pedido = currval('pedido_id_pedido_seq'))
WHERE id_pedido = currval('pedido_id_pedido_seq');

COMMIT;
-- Si algo fallara, en lugar de COMMIT iria:  ROLLBACK;  (se revierte TODO)


-- ---------------------------------------------------------------------
-- TRANSACCION 2: REGISTRAR UN PAGO Y SU FACTURA  (PAGO, FACTURA, PEDIDO)
-- ---------------------------------------------------------------------
BEGIN;

INSERT INTO PAGO (monto, metodo, fcha_pago, estado, id_pedido)
VALUES (150.00, 'tarjeta debito', CURRENT_DATE, 'completado', 5);

INSERT INTO FACTURA (numero, fecha_emision, monto_total, id_pago)
VALUES ('FAC-T01', CURRENT_DATE, 150.00, currval('pago_id_pago_seq'));

UPDATE PEDIDO SET estado = 'Pagado' WHERE id_pedido = 5;

COMMIT;
