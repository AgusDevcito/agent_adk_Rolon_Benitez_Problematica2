"""Base de conocimiento de negocio: cómo traducir términos de la empresa a cálculos sobre los datos."""
from ._comun import normalizar

GLOSARIO = {
    "ingresos": "Facturación = SUM(total). 'total' ya incluye el descuento: cantidad * precio_unitario * (1 - descuento).",
    "mas vendido": "Producto más vendido = mayor SUM(cantidad) (unidades). Si el usuario habla de dinero, usar SUM(total) y aclararlo.",
    "ventas": "Una 'venta' es una fila (venta_id). Cantidad de ventas = COUNT(*); unidades = SUM(cantidad); monto = SUM(total).",
    "ticket promedio": "Ticket promedio = AVG(total) por venta.",
    "promedio por sucursal": "Promedio de ventas por sucursal: por defecto AVG(total) agrupado por sucursal. "
                             "Si piden promedio mensual, primero sumar por sucursal y mes y luego promediar.",
    "periodo": "Las fechas disponibles se ven con 'inspeccionar_fuente'. Los períodos relativos ('último trimestre', "
               "'últimos seis meses') se calculan respecto de la ÚLTIMA fecha con datos (MAX(fecha)), no de hoy.",
    "trimestre": "Q1 = ene-mar, Q2 = abr-jun, Q3 = jul-sep, Q4 = oct-dic. Usar quarter(fecha) en DuckDB.",
    "mes": "Para filtrar un mes usar month(fecha) = N (y year(fecha) si hay varios años). Para series usar date_trunc('month', fecha).",
    "disminucion significativa": "Comparar un período contra el anterior (ej. último trimestre vs. el previo) por producto y "
                                 "calcular variación % = (actual - anterior) / anterior * 100. Se considera significativa "
                                 "una caída de 10% o más, salvo que el usuario indique otro umbral.",
    "comportamiento": "Comportamiento/evolución de ventas = serie mensual de SUM(total) y COUNT(*), ordenada por mes.",
    "mejores clientes": "Clientes con más compras = COUNT(*) por cliente_id (cantidad de compras); si piden 'que más gastaron', SUM(total). "
                        "Los datos solo tienen el ID del cliente, no su nombre.",
    "descuento": "La columna descuento es una proporción (0.2 = 20%). Monto descontado = cantidad * precio_unitario * descuento.",
    "canal": "Canal de venta: E-commerce, Marketplace o Tienda fisica.",
    "metodo de pago": "Columna metodo_pago (Efectivo, Tarjeta de credito, Tarjeta de debito, Transferencia, etc.).",
    "sucursal": "Cada sucursal pertenece a una provincia (columnas sucursal y provincia).",
    "fuentes duplicadas": "valhalla_ventas (Parquet) y valhalla_ventas_1 (CSV) contienen los MISMOS datos en distinto formato. "
                          "Usar solo una (preferir la Parquet, es más rápida) para no duplicar resultados.",
}

ALIAS = {
    "facturacion": "ingresos", "ganancia": "ingresos", "recaudacion": "ingresos", "monto": "ingresos",
    "top": "mas vendido", "producto mas vendido": "mas vendido", "ranking": "mas vendido",
    "ultimo trimestre": "periodo", "ultimos meses": "periodo", "ultimos seis meses": "periodo", "fecha": "periodo",
    "caida": "disminucion significativa", "baja": "disminucion significativa", "disminucion": "disminucion significativa",
    "evolucion": "comportamiento", "tendencia": "comportamiento", "clientes": "mejores clientes",
    "pago": "metodo de pago", "duplicado": "fuentes duplicadas", "csv": "fuentes duplicadas",
    "promedio": "promedio por sucursal",
}


def definicion_negocio(termino: str = "") -> str:
    """
    Explica cómo se calcula un concepto de negocio con los datos (ingresos, producto más vendido,
    último trimestre, disminución significativa, mejores clientes, etc.). Úsala ante preguntas con
    términos ambiguos ANTES de escribir el SQL.

    Args:
        termino: Concepto a consultar. Vacío = lista todos los conceptos.
    """
    t = normalizar(termino)
    if not t:
        return "Conceptos definidos:\n" + "\n".join(f"- {k}: {v}" for k, v in GLOSARIO.items())
    clave = t if t in GLOSARIO else ALIAS.get(t)
    if not clave:
        clave = next((k for k in GLOSARIO if k in t or t in k), None) or \
                next((v for a, v in ALIAS.items() if a in t), None)
    if not clave:
        return (f"No hay una definición oficial para '{termino}'. Conceptos disponibles: "
                f"{', '.join(GLOSARIO)}. Si es ambiguo, pedí al usuario que lo aclare.")
    return f"{clave}: {GLOSARIO[clave]}"
