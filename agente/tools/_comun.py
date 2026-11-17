"""Utilidades compartidas: rutas, conexión DuckDB de solo lectura y registro de fuentes."""
import json
import re
import threading
import unicodedata
from pathlib import Path

import duckdb

BASE_DIR = Path(__file__).resolve().parents[2]          # carpeta Modelos-Problematica2
AGENTE_DIR = Path(__file__).resolve().parents[1]
DATOS_DIRS = [BASE_DIR, BASE_DIR / "datos"]             # donde se buscan archivos de datos
FUENTES_EXTRA_PATH = AGENTE_DIR / "data" / "fuentes_extra.json"
AUDITORIA_PATH = AGENTE_DIR / "data" / "auditoria.jsonl"

EXTENSIONES = {".csv": "CSV", ".parquet": "Parquet", ".json": "JSON", ".jsonl": "JSON",
               ".db": "SQLite", ".sqlite": "SQLite", ".sql": "SQL"}

_lock = threading.Lock()
_con = None
_fuentes: dict[str, dict] = {}


def normalizar(texto) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return texto.lower().strip()


def nombre_tabla(path: Path) -> str:
    n = re.sub(r"[^a-z0-9]+", "_", normalizar(path.stem)).strip("_")
    return n if n and not n[0].isdigit() else f"t_{n}"


def leer_json(path: Path, defecto):
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8") or "null") or defecto


def escribir_json(path: Path, datos) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def _descubrir_archivos() -> list[Path]:
    archivos = []
    for d in DATOS_DIRS:
        if d.exists():
            archivos += [p for p in d.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONES]
    archivos += [Path(p) for p in leer_json(FUENTES_EXTRA_PATH, []) if Path(p).exists()]
    return sorted(set(archivos))


def _cargar(con, path: Path) -> list[str]:
    """Carga un archivo como tabla(s) en memoria. Devuelve los nombres de tabla creados."""
    ext, ruta = path.suffix.lower(), str(path).replace("'", "''")
    base = nombre_tabla(path)
    if ext == ".csv":
        con.execute(f"CREATE TABLE {base} AS SELECT * FROM read_csv_auto('{ruta}')")
    elif ext == ".parquet":
        con.execute(f"CREATE TABLE {base} AS SELECT * FROM read_parquet('{ruta}')")
    elif ext in {".json", ".jsonl"}:
        con.execute(f"CREATE TABLE {base} AS SELECT * FROM read_json_auto('{ruta}')")
    elif ext in {".db", ".sqlite"}:
        con.execute("INSTALL sqlite; LOAD sqlite;")
        con.execute(f"ATTACH '{ruta}' AS src (TYPE sqlite, READ_ONLY)")
        creadas = []
        for (t,) in con.execute("SELECT name FROM src.sqlite_master WHERE type='table'").fetchall():
            nt = f"{base}_{nombre_tabla(Path(t))}"
            con.execute(f'CREATE TABLE {nt} AS SELECT * FROM src."{t}"')
            creadas.append(nt)
        con.execute("DETACH src")
        return creadas
    elif ext == ".sql":
        # Exportaciones de consultas SQL (CREATE TABLE + INSERT) se ejecutan en un esquema aislado.
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {base}")
        con.execute(f"SET schema='{base}'")
        con.execute(path.read_text(encoding="utf-8"))
        con.execute("SET schema='main'")
        return [f"{base}.{t}" for (t,) in con.execute(
            f"SELECT table_name FROM information_schema.tables WHERE table_schema='{base}'").fetchall()]
    return [base]


def conexion(recargar: bool = False):
    """Conexión DuckDB en memoria con todas las fuentes cargadas y acceso externo bloqueado."""
    global _con, _fuentes
    with _lock:
        if _con is not None and not recargar:
            return _con
        con = duckdb.connect(":memory:")
        fuentes = {}
        for path in _descubrir_archivos():
            try:
                for t in _cargar(con, path):
                    filas = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                    fuentes[t] = {"tabla": t, "archivo": path.name, "ruta": str(path),
                                  "formato": EXTENSIONES[path.suffix.lower()], "filas": filas}
            except Exception as e:  # una fuente rota no debe tumbar al resto
                fuentes[f"error:{path.name}"] = {"archivo": path.name, "error": str(e)}
        # Seguridad: desde aquí el SQL no puede leer/escribir archivos ni cambiar configuración.
        con.execute("SET enable_external_access = false")
        con.execute("SET lock_configuration = true")
        if _con is not None:
            _con.close()
        _con, _fuentes = con, fuentes
        return _con


def fuentes() -> dict[str, dict]:
    conexion()
    return _fuentes
