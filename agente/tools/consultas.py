import json
import re
import threading
import time
from datetime import datetime

from google.adk.tools.tool_context import ToolContext

from ._comun import AUDITORIA_PATH, conexion, fuentes

MAX_FILAS = 50
TIMEOUT_SEG = 30
PROHIBIDAS = ["insert", "update", "delete", "drop", "create", "alter", "truncate", "merge",
              "copy", "attach", "detach", "install", "load", "pragma", "set", "reset", "call", "export",
              "import", "vacuum", "checkpoint", "grant", "revoke", "use"]
FUNCIONES_PROHIBIDAS = ["read_csv", "read_parquet", "read_json", "read_text", "read_blob", "glob",
                        "sqlite_scan", "parquet_scan", "query_table", "getenv"]


def validar_sql(sql: str) -> str | None:
    """Devuelve un mensaje de error si la consulta no es de solo lectura; None si es válida."""
    limpio = re.sub(r"--[^\n]*|/\*.*?\*/", " ", sql or "", flags=re.S).strip().rstrip(";").strip()
    if not limpio:
        return "La consulta está vacía."
    sin_strings = re.sub(r"'(?:[^']|'')*'", "''", limpio)
    if ";" in sin_strings:
        return "Solo se permite UNA sentencia por consulta."
    if not re.match(r"^(select|with)\b", sin_strings, re.I):
        return "Solo se permiten consultas de lectura (SELECT o WITH ... SELECT)."
    palabras = set(re.findall(r"[a-z_]+", sin_strings.lower()))
    if bad := sorted(palabras & set(PROHIBIDAS)):
        return f"Operación no autorizada: {', '.join(bad).upper()}. El asistente solo puede leer datos."
    if bad := sorted(palabras & set(FUNCIONES_PROHIBIDAS)):
        return f"Función no permitida: {', '.join(bad)}. Consultá solo las tablas registradas."
    return None


def _auditar(registro: dict) -> None:
    AUDITORIA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDITORIA_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")


def _formatear(columnas, filas) -> str:
    def fmt(v):
        if isinstance(v, float):
            return f"{v:,.2f}"
        return str(v)
    cab = " | ".join(columnas)
    return "\n".join([cab, "-" * len(cab)] + [" | ".join(fmt(v) for v in f) for f in filas])


def ejecutar_consulta_sql(sql: str, pregunta: str, tool_context: ToolContext = None) -> str:
    """
    Ejecuta una consulta SQL de SOLO LECTURA (dialecto DuckDB) sobre las tablas registradas y devuelve
    el resultado junto con la consulta utilizada y las fuentes de origen. Toda ejecución queda auditada.

    Args:
        sql: Consulta SELECT (o WITH ... SELECT). Usar los nombres de tabla de 'listar_fuentes'.
        pregunta: La pregunta del usuario en lenguaje natural que motiva la consulta (para auditoría).
    """
    registro = {"fecha": datetime.now().isoformat(timespec="seconds"), "pregunta": pregunta, "sql": sql}
    if error := validar_sql(sql):
        registro.update(estado="RECHAZADA", detalle=error)
        _auditar(registro)
        return f"Consulta rechazada: {error}"

    con = conexion()
    cur = con.cursor()
    timer = threading.Timer(TIMEOUT_SEG, cur.interrupt)
    inicio = time.perf_counter()
    try:
        timer.start()
        res = cur.execute(sql.strip().rstrip(";"))
        columnas = [d[0] for d in res.description]
        filas = res.fetchmany(MAX_FILAS + 1)
    except Exception as e:
        registro.update(estado="ERROR", detalle=str(e))
        _auditar(registro)
        return f"Error al ejecutar la consulta: {e}. Revisá nombres de columnas con 'inspeccionar_fuente'."
    finally:
        timer.cancel()
        cur.close()
    ms = round((time.perf_counter() - inicio) * 1000)

    truncado = len(filas) > MAX_FILAS
    filas = filas[:MAX_FILAS]
    tablas = [t for t, f in fuentes().items() if "error" not in f and re.search(rf"\b{re.escape(t)}\b", sql, re.I)]
    origen = ", ".join(f"{t} ({fuentes()[t]['archivo']})" for t in tablas) or "desconocido"

    registro.update(estado="OK", filas=len(filas), ms=ms, fuentes=tablas)
    _auditar(registro)
    if tool_context is not None:
        hist = list(tool_context.state.get("consultas_sesion", []))[-9:]
        hist.append({"pregunta": pregunta, "sql": sql})
        tool_context.state["consultas_sesion"] = hist

    if not filas:
        cuerpo = "La consulta no devolvió resultados (puede que no haya datos para ese filtro)."
    else:
        cuerpo = _formatear(columnas, filas)
        if truncado:
            cuerpo += f"\n(Se muestran solo las primeras {MAX_FILAS} filas.)"
    return (f"Resultado ({len(filas)} fila/s, {ms} ms):\n{cuerpo}\n\n"
            f"SQL ejecutado:\n```sql\n{sql.strip()}\n```\nFuente de los datos: {origen}")


def consultar_historial(cantidad: int = 5) -> str:
    """
    Muestra las últimas consultas ejecutadas (auditoría): fecha, pregunta, SQL, estado y fuentes.

    Args:
        cantidad: Cuántas consultas mostrar (1 a 20, por defecto 5).
    """
    cantidad = max(1, min(int(cantidad or 5), 20))
    if not AUDITORIA_PATH.exists():
        return "Todavía no se ejecutó ninguna consulta."
    regs = [json.loads(l) for l in AUDITORIA_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    salida = [f"Últimas {min(cantidad, len(regs))} consultas auditadas:"]
    for r in regs[-cantidad:]:
        salida.append(f"- [{r['fecha']}] {r['estado']} | \"{r.get('pregunta', '')}\"\n  SQL: {r['sql']}"
                      + (f"\n  Detalle: {r['detalle']}" if r.get("detalle") else ""))
    return "\n".join(salida)
