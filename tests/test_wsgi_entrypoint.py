"""
Klein AI - WSGI Serverless Entrypoint & REST API Test Suite
Verifies that app.py exports valid WSGI callables (app, application, handler)
and correctly handles HTTP requests according to the WSGI standard.
"""
import io
import json
import pytest
from app import app, application, handler


def run_wsgi_request(method="GET", path="/", body=None, query_string="", headers=None):
    """Helper to simulate WSGI environment call."""
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query_string,
        "wsgi.input": io.BytesIO(),
    }
    if headers:
        for k, v in headers.items():
            environ[f"HTTP_{k.upper().replace('-', '_')}"] = v

    if body is not None:
        if isinstance(body, dict):
            body_bytes = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            body_bytes = body.encode("utf-8")
        else:
            body_bytes = body
        environ["wsgi.input"] = io.BytesIO(body_bytes)
        environ["CONTENT_LENGTH"] = str(len(body_bytes))
        environ["CONTENT_TYPE"] = "application/json"

    captured_status = []
    captured_headers = []

    def start_response(status, response_headers, exc_info=None):
        captured_status.append(status)
        captured_headers.append(response_headers)

    response_chunks = app(environ, start_response)
    raw_body = b"".join(response_chunks)

    header_dict = dict(captured_headers[0]) if captured_headers else {}
    return {
        "status": captured_status[0] if captured_status else None,
        "headers": header_dict,
        "body_bytes": raw_body,
        "body_text": raw_body.decode("utf-8", errors="replace")
    }


def test_wsgi_exported_variables():
    """Verify app.py exports top-level app, application, and handler variables."""
    assert callable(app)
    assert callable(application)
    assert callable(handler)
    assert app is application
    assert app is handler


def test_wsgi_root_landing_page():
    """Verify GET / returns 200 OK with HTML landing page."""
    res = run_wsgi_request("GET", "/")
    assert res["status"] == "200 OK"
    assert "text/html" in res["headers"].get("Content-Type", "")
    assert "Klein AI" in res["body_text"]
    assert "Autonomous Research Agent" in res["body_text"]
    assert "*" in res["headers"].get("Access-Control-Allow-Origin", "")


def test_wsgi_health_endpoint():
    """Verify GET /api/health and GET /health return system diagnostics."""
    for path in ("/api/health", "/health"):
        res = run_wsgi_request("GET", path)
        assert res["status"] == "200 OK"
        data = json.loads(res["body_text"])
        assert data["status"] == "healthy"
        assert data["app"] == "Klein AI"
        assert "default_model" in data
        assert "gemini_configured" in data


def test_wsgi_demo_endpoint():
    """Verify GET /api/demo returns verified demo dataset."""
    res = run_wsgi_request("GET", "/api/demo")
    assert res["status"] == "200 OK"
    data = json.loads(res["body_text"])
    assert data["success"] is True
    assert "Cybersecurity" in data["topic"]
    assert "blueprint" in data["data"]


def test_wsgi_sessions_endpoint():
    """Verify GET /api/sessions returns sessions list."""
    res = run_wsgi_request("GET", "/api/sessions")
    assert res["status"] == "200 OK"
    data = json.loads(res["body_text"])
    assert data["success"] is True
    assert isinstance(data["sessions"], list)


def test_wsgi_cors_options_preflight():
    """Verify OPTIONS request returns 204 No Content with CORS headers."""
    res = run_wsgi_request("OPTIONS", "/api/research")
    assert res["status"] == "204 No Content"
    assert res["headers"].get("Access-Control-Allow-Origin") == "*"
    assert "POST" in res["headers"].get("Access-Control-Allow-Methods")


def test_wsgi_research_validation_empty_topic():
    """Verify POST /api/research rejects empty topic with 400 Bad Request."""
    res = run_wsgi_request("POST", "/api/research", body={"topic": ""})
    assert res["status"] == "400 Bad Request"
    data = json.loads(res["body_text"])
    assert data["success"] is False
    assert "required" in data["error"].lower()


def test_wsgi_not_found():
    """Verify non-existent route returns 404 Not Found."""
    res = run_wsgi_request("GET", "/non_existent_path")
    assert res["status"] == "404 Not Found"
    data = json.loads(res["body_text"])
    assert "error" in data
