# -*- coding: utf-8 -*-
"""Локальное файловое облако — простой сервер для файлов из родительской папки."""
import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Корень облака = родительская папка от этого скрипта
ROOT = Path(__file__).resolve().parent.parent
SAFE_NAME = {"py", "pyc", "db", "sqlite", "lock", "tmp"}

MIME = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".zip": "application/zip",
    ".rar": "application/x-rar-compressed",
    ".7z": "application/x-7z-compressed",
    ".txt": "text/plain; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".wav": "audio/wav",
}


def human_size(num):
    num = float(num)
    for unit in ("Б", "КБ", "МБ", "ГБ", "ТБ"):
        if num < 1024 or unit == "ТБ":
            if unit == "Б":
                return f"{int(num)} {unit}"
            return f"{num:.1f} {unit}"
        num /= 1024


def is_dir_empty(p):
    try:
        return not any(p.iterdir())
    except OSError:
        return True


def walk_dir(base, rel=""):
    base_path = base / rel
    entries = []
    try:
        items = sorted(base_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    except OSError:
        return entries
    for p in items:
        if p.name in (".", ".."):
            continue
        if p.is_dir():
            entries.append({
                "name": p.name,
                "path": os.path.join(rel, p.name).replace("\\", "/"),
                "type": "dir",
                "size": None,
                "size_h": "",
                "modified": None,
            })
        else:
            try:
                st = p.stat()
            except OSError:
                continue
            entries.append({
                "name": p.name,
                "path": os.path.join(rel, p.name).replace("\\", "/"),
                "type": "file",
                "size": st.st_size,
                "size_h": human_size(st.st_size),
                "modified": st.st_mtime,
            })
    return entries


def resolve_rel(root, rel):
    """Безопасно раскрывает относительный путь внутри ROOT."""
    target = (root / rel).resolve()
    if not (target == root.resolve() or root.resolve() in target.parents):
        return None
    return target


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send_json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_error(self, code, message):
        self._send_json({"error": message}, code)

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return None
        return self.rfile.read(length)

    # ---------- ПУТИ ----------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path)

        if path == "/" or path == "/index.html":
            self._serve_static("index.html")
            return

        if path == "/api/list":
            qs = urllib.parse.parse_qs(parsed.query)
            rel = qs.get("path", [""])[0]
            target = resolve_rel(ROOT, rel)
            if target is None:
                return self._send_error(400, "Неверный путь")
            if not target.is_dir():
                return self._send_error(400, "Это не папка")
            entries = walk_dir(ROOT, rel)
            return self._send_json({"path": rel, "entries": entries})

        if path.startswith("/api/download"):
            qs = urllib.parse.parse_qs(parsed.query)
            rel = qs.get("path", [""])[0]
            target = resolve_rel(ROOT, rel)
            if target is None or not target.is_file():
                return self._send_error(404, "Файл не найден")
            return self._download(target)

        # статика фронтенда
        if path.startswith("/static/"):
            return self._serve_static(path[1:])

        return self._send_error(404, "Не найдено")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/upload":
            return self._handle_upload(parsed)

        if path == "/api/mkdir":
            body = self._read_body()
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                return self._send_error(400, "Неверный JSON")
            rel = resolve_rel(ROOT, data.get("dir", ""))
            name = (data.get("name") or "").strip()
            if rel is None or not rel.is_dir():
                return self._send_error(400, "Неверная папка")
            if not name or "/" in name or "\\" in name or name in (".", ".."):
                return self._send_error(400, "Некорректное имя")
            target = rel / name
            try:
                target.mkdir()
            except FileExistsError:
                return self._send_error(409, "Папка уже существует")
            except OSError as e:
                return self._send_error(500, str(e))
            return self._send_json({"ok": True, "path": (data.get("dir", "") + "/" + name).replace("\\", "/").lstrip("/")})

        if path == "/api/delete":
            body = self._read_body()
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                return self._send_error(400, "Неверный JSON")
            rel = (data.get("path") or "").strip()
            target = resolve_rel(ROOT, rel)
            if target is None or target == ROOT.resolve():
                return self._send_error(400, "Неверный путь")
            if not target.exists():
                return self._send_error(404, "Не найдено")
            try:
                if target.is_dir() and not is_dir_empty(target):
                    return self._send_error(400, "Папка не пуста")
                os.remove(target) if target.is_file() else target.rmdir()
            except OSError as e:
                return self._send_error(500, str(e))
            return self._send_json({"ok": True})

        if path == "/api/rename":
            body = self._read_body()
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                return self._send_error(400, "Неверный JSON")
            old_rel = (data.get("path") or "").strip()
            new_name = (data.get("name") or "").strip()
            old_target = resolve_rel(ROOT, old_rel)
            if old_target is None or not old_target.exists():
                return self._send_error(404, "Не найдено")
            if not new_name or new_name in (".", "..") or "/" in new_name or "\\" in new_name:
                return self._send_error(400, "Некорректное имя")
            new_target = old_target.parent / new_name
            try:
                old_target.rename(new_target)
            except OSError as e:
                return self._send_error(500, str(e))
            new_rel = os.path.join(os.path.dirname(old_rel), new_name).replace("\\", "/")
            return self._send_json({"ok": True, "path": new_rel})

        return self._send_error(404, "Не найдено")

    # ---------- ВНУТРЕННЕЕ ----------
    def _serve_static(self, rel):
        target = (Path(__file__).resolve().parent / rel).resolve()
        if not (Path(__file__).resolve().parent == target.parent or target.exists()):
            return self._send_error(404, "Не найдено")
        if not target.exists() or not target.is_file():
            return self._send_error(404, "Не найдено")
        ext = target.suffix.lower()
        ctype = MIME.get(ext, "application/octet-stream")
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _download(self, target):
        st = target.stat()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", 'attachment; filename="{}"'.format(
            urllib.parse.quote(target.name)))
        self.send_header("Content-Length", str(st.st_size))
        self.end_headers()
        with open(target, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def _handle_upload(self, parsed):
        qs = urllib.parse.parse_qs(parsed.query)
        rel = qs.get("dir", [""])[0]
        target_dir = resolve_rel(ROOT, rel)
        if target_dir is None or not target_dir.is_dir():
            return self._send_error(400, "Неверная папка")

        # multipart разбор (максимум 200 МБ)
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            return self._send_error(400, "Ожидается multipart/form-data")
        boundary = content_type.split("boundary=")[-1].strip().strip('"').encode("utf-8")
        body = self._read_body()
        if body is None:
            return self._send_error(400, "Пустое тело")

        parts = body.split(b"--" + boundary)
        saved = []
        errors = []
        for part in parts:
            part = part.strip(b"\r\n")
            if not part or part in (b"--", b""):
                continue
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue
            headers = part[:header_end].decode("utf-8", "ignore")
            file_data = part[header_end + 4:]
            filename = None
            for line in headers.split("\r\n"):
                if "name=\"file\"" in line and "filename=" in line:
                    if 'filename="' in line:
                        filename = line.split('filename="')[1].split('"')[0]
                    elif "filename*=UTF-8''" in line:
                        filename = urllib.parse.unquote(line.split("filename*=UTF-8''")[1].split(";")[0].strip())
            if not filename:
                continue
            filename = os.path.basename(filename.replace("\\", "/"))
            if not filename or filename in (".", ".."):
                continue
            dest = target_dir / filename
            try:
                with open(dest, "wb") as f:
                    f.write(file_data)
                saved.append(filename)
            except OSError as e:
                errors.append(str(e))
        return self._send_json({"ok": True, "saved": saved, "errors": errors})


def main():
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("Файловое облако запущено:")
    print(f"  Адрес: http://127.0.0.1:{port}")
    print(f"  Папка: {ROOT}")
    print("  Для остановки нажмите Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено.")
        server.server_close()


if __name__ == "__main__":
    main()