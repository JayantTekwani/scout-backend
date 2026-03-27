"""
Lightweight HTTP API for Sentinel-RAG.

Run:
    python api_server.py
"""

import json
import os
import base64
import re
import tempfile
import secrets
import time
import ssl
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import certifi

from core.config import CONFIG
from core.ingestion import load_and_chunk_file, load_and_chunk_url
from core.pipeline import SentinelPipeline

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", "8008"))
PROJECTS_ROOT = Path(__file__).parent / "projects"
ALLOWED_ORIGINS = {
    x.strip() for x in os.getenv("SCOUT_ALLOWED_ORIGINS", "*").split(",") if x.strip()
}
AUTH_TOKEN = os.getenv("SCOUT_AUTH_TOKEN", "").strip()
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID", "").strip()
MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET", "").strip()
MICROSOFT_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID", "common").strip() or "common"
OAUTH_STATE_TTL_SECS = 600
OAUTH_STATE: Dict[str, Dict[str, Any]] = {}
OAUTH_STATE_LOCK = Lock()
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
INSECURE_SSL_FALLBACK = os.getenv("SCOUT_OAUTH_INSECURE_SSL_FALLBACK", "1").strip() in ("1", "true", "True", "yes")
ALLOW_OAUTH_STATE_BYPASS = os.getenv("SCOUT_OAUTH_ALLOW_STATE_BYPASS", "1").strip() in ("1", "true", "True", "yes")


def _ssl_error_needs_fallback(err: Exception) -> bool:
    msg = str(err)
    return "CERTIFICATE_VERIFY_FAILED" in msg or "certificate verify failed" in msg


@dataclass
class SessionContext:
    current_project: str
    pipeline: Optional[SentinelPipeline]
    demo_loaded: bool = False


class ScoutAPIState:
    """Process runtime state with per-session contexts."""

    def __init__(self) -> None:
        PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()
        self.sessions: Dict[str, SessionContext] = {}
        self._ensure_project_dirs("default")
        self.sessions["default"] = SessionContext(current_project="default", pipeline=None, demo_loaded=False)

    def _safe_project_name(self, name: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip()).strip("-").lower()
        return cleaned or "default"

    def _project_dir(self, project_name: str) -> Path:
        return PROJECTS_ROOT / self._safe_project_name(project_name)

    def _project_index_path(self, project_name: str) -> str:
        return str(self._project_dir(project_name) / "index")

    def _project_docs_dir(self, project_name: str) -> Path:
        return self._project_dir(project_name) / "docs"

    def _ensure_project_dirs(self, project_name: str) -> None:
        pdir = self._project_dir(project_name)
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "docs").mkdir(parents=True, exist_ok=True)

    def list_projects(self) -> list[str]:
        if not PROJECTS_ROOT.exists():
            return []
        names = [p.name for p in PROJECTS_ROOT.iterdir() if p.is_dir()]
        return sorted(names)

    def get_or_create_session(self, session_id: str) -> SessionContext:
        safe_session = (session_id or "default").strip()
        with self.lock:
            if safe_session not in self.sessions:
                self.sessions[safe_session] = SessionContext(
                    current_project="default",
                    pipeline=None,
                    demo_loaded=False,
                )
            return self.sessions[safe_session]

    def ensure_pipeline(self, ctx: SessionContext) -> SentinelPipeline:
        if ctx.pipeline is None:
            ctx.pipeline = SentinelPipeline(index_path=self._project_index_path(ctx.current_project))
        return ctx.pipeline

    def select_project(
        self, session_id: str, project_name: str, create_if_missing: bool = True
    ) -> str:
        ctx = self.get_or_create_session(session_id)
        safe_name = self._safe_project_name(project_name)
        pdir = self._project_dir(safe_name)
        if not pdir.exists() and not create_if_missing:
            raise ValueError("Project does not exist")
        self._ensure_project_dirs(safe_name)
        ctx.current_project = safe_name
        ctx.pipeline = None
        ctx.demo_loaded = False
        return safe_name

    def ensure_demo_loaded(self, session_id: str) -> None:
        ctx = self.get_or_create_session(session_id)
        pipeline = self.ensure_pipeline(ctx)
        if pipeline.vector_store.is_ready() or ctx.demo_loaded:
            return

        demo_path = Path(__file__).parent / "data" / "demo_documents.txt"
        if not demo_path.exists():
            return

        docs = load_and_chunk_file(str(demo_path), authority_score=0.85, access_level=1)
        hdocs = load_and_chunk_file(str(demo_path), authority_score=0.99, access_level=4)

        for d in hdocs:
            d.metadata["source"] = "security_policy_internal.txt"
            d.metadata["access_level"] = 4

        pipeline.vector_store.add_documents(docs + hdocs[:10])
        ctx.demo_loaded = True


STATE = ScoutAPIState()


def _is_origin_allowed(origin: Optional[str]) -> bool:
    if "*" in ALLOWED_ORIGINS:
        return True
    return bool(origin and origin in ALLOWED_ORIGINS)


def _origin_for_response(handler: BaseHTTPRequestHandler) -> str:
    origin = handler.headers.get("Origin")
    if _is_origin_allowed(origin):
        return origin or "*"
    return "null"


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: Dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", _origin_for_response(handler))
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header(
        "Access-Control-Allow-Headers",
        "Content-Type, Authorization, X-Session-Id, X-Scout-Token",
    )
    handler.send_header("Vary", "Origin")
    handler.end_headers()
    handler.wfile.write(body)


def _html_response(handler: BaseHTTPRequestHandler, status: int, html: str) -> None:
    body = html.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _redirect_response(handler: BaseHTTPRequestHandler, location: str, status: int = 302) -> None:
    handler.send_response(status)
    handler.send_header("Location", location)
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()


def _server_base_url(handler: BaseHTTPRequestHandler) -> str:
    host = (handler.headers.get("Host") or f"{HOST}:{PORT}").strip()
    # Azure redirect URI validation is strict for localhost vs 127.0.0.1.
    # Normalize loopback host to localhost for local OAuth callbacks.
    if host.startswith("127.0.0.1:"):
        host = host.replace("127.0.0.1", "localhost", 1)
    proto = (handler.headers.get("X-Forwarded-Proto") or "http").strip()
    return f"{proto}://{host}"


def _oauth_store_state(provider: str, mode: str = "signin") -> str:
    state = secrets.token_urlsafe(24)
    with OAUTH_STATE_LOCK:
        OAUTH_STATE[state] = {
            "provider": provider,
            "mode": mode,
            "created_at": int(time.time()),
        }
        # Best-effort cleanup for expired states.
        cutoff = int(time.time()) - OAUTH_STATE_TTL_SECS
        for k, v in list(OAUTH_STATE.items()):
            if int(v.get("created_at", 0)) < cutoff:
                OAUTH_STATE.pop(k, None)
    return state


def _oauth_pop_state(state: str, provider: str) -> bool:
    if not state:
        return False
    with OAUTH_STATE_LOCK:
        data = OAUTH_STATE.pop(state, None)
    if not data:
        return False
    if data.get("provider") != provider:
        return False
    age = int(time.time()) - int(data.get("created_at", 0))
    return age <= OAUTH_STATE_TTL_SECS


def _http_form_post_json(url: str, payload: Dict[str, str]) -> Dict[str, Any]:
    data = urlencode(payload).encode("utf-8")
    req = Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urlopen(req, timeout=20, context=SSL_CONTEXT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} from {url}: {body or e.reason}")
    except Exception as e:
        if INSECURE_SSL_FALLBACK and _ssl_error_needs_fallback(e):
            insecure_ctx = ssl._create_unverified_context()
            with urlopen(req, timeout=20, context=insecure_ctx) as resp:
                return json.loads(resp.read().decode("utf-8"))
        raise


def _http_get_json(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    req = Request(url, method="GET")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urlopen(req, timeout=20, context=SSL_CONTEXT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} from {url}: {body or e.reason}")
    except Exception as e:
        if INSECURE_SSL_FALLBACK and _ssl_error_needs_fallback(e):
            insecure_ctx = ssl._create_unverified_context()
            with urlopen(req, timeout=20, context=insecure_ctx) as resp:
                return json.loads(resp.read().decode("utf-8"))
        raise


def _oauth_popup_html(payload: Dict[str, Any]) -> str:
    data = json.dumps(payload)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>SCOUT OAuth</title></head>
<body style="font-family: sans-serif; background:#0b1020; color:#e2e8f0; display:grid; place-items:center; min-height:100vh;">
  <div>Authentication complete. You can close this window.</div>
  <script>
    (function() {{
      var payload = {data};
      if (window.opener && !window.opener.closed) {{
        window.opener.postMessage(payload, "*");
      }}
      setTimeout(function() {{ window.close(); }}, 350);
    }})();
  </script>
</body></html>"""


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class ScoutAPIHandler(BaseHTTPRequestHandler):
    server_version = "ScoutAPI/1.0"

    def do_OPTIONS(self) -> None:
        _json_response(self, 200, {"ok": True})

    def _require_auth(self) -> bool:
        if not AUTH_TOKEN:
            return True
        supplied = (
            self.headers.get("X-Scout-Token")
            or self.headers.get("Authorization", "").replace("Bearer ", "")
        ).strip()
        return secrets.compare_digest(supplied, AUTH_TOKEN)

    def _session_id(self, payload: Optional[dict] = None) -> str:
        sid = (self.headers.get("X-Session-Id") or "").strip()
        if not sid and payload:
            sid = str(payload.get("session_id", "")).strip()
        return sid or "default"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/auth/google/start":
            if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
                _json_response(
                    self,
                    400,
                    {
                        "ok": False,
                        "error": "Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
                    },
                )
                return
            state = _oauth_store_state("google", mode=(qs.get("mode", ["signin"])[0] or "signin"))
            base = _server_base_url(self)
            redirect_uri = f"{base}/auth/google/callback"
            auth_url = (
                "https://accounts.google.com/o/oauth2/v2/auth?"
                + urlencode(
                    {
                        "client_id": GOOGLE_CLIENT_ID,
                        "redirect_uri": redirect_uri,
                        "response_type": "code",
                        "scope": "openid email profile",
                        "state": state,
                        "prompt": "select_account",
                    }
                )
            )
            _redirect_response(self, auth_url)
            return

        if path == "/auth/google/callback":
            error = (qs.get("error", [""])[0] or "").strip()
            state = (qs.get("state", [""])[0] or "").strip()
            code = (qs.get("code", [""])[0] or "").strip()
            state_ok = _oauth_pop_state(state, "google")
            if not state_ok and not ALLOW_OAUTH_STATE_BYPASS:
                _html_response(
                    self,
                    400,
                    _oauth_popup_html(
                        {"type": "SCOUT_OAUTH_RESULT", "ok": False, "provider": "google", "error": "Invalid or expired OAuth state"}
                    ),
                )
                return
            if error:
                _html_response(
                    self,
                    400,
                    _oauth_popup_html({"type": "SCOUT_OAUTH_RESULT", "ok": False, "provider": "google", "error": error}),
                )
                return
            if not code:
                _html_response(
                    self,
                    400,
                    _oauth_popup_html({"type": "SCOUT_OAUTH_RESULT", "ok": False, "provider": "google", "error": "Missing code"}),
                )
                return
            try:
                base = _server_base_url(self)
                redirect_uri = f"{base}/auth/google/callback"
                token = _http_form_post_json(
                    "https://oauth2.googleapis.com/token",
                    {
                        "client_id": GOOGLE_CLIENT_ID,
                        "client_secret": GOOGLE_CLIENT_SECRET,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                    },
                )
                access_token = str(token.get("access_token", "")).strip()
                if not access_token:
                    raise RuntimeError("No access token returned by Google.")
                info = _http_get_json(
                    "https://openidconnect.googleapis.com/v1/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                payload = {
                    "type": "SCOUT_OAUTH_RESULT",
                    "ok": True,
                    "provider": "google",
                    "profile": {
                        "email": info.get("email", ""),
                        "name": info.get("name", ""),
                        "picture": info.get("picture", ""),
                        "id": info.get("sub", ""),
                    },
                }
                _html_response(self, 200, _oauth_popup_html(payload))
            except Exception as e:
                _html_response(
                    self,
                    500,
                    _oauth_popup_html(
                        {"type": "SCOUT_OAUTH_RESULT", "ok": False, "provider": "google", "error": str(e)}
                    ),
                )
            return

        if path == "/auth/microsoft/start":
            if not MICROSOFT_CLIENT_ID or not MICROSOFT_CLIENT_SECRET:
                _json_response(
                    self,
                    400,
                    {
                        "ok": False,
                        "error": "Microsoft OAuth not configured. Set MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET.",
                    },
                )
                return
            state = _oauth_store_state("microsoft", mode=(qs.get("mode", ["signin"])[0] or "signin"))
            base = _server_base_url(self)
            redirect_uri = f"{base}/auth/microsoft/callback"
            auth_url = (
                f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}/oauth2/v2.0/authorize?"
                + urlencode(
                    {
                        "client_id": MICROSOFT_CLIENT_ID,
                        "response_type": "code",
                        "redirect_uri": redirect_uri,
                        "response_mode": "query",
                        "scope": "openid profile email User.Read",
                        "state": state,
                        "prompt": "select_account",
                    }
                )
            )
            _redirect_response(self, auth_url)
            return

        if path == "/auth/microsoft/callback":
            error = (qs.get("error", [""])[0] or "").strip()
            state = (qs.get("state", [""])[0] or "").strip()
            code = (qs.get("code", [""])[0] or "").strip()
            state_ok = _oauth_pop_state(state, "microsoft")
            if not state_ok and not ALLOW_OAUTH_STATE_BYPASS:
                _html_response(
                    self,
                    400,
                    _oauth_popup_html(
                        {
                            "type": "SCOUT_OAUTH_RESULT",
                            "ok": False,
                            "provider": "microsoft",
                            "error": "Invalid or expired OAuth state",
                        }
                    ),
                )
                return
            if error:
                _html_response(
                    self,
                    400,
                    _oauth_popup_html({"type": "SCOUT_OAUTH_RESULT", "ok": False, "provider": "microsoft", "error": error}),
                )
                return
            if not code:
                _html_response(
                    self,
                    400,
                    _oauth_popup_html({"type": "SCOUT_OAUTH_RESULT", "ok": False, "provider": "microsoft", "error": "Missing code"}),
                )
                return
            try:
                base = _server_base_url(self)
                redirect_uri = f"{base}/auth/microsoft/callback"
                token = _http_form_post_json(
                    f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}/oauth2/v2.0/token",
                    {
                        "client_id": MICROSOFT_CLIENT_ID,
                        "client_secret": MICROSOFT_CLIENT_SECRET,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                        "scope": "openid profile email User.Read",
                    },
                )
                access_token = str(token.get("access_token", "")).strip()
                if not access_token:
                    raise RuntimeError("No access token returned by Microsoft.")
                info = _http_get_json(
                    "https://graph.microsoft.com/v1.0/me?$select=id,displayName,mail,userPrincipalName",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                payload = {
                    "type": "SCOUT_OAUTH_RESULT",
                    "ok": True,
                    "provider": "microsoft",
                    "profile": {
                        "email": info.get("mail") or info.get("userPrincipalName") or "",
                        "name": info.get("displayName") or "",
                        "id": info.get("id") or "",
                    },
                }
                _html_response(self, 200, _oauth_popup_html(payload))
            except Exception as e:
                _html_response(
                    self,
                    500,
                    _oauth_popup_html(
                        {"type": "SCOUT_OAUTH_RESULT", "ok": False, "provider": "microsoft", "error": str(e)}
                    ),
                )
            return

        if not self._require_auth():
            _json_response(self, 401, {"ok": False, "error": "Unauthorized"})
            return
        session_id = self._session_id()
        ctx = STATE.get_or_create_session(session_id)
        if path == "/health":
            pipeline = ctx.pipeline
            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "ready": pipeline.vector_store.is_ready() if pipeline else False,
                    "doc_count": pipeline.vector_store.doc_count() if pipeline else 0,
                    "current_project": ctx.current_project,
                    "session_id": session_id,
                },
            )
            return
        if path == "/projects":
            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "projects": STATE.list_projects(),
                    "current_project": ctx.current_project,
                    "session_id": session_id,
                },
            )
            return

        _json_response(self, 404, {"ok": False, "error": "Not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path not in ("/chat", "/ingest", "/ingest_urls", "/reset", "/projects/select", "/session"):
            _json_response(self, 404, {"ok": False, "error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            payload = json.loads(raw)
        except Exception:
            _json_response(self, 400, {"ok": False, "error": "Invalid JSON body"})
            return

        if path == "/session":
            if not self._require_auth():
                _json_response(self, 401, {"ok": False, "error": "Unauthorized"})
                return
            requested = str(payload.get("session_id", "")).strip()
            session_id = requested or f"sess_{secrets.token_hex(8)}"
            STATE.get_or_create_session(session_id)
            _json_response(self, 200, {"ok": True, "session_id": session_id})
            return

        if not self._require_auth():
            _json_response(self, 401, {"ok": False, "error": "Unauthorized"})
            return

        session_id = self._session_id(payload)
        ctx = STATE.get_or_create_session(session_id)

        if path == "/reset":
            pipeline = STATE.ensure_pipeline(ctx)
            pipeline.vector_store.reset()
            ctx.demo_loaded = False
            _json_response(self, 200, {"ok": True, "message": "Index reset complete"})
            return

        if path == "/projects/select":
            project_name = str(payload.get("name", "")).strip()
            if not project_name:
                _json_response(self, 400, {"ok": False, "error": "Missing project name"})
                return
            create_if_missing = bool(payload.get("create_if_missing", True))
            try:
                chosen = STATE.select_project(
                    session_id=session_id,
                    project_name=project_name,
                    create_if_missing=create_if_missing,
                )
            except ValueError as e:
                _json_response(self, 404, {"ok": False, "error": str(e)})
                return

            ctx = STATE.get_or_create_session(session_id)
            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "current_project": chosen,
                    "doc_count": STATE.ensure_pipeline(ctx).vector_store.doc_count(),
                    "session_id": session_id,
                },
            )
            return

        if path == "/ingest":
            pipeline = STATE.ensure_pipeline(ctx)
            files = payload.get("files", [])
            if not isinstance(files, list) or not files:
                _json_response(self, 400, {"ok": False, "error": "Missing 'files' list"})
                return

            authority_score = float(payload.get("authority_score", 0.85))
            authority_score = max(0.0, min(1.0, authority_score))
            access_level = int(payload.get("access_level", 1))
            access_level = max(1, min(5, access_level))

            total_chunks = 0
            ingested_files = []

            for f in files:
                name = str(f.get("name", "")).strip()
                content_b64 = str(f.get("content_base64", "")).strip()
                if not name or not content_b64:
                    continue

                suffix = Path(name).suffix.lower()
                if suffix not in (".pdf", ".txt", ".md"):
                    continue

                try:
                    data = base64.b64decode(content_b64)
                except Exception:
                    continue

                tmp_path = None
                try:
                    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                        tmp.write(data)
                        tmp_path = tmp.name

                    # Persist original upload in project docs folder
                    docs_dir = STATE._project_docs_dir(ctx.current_project)
                    docs_dir.mkdir(parents=True, exist_ok=True)
                    with open(docs_dir / name, "wb") as out_f:
                        out_f.write(data)

                    docs = load_and_chunk_file(
                        tmp_path,
                        authority_score=authority_score,
                        access_level=access_level,
                    )
                    for d in docs:
                        d.metadata["source"] = name
                        d.metadata["access_level"] = access_level
                        d.metadata["authority_score"] = authority_score

                    total_chunks += pipeline.vector_store.add_documents(docs)
                    ingested_files.append(name)
                except Exception:
                    continue
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        os.unlink(tmp_path)

            if not ingested_files:
                _json_response(
                    self,
                    400,
                    {"ok": False, "error": "No valid files ingested. Use PDF, TXT, or MD."},
                )
                return

            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "files": ingested_files,
                    "chunks_indexed": total_chunks,
                    "doc_count": pipeline.vector_store.doc_count(),
                    "current_project": ctx.current_project,
                    "session_id": session_id,
                },
            )
            return

        if path == "/ingest_urls":
            pipeline = STATE.ensure_pipeline(ctx)
            urls = payload.get("urls", [])
            if not isinstance(urls, list) or not urls:
                _json_response(self, 400, {"ok": False, "error": "Missing 'urls' list"})
                return

            authority_score = float(payload.get("authority_score", 0.85))
            authority_score = max(0.0, min(1.0, authority_score))
            access_level = int(payload.get("access_level", 1))
            access_level = max(1, min(5, access_level))

            total_chunks = 0
            ingested_urls = []

            for url in urls:
                u = str(url).strip()
                if not (u.startswith("http://") or u.startswith("https://")):
                    continue
                try:
                    docs = load_and_chunk_url(
                        u,
                        authority_score=authority_score,
                        access_level=access_level,
                    )
                    total_chunks += pipeline.vector_store.add_documents(docs)
                    ingested_urls.append(u)
                except Exception:
                    continue

            if not ingested_urls:
                _json_response(
                    self,
                    400,
                    {"ok": False, "error": "No URLs were ingested. Ensure links are public/reachable."},
                )
                return

            _json_response(
                self,
                200,
                {
                    "ok": True,
                    "urls": ingested_urls,
                    "chunks_indexed": total_chunks,
                    "doc_count": pipeline.vector_store.doc_count(),
                    "current_project": ctx.current_project,
                    "session_id": session_id,
                },
            )
            return

        # /chat
        query = str(payload.get("query", "")).strip()
        if not query:
            _json_response(self, 400, {"ok": False, "error": "Missing 'query'"})
            return

        if not os.environ.get("GROQ_API_KEY") and not CONFIG.GROQ_API_KEY:
            _json_response(self, 400, {"ok": False, "error": "GROQ_API_KEY is required"})
            return

        if payload.get("load_demo_if_empty", True):
            STATE.ensure_demo_loaded(session_id)
            ctx = STATE.get_or_create_session(session_id)

        pipeline = STATE.ensure_pipeline(ctx)
        if not pipeline.vector_store.is_ready():
            _json_response(
                self,
                400,
                {"ok": False, "error": "No vectors indexed. Load demo data or ingest your documents."},
            )
            return

        user_access_level = int(payload.get("user_access_level", 2))
        user_access_level = max(1, min(5, user_access_level))

        response = pipeline.run(
            query=query,
            user_access_level=user_access_level,
            after_date=_parse_iso_datetime(payload.get("after_date")),
            before_date=_parse_iso_datetime(payload.get("before_date")),
            milestone_tag=payload.get("milestone_tag"),
        )

        source_cards = []
        for s in response.sources:
            source_cards.append(
                {
                    "chunk_id": s.chunk_id,
                    "source": s.metadata.source,
                    "authority_score": s.metadata.authority_score,
                    "access_level": s.metadata.access_level,
                    "milestone_tag": s.metadata.milestone_tag,
                }
            )

        _json_response(
            self,
            200,
            {
                "ok": True,
                "answer": response.answer,
                "intent": response.decision_trace.intent.model_dump(mode="json"),
                "trace": response.decision_trace.model_dump(mode="json"),
                "conflict": response.conflict.model_dump(mode="json"),
                "computation": response.computation.model_dump(mode="json"),
                "sources": source_cards,
                "timestamp": response.timestamp.isoformat(),
                "current_project": ctx.current_project,
                "session_id": session_id,
                "plan": response.decision_trace.planning_steps,
            },
        )

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), ScoutAPIHandler)
    print(f"SCOUT API listening on http://{HOST}:{PORT}")
    server.serve_forever()

if __name__ == "__main__":
    main()
    
