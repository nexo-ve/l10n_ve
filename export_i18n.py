#!/usr/bin/env python3
import argparse
import configparser
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_LANG = "es_VE"
DEFAULT_ODOO_BIN = Path("/workspace/odoo/odoo-bin")
DEFAULT_ODOO_CONF = Path("/workspace/jrhomo.conf")


def discover_modules():
    modules = []
    for path in sorted(REPO_ROOT.iterdir()):
        if path.is_dir() and (path / "__manifest__.py").is_file():
            modules.append(path.name)
    return modules


def read_db_config(conf_path):
    config = configparser.ConfigParser()
    config.read(conf_path)
    section = config["options"] if config.has_section("options") else {}
    return {
        "host": section.get("db_host", "localhost"),
        "port": section.get("db_port", "5432"),
        "user": section.get("db_user", "odoo"),
        "password": section.get("db_password", "odoo"),
    }


def psql_query(db_config, database, query):
    env = os.environ.copy()
    if db_config["password"]:
        env["PGPASSWORD"] = db_config["password"]
    cmd = [
        "psql",
        "-h",
        db_config["host"],
        "-p",
        db_config["port"],
        "-U",
        db_config["user"],
        "-d",
        database,
        "-tAc",
        query,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def list_databases(db_config):
    output = psql_query(
        db_config,
        "postgres",
        "SELECT datname FROM pg_database WHERE datistemplate = false AND datallowconn = true ORDER BY datname",
    )
    if not output:
        return []
    return [line.strip() for line in output.splitlines() if line.strip() and line.strip() != "postgres"]


def detect_database(db_config, repo_modules):
    if not repo_modules:
        return None
    module_list = ",".join(f"'{module}'" for module in repo_modules)
    best_db = None
    best_count = -1
    for database in list_databases(db_config):
        count = psql_query(
            db_config,
            database,
            f"SELECT COUNT(*) FROM ir_module_module WHERE state = 'installed' AND name IN ({module_list})",
        )
        if count is None:
            continue
        count = int(count)
        if count > best_count:
            best_count = count
            best_db = database
    return best_db if best_count > 0 else None


def get_installed_modules(db_config, database, repo_modules):
    module_list = ",".join(f"'{module}'" for module in repo_modules)
    output = psql_query(
        db_config,
        database,
        f"SELECT name FROM ir_module_module WHERE state = 'installed' AND name IN ({module_list}) ORDER BY name",
    )
    if not output:
        return set()
    return {line.strip() for line in output.splitlines() if line.strip()}


def ensure_language(db_config, database, lang):
    active = psql_query(
        db_config,
        database,
        f"SELECT active FROM res_lang WHERE code = '{lang}'",
    )
    if active is None:
        print(f"ERROR: No se encontró el idioma {lang} en la base de datos {database}.")
        sys.exit(1)
    if active != "t":
        print(f"ERROR: El idioma {lang} existe pero no está activo en {database}.")
        sys.exit(1)


def export_module(odoo_bin, odoo_conf, database, module, lang, output_path):
    cmd = [
        sys.executable,
        str(odoo_bin),
        "-c",
        str(odoo_conf),
        "-d",
        database,
        "-l",
        lang,
        f"--i18n-export={output_path}",
        f"--modules={module}",
        "--stop-after-init",
        "--log-level=warn",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=odoo_bin.parent.parent)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        return False, stderr
    if not output_path.exists() or output_path.stat().st_size == 0:
        return False, "El archivo exportado está vacío."
    return True, ""


def merge_po(existing_path, exported_path, lang):
    if existing_path.exists():
        cmd = [
            "msgmerge",
            "-U",
            str(existing_path),
            str(exported_path),
            "--backup=off",
            "--no-wrap",
            "--previous",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return False, result.stderr.strip() or result.stdout.strip()
        target_path = existing_path
    else:
        existing_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(exported_path, existing_path)
        target_path = existing_path

    content = target_path.read_text(encoding="utf-8")
    if f"Language: {lang}" not in content:
        content = content.replace(
            '"Language-Team: \\n"',
            f'"Language-Team: \\n"\n"Language: {lang}\\n"',
            1,
        )
    revision_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M%z")
    if '"PO-Revision-Date:' in content:
        lines = []
        replaced = False
        for line in content.splitlines():
            if not replaced and line.startswith('"PO-Revision-Date:'):
                lines.append(f'"PO-Revision-Date: {revision_date}\\n"')
                replaced = True
            else:
                lines.append(line)
        content = "\n".join(lines) + "\n"
    target_path.write_text(content, encoding="utf-8")
    return True, ""


def count_translations(po_path):
    content = po_path.read_text(encoding="utf-8")
    entries = content.count("\nmsgid ")
    translated = content.count("\nmsgstr \"")
    non_empty = sum(
        1
        for block in content.split("\nmsgid ")[1:]
        if block.split("\nmsgstr ", 1)[-1].split("\n", 1)[0].strip() not in ('""', "")
    )
    return entries, non_empty


def parse_args():
    parser = argparse.ArgumentParser(
        description="Exporta archivos es_VE.po desde Odoo para los módulos de l10n-venezuela.",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path(os.environ.get("ODOO_CONF", DEFAULT_ODOO_CONF)),
        help="Archivo de configuración de Odoo.",
    )
    parser.add_argument(
        "-d",
        "--database",
        default=os.environ.get("ODOO_DB", ""),
        help="Base de datos de Odoo. Si no se indica, se autodetecta.",
    )
    parser.add_argument(
        "--odoo-bin",
        type=Path,
        default=Path(os.environ.get("ODOO_BIN", DEFAULT_ODOO_BIN)),
        help="Ruta al ejecutable odoo-bin.",
    )
    parser.add_argument(
        "-l",
        "--language",
        default=os.environ.get("ODOO_LANG", DEFAULT_LANG),
        help="Código de idioma a exportar.",
    )
    parser.add_argument(
        "-m",
        "--modules",
        nargs="*",
        help="Módulos específicos a exportar. Por defecto, todos los del repositorio.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Intentar exportar todos los módulos del repositorio, incluso los no instalados.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.odoo_bin.exists():
        print(f"ERROR: No se encontró odoo-bin en {args.odoo_bin}")
        sys.exit(1)
    if not args.config.exists():
        print(f"ERROR: No se encontró el archivo de configuración {args.config}")
        sys.exit(1)
    if not shutil.which("msgmerge"):
        print("ERROR: msgmerge no está instalado. Instala gettext.")
        sys.exit(1)

    repo_modules = discover_modules()
    modules = args.modules or repo_modules
    unknown = sorted(set(modules) - set(repo_modules))
    if unknown:
        print(f"ERROR: Módulos desconocidos en el repositorio: {', '.join(unknown)}")
        sys.exit(1)

    db_config = read_db_config(args.config)
    database = args.database or detect_database(db_config, repo_modules)
    if not database:
        print("ERROR: No se pudo detectar una base de datos con módulos l10n-venezuela instalados.")
        sys.exit(1)

    ensure_language(db_config, database, args.language)
    installed = get_installed_modules(db_config, database, repo_modules)

    print(f"Repositorio: {REPO_ROOT}")
    print(f"Configuración: {args.config}")
    print(f"Base de datos: {database}")
    print(f"Idioma: {args.language}")
    print(f"Módulos en repositorio: {len(repo_modules)}")
    print(f"Módulos instalados: {len(installed)}")
    print()

    exported = 0
    skipped = 0
    failed = []

    with tempfile.TemporaryDirectory(prefix="l10n_ve_i18n_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        for module in modules:
            po_path = REPO_ROOT / module / "i18n" / f"{args.language}.po"
            if not args.all and module not in installed:
                print(f"[SKIP] {module}: no instalado en {database}")
                skipped += 1
                continue
            if module not in installed:
                print(f"[WARN] {module}: no instalado en {database}, se intentará exportar igualmente")

            export_path = tmp_path / f"{module}.po"
            print(f"[EXPORT] {module}...", end=" ", flush=True)
            ok, error = export_module(
                args.odoo_bin,
                args.config,
                database,
                module,
                args.language,
                export_path,
            )
            if not ok:
                print("FALLÓ")
                failed.append((module, error))
                continue

            if export_path.read_text(encoding="utf-8").count("\nmsgid ") <= 1:
                print("SIN TÉRMINOS (módulo no instalado o sin cadenas traducibles)")
                skipped += 1
                continue

            ok, error = merge_po(po_path, export_path, args.language)
            if not ok:
                print("FALLÓ al fusionar")
                failed.append((module, error))
                continue

            total, done = count_translations(po_path)
            print(f"OK ({done}/{total} traducciones) -> {po_path.relative_to(REPO_ROOT)}")
            exported += 1

    print()
    print(f"Completado: {exported} exportados, {skipped} omitidos, {len(failed)} fallidos.")
    if failed:
        print()
        for module, error in failed:
            print(f"  - {module}: {error[:300]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
