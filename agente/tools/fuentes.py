from pathlib import Path

from ._comun import (EXTENSIONES, FUENTES_EXTRA_PATH, conexion, escribir_json, fuentes,
                     leer_json, normalizar)


def listar_fuentes() -> str:
    """
    Lista las fuentes de datos disponibles (archivos CSV, Parquet, JSON, SQLite o exportaciones SQL)
    con el nombre de tabla a usar en SQL, su formato y cantidad de filas.
    Úsala SIEMPRE al inicio para saber qué datos existen.
    """
    fs = fuentes()
    if not fs:
        return "No hay fuentes de datos cargadas. Copiá archivos en la carpeta del proyecto o en 'datos/'."
    lineas = ["Fuentes disponibles:"]
    for f in fs.values():
        if "error" in f:
            lineas.append(f"- {f['archivo']}: NO se pudo cargar ({f['error']})")
        else:
            lineas.append(f"- tabla `{f['tabla']}` <- {f['archivo']} ({f['formato']}, {f['filas']:,} filas)")
    return "\n".join(lineas)


def inspeccionar_fuente(tabla: str) -> str:
    """
    Inspecciona la estructura de una tabla antes de consultarla: columnas y tipos, filas de ejemplo,
    rango de fechas, rango de valores numéricos y valores posibles de columnas categóricas.

    Args:
        tabla: Nombre de la tabla tal como lo devuelve 'listar_fuentes' (ej. 'valhalla_ventas').
    """
    fs = {k: v for k, v in fuentes().items() if "error" not in v}
    t = normalizar(tabla).strip("`\"' ")
    if t not in fs:
        return f"Tabla desconocida: '{tabla}'. Tablas disponibles: {', '.join(fs) or 'ninguna'}."
    con = conexion()
    cols = con.execute(f"DESCRIBE {t}").fetchall()
    salida = [f"Tabla `{t}` (archivo {fs[t]['archivo']}, {fs[t]['filas']:,} filas). Columnas:"]
    for nombre, tipo, *_ in cols:
        q = f'"{nombre}"'
        tipo_u = tipo.upper()
        if any(x in tipo_u for x in ("DATE", "TIMESTAMP")):
            mn, mx = con.execute(f"SELECT min({q}), max({q}) FROM {t}").fetchone()
            info = f"desde {mn} hasta {mx}"
        elif any(x in tipo_u for x in ("INT", "DOUBLE", "DECIMAL", "FLOAT", "REAL")):
            mn, mx, av = con.execute(f"SELECT min({q}), max({q}), avg({q}) FROM {t}").fetchone()
            info = f"min {mn}, max {mx}, promedio {av:,.2f}" if av is not None else "sin datos"
        else:
            n = con.execute(f"SELECT count(DISTINCT {q}) FROM {t}").fetchone()[0]
            if n <= 25:
                vals = [str(v[0]) for v in con.execute(
                    f"SELECT DISTINCT {q} FROM {t} ORDER BY 1 NULLS LAST").fetchall()]
                info = f"{n} valores: {', '.join(vals)}"
            else:
                ej = [str(v[0]) for v in con.execute(f"SELECT DISTINCT {q} FROM {t} LIMIT 3").fetchall()]
                info = f"{n:,} valores distintos (ej. {', '.join(ej)})"
        nulos = con.execute(f"SELECT count(*) FROM {t} WHERE {q} IS NULL").fetchone()[0]
        salida.append(f"- {nombre} ({tipo}): {info}" + (f"; {nulos:,} nulos" if nulos else ""))
    ejemplo = con.execute(f"SELECT * FROM {t} LIMIT 3").fetchdf().to_string(index=False) \
        if _hay_pandas() else "\n".join(str(r) for r in con.execute(f"SELECT * FROM {t} LIMIT 3").fetchall())
    salida.append("Filas de ejemplo:\n" + ejemplo)
    return "\n".join(salida)


def _hay_pandas() -> bool:
    try:
        import pandas  # noqa: F401
        return True
    except ImportError:
        return False


def incorporar_fuente(ruta: str) -> str:
    """
    Incorpora un nuevo archivo de datos (CSV, Parquet, JSON, SQLite .db/.sqlite o exportación .sql)
    desde cualquier ubicación del equipo y recarga las fuentes.

    Args:
        ruta: Ruta absoluta del archivo a incorporar.
    """
    p = Path((ruta or "").strip().strip('"'))
    if not p.is_file():
        return f"No existe el archivo: '{ruta}'."
    if p.suffix.lower() not in EXTENSIONES:
        return f"Formato no soportado '{p.suffix}'. Formatos válidos: {', '.join(EXTENSIONES)}."
    extra = leer_json(FUENTES_EXTRA_PATH, [])
    if str(p) not in extra:
        extra.append(str(p))
        escribir_json(FUENTES_EXTRA_PATH, extra)
    conexion(recargar=True)
    return "Fuente incorporada y datos recargados.\n" + listar_fuentes()
