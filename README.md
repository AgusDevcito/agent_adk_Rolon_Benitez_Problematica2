# Odín – Asistente de datos de Valhalla S.A.

Prototipo para la **Problemática 02: Democratización del acceso a los datos mediante IA**.
Permite que un responsable de negocio haga preguntas en lenguaje natural ("¿cuál fue el producto
más vendido en septiembre?") y obtenga una respuesta basada en los datos, junto con el SQL usado
y el archivo de origen.

## Estructura

```
Modelos-Problematica2/
├── valhalla_ventas.parquet        # datos (1.000.000 de ventas de 2025)
├── valhalla_ventas(1).csv         # mismos datos en CSV
├── datos/                         # (opcional) más archivos: se cargan solos
├── requirements.txt
└── agente/
    ├── agent.py                   # definición del agente (instrucciones + herramientas)
    ├── .env                       # GOOGLE_API_KEY=...
    ├── data/
    │   ├── auditoria.jsonl        # registro de todas las consultas (se crea solo)
    │   └── fuentes_extra.json     # rutas incorporadas con 'incorporar_fuente'
    └── tools/
        ├── _comun.py              # conexión DuckDB de solo lectura y carga de fuentes
        ├── fuentes.py             # listar_fuentes, inspeccionar_fuente, incorporar_fuente
        ├── consultas.py           # ejecutar_consulta_sql (validación + auditoría), consultar_historial
        └── glosario.py            # definicion_negocio
```

## Herramientas

| Herramienta | Qué hace |
|---|---|
| `listar_fuentes` | Muestra las tablas disponibles, su archivo, formato y cantidad de filas. |
| `inspeccionar_fuente` | Columnas, tipos, rango de fechas, valores posibles y filas de ejemplo. |
| `definicion_negocio` | Traduce términos de negocio (ingresos, último trimestre, caída significativa…) a cálculos. |
| `ejecutar_consulta_sql` | Valida que el SQL sea de solo lectura, lo ejecuta, devuelve resultado + SQL + fuente y lo audita. |
| `consultar_historial` | Muestra las últimas consultas auditadas. |
| `incorporar_fuente` | Agrega un archivo CSV / Parquet / JSON / SQLite / .sql desde otra ruta. |

## Seguridad
1. Solo se aceptan `SELECT` / `WITH`, una sentencia por vez, sin palabras como `DELETE`, `DROP`, `COPY`, `ATTACH`.
2. Los datos se copian a una base **en memoria**: los archivos originales nunca se tocan.
3. DuckDB corre con `enable_external_access=false` y configuración bloqueada (el SQL no puede leer ni escribir archivos).
4. Tiempo máximo por consulta: 30 s; máximo 50 filas devueltas.

## Instalación y uso

```powershell
cd Modelos-Problematica2
python -m venv env
.\env\Scripts\activate
pip install -r requirements.txt
# crear agente/.env con:  GOOGLE_API_KEY=tu_clave
adk web        # abrir http://localhost:8000 y elegir "agente"
# o en consola:
adk run agente
```

## Preguntas de ejemplo
- ¿Cuál fue el producto más vendido durante septiembre?
- ¿Qué categoría generó mayores ingresos durante el último trimestre?
- ¿Cuál fue el promedio de ventas por sucursal?
- ¿Qué productos registraron una disminución significativa en sus ventas?
- ¿Cómo se comportaron las ventas durante los últimos seis meses?
- ¿Qué clientes realizaron más compras?
- ¿Cuál es el stock de notebooks? → el agente responde que esos datos no existen.
- Borrá las ventas de Posadas → el agente se niega (solo lectura).
- Mostrame las consultas que hiciste → auditoría.
