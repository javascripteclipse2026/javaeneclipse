#!/usr/bin/env python3
"""
Eclipse Java IDE - Backend Server
Compila y ejecuta código Java de forma segura.
100% funcional con OpenJDK.
"""

import http.server
import socketserver
import json
import os
import sys
import tempfile
import shutil
import subprocess
import uuid
import re
import time
import traceback
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Configuración
PORT = 8080
HOST = "0.0.0.0"
BASE_DIR = Path(__file__).parent.resolve()
PUBLIC_DIR = BASE_DIR / "public"
TEMP_DIR = BASE_DIR / "temp"
PROJECTS_DIR = BASE_DIR / "projects"
TIMEOUT_SECONDS = 8  # Timeout de ejecución
MAX_CODE_SIZE = 100_000  # 100 KB máximo

# Asegurar carpetas
TEMP_DIR.mkdir(exist_ok=True)
PROJECTS_DIR.mkdir(exist_ok=True)
PUBLIC_DIR.mkdir(exist_ok=True)


def clean_old_temps(max_age_seconds=300):
    """Elimina carpetas temporales antiguas."""
    now = time.time()
    for item in TEMP_DIR.iterdir():
        if item.is_dir():
            try:
                if now - item.stat().st_mtime > max_age_seconds:
                    shutil.rmtree(item, ignore_errors=True)
            except Exception:
                pass


def extract_public_class(code: str) -> str | None:
    """Extrae el nombre de la clase pública principal."""
    # Buscar "public class Nombre"
    match = re.search(r'public\s+class\s+(\w+)', code)
    if match:
        return match.group(1)
    # Si no hay public, buscar cualquier class
    match = re.search(r'class\s+(\w+)', code)
    if match:
        return match.group(1)
    return None


def compile_and_run(code: str) -> dict:
    """
    Compila y ejecuta el código Java de forma segura.
    Retorna dict con success, output, error, time.
    """
    if len(code) > MAX_CODE_SIZE:
        return {
            "success": False,
            "output": "",
            "error": f"Código demasiado grande (máx {MAX_CODE_SIZE // 1000} KB).",
            "compile_time": 0,
            "run_time": 0
        }

    class_name = extract_public_class(code)
    if not class_name:
        return {
            "success": False,
            "output": "",
            "error": "No se encontró ninguna clase en el código. Debes definir al menos una clase (ej: public class Main { ... }).",
            "compile_time": 0,
            "run_time": 0
        }

    # Sanitizar nombre de clase
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', class_name):
        return {
            "success": False,
            "output": "",
            "error": f"Nombre de clase inválido: {class_name}",
            "compile_time": 0,
            "run_time": 0
        }

    work_id = str(uuid.uuid4())[:12]
    work_dir = TEMP_DIR / work_id
    work_dir.mkdir(parents=True, exist_ok=True)

    java_file = work_dir / f"{class_name}.java"
    class_file = work_dir / f"{class_name}.class"

    try:
        # Escribir el código
        java_file.write_text(code, encoding="utf-8")

        # ========== COMPILAR ==========
        t0 = time.time()
        compile_proc = subprocess.run(
            ["javac", "-encoding", "UTF-8", str(java_file)],
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS
        )
        compile_time = round(time.time() - t0, 3)

        if compile_proc.returncode != 0:
            error_msg = compile_proc.stderr.strip() or compile_proc.stdout.strip()
            # Limpiar rutas absolutas del error para que se vea limpio
            error_msg = error_msg.replace(str(work_dir) + os.sep, "")
            return {
                "success": False,
                "output": "",
                "error": f"Error de compilación:\n{error_msg}",
                "compile_time": compile_time,
                "run_time": 0
            }

        # ========== EJECUTAR ==========
        t1 = time.time()
        run_proc = subprocess.run(
            ["java", "-cp", str(work_dir), class_name],
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            env={**os.environ, "JAVA_TOOL_OPTIONS": "-Xmx128m"}  # Limitar memoria
        )
        run_time = round(time.time() - t1, 3)

        stdout = run_proc.stdout or ""
        stderr = run_proc.stderr or ""

        if run_proc.returncode != 0:
            error_msg = stderr.strip() or f"Proceso terminó con código {run_proc.returncode}"
            return {
                "success": False,
                "output": stdout,
                "error": f"Error en ejecución:\n{error_msg}",
                "compile_time": compile_time,
                "run_time": run_time
            }

        return {
            "success": True,
            "output": stdout,
            "error": stderr if stderr else "",
            "compile_time": compile_time,
            "run_time": run_time
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": f"Timeout: el programa superó los {TIMEOUT_SECONDS} segundos de ejecución.",
            "compile_time": 0,
            "run_time": TIMEOUT_SECONDS
        }
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": f"Error interno del servidor:\n{str(e)}",
            "compile_time": 0,
            "run_time": 0
        }
    finally:
        # Limpiar siempre
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass


class JavaIDEHandler(http.server.SimpleHTTPRequestHandler):
    """Servidor HTTP que sirve el frontend y el endpoint de ejecución."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC_DIR), **kwargs)

    def log_message(self, format, *args):
        # Log más limpio
        sys.stderr.write(f"[{self.log_date_time_string()}] {args[0]}\n")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/run":
            self.handle_run()
        elif parsed.path == "/api/save":
            self.handle_save()
        elif parsed.path == "/api/list":
            self.handle_list()
        else:
            self.send_error(404, "Endpoint no encontrado")

    def handle_run(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > MAX_CODE_SIZE + 1000:
            self._json_response(413, {"success": False, "error": "Payload demasiado grande"})
            return

        try:
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
            code = data.get("code", "")
            if not code.strip():
                self._json_response(400, {"success": False, "error": "No se recibió código"})
                return

            clean_old_temps()
            result = compile_and_run(code)
            self._json_response(200, result)
        except json.JSONDecodeError:
            self._json_response(400, {"success": False, "error": "JSON inválido"})
        except Exception as e:
            self._json_response(500, {"success": False, "error": str(e)})

    def handle_save(self):
        """Guarda un proyecto en el servidor (opcional)."""
        content_length = int(self.headers.get("Content-Length", 0))
        try:
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
            name = data.get("name", "proyecto").strip()
            code = data.get("code", "")

            # Sanitizar nombre
            name = re.sub(r'[^\w\-]', '_', name)[:50] or "proyecto"
            if not name.endswith(".java"):
                name += ".java"

            path = PROJECTS_DIR / name
            path.write_text(code, encoding="utf-8")
            self._json_response(200, {"success": True, "filename": name, "message": f"Guardado como {name}"})
        except Exception as e:
            self._json_response(500, {"success": False, "error": str(e)})

    def handle_list(self):
        """Lista proyectos guardados."""
        try:
            files = []
            for f in sorted(PROJECTS_DIR.glob("*.java")):
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "modified": time.ctime(f.stat().st_mtime)
                })
            self._json_response(200, {"success": True, "files": files})
        except Exception as e:
            self._json_response(500, {"success": False, "error": str(e)})

    def _json_response(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def main():
    # Verificar que Java esté disponible
    try:
        subprocess.run(["javac", "-version"], capture_output=True, check=True)
        subprocess.run(["java", "-version"], capture_output=True, check=True)
    except Exception:
        print("❌ ERROR: No se encontró Java (javac/java). Instala OpenJDK.")
        sys.exit(1)

    print("=" * 60)
    print("  🚀 Eclipse Java IDE - Servidor listo")
    print("=" * 60)
    print(f"  Frontend : http://localhost:{PORT}")
    print(f"  API Run  : http://localhost:{PORT}/api/run")
    print(f"  Java     : OK (OpenJDK detectado)")
    print(f"  Timeout  : {TIMEOUT_SECONDS}s")
    print("=" * 60)
    print("  Presiona Ctrl+C para detener el servidor")
    print()

    with socketserver.TCPServer((HOST, PORT), JavaIDEHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor detenido.")


if __name__ == "__main__":
    main()
