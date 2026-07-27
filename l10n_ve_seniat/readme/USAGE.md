# Usage

Notas de crédito y débito
-------------------------

1. Abra una factura de cliente o de proveedor publicada.
2. Use **Nota de crédito** (reversión) o **Nota de Debito** según corresponda.
3. En **ventas**, aplican las reglas SENIAT de emisión, montos y productos.
4. En **proveedor**, el registro es más libre: puede cambiar moneda, impuestos y
   montos distintos a la factura origen (sin tope SENIAT de NC ni forzar bolívares).
5. Si tras una nota de crédito total de cliente queda una ND sin revertir,
   use el asistente **Nota de crédito por ND**.

Las notas reutilizan el mismo diario y contacto de la factura origen.


## Descuento en borrador

En facturas en borrador (VE), use el botón **Descuento** junto a los totales
para aplicar un descuento global con motivo, porcentaje o monto fijo.

## Descuento post-factura

En facturas de cliente confirmadas (VE), use el botón **Descuento** del
encabezado para generar una nota de crédito en borrador:

1. Seleccione el motivo (Pronto pago, Pago en divisas, Descuento comercial, etc.).
2. Indique porcentaje sobre el subtotal sin IVA o un monto fijo.
3. Confirme para crear la nota de crédito con impuestos proporcionales.
4. Revise y publique la nota de crédito.

Puede generar varias notas de crédito de descuento mientras quede subtotal
disponible.
