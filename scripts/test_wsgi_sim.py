import io
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app

def simulate_request(path, method="GET", body=None, headers=None, query_string=""):
    env = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query_string,
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.input": io.BytesIO(body.encode("utf-8") if isinstance(body, str) else (body or b"")),
        "CONTENT_LENGTH": str(len(body.encode("utf-8")) if isinstance(body, str) else len(body or b"")),
    }
    if headers:
        for k, v in headers.items():
            header_key = "HTTP_" + k.upper().replace("-", "_")
            if k.lower() == "content-type":
                env["CONTENT_TYPE"] = v
            else:
                env[header_key] = v

    captured_status = []
    captured_headers = []

    def start_response(status, response_headers):
        captured_status.append(status)
        captured_headers.extend(response_headers)

    response_chunks = app(env, start_response)
    response_body = b"".join(response_chunks)
    header_dict = {k: v for k, v in captured_headers}

    return captured_status[0], header_dict, response_body

def run_tests():
    print("Testing 1: GET / (HTML Landing Page)")
    status, headers, body = simulate_request("/")
    assert status == "200 OK", f"Expected 200 OK, got {status}"
    assert b"<!DOCTYPE html>" in body
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    print("  -> Passed!")

    print("Testing 2: GET / with JSON Accept header")
    status, headers, body = simulate_request("/", headers={"Accept": "application/json"})
    assert status == "200 OK", f"Expected 200 OK, got {status}"
    data = json.loads(body.decode("utf-8"))
    assert data["status"] == "healthy"
    assert "version" in data
    print("  -> Passed!")

    print("Testing 3: GET /api/health (Minimal diagnostic check)")
    status, headers, body = simulate_request("/api/health")
    assert status == "200 OK"
    data = json.loads(body.decode("utf-8"))
    assert data["status"] == "healthy"
    assert "gemini_configured" in data
    assert "gemini_masked_key" not in data
    assert "tavily_configured" in data
    print("  -> Passed! (No secret leakage)")

    print("Testing 4: GET /api/demo")
    status, headers, body = simulate_request("/api/demo")
    assert status == "200 OK"
    data = json.loads(body.decode("utf-8"))
    assert data["success"] is True
    assert "10.5220/0012937100004508" in str(data)
    print("  -> Passed!")

    print("Testing 5: GET /api/sessions")
    status, headers, body = simulate_request("/api/sessions")
    assert status == "200 OK"
    data = json.loads(body.decode("utf-8"))
    assert data["success"] is True
    assert "sessions" in data
    print("  -> Passed!")

    print("Testing 6: POST /api/research - Content-Type validation")
    status, headers, body = simulate_request("/api/research", method="POST", body="hello", headers={"Content-Type": "text/plain"})
    assert "415" in status
    print("  -> Passed! (Rejected invalid Content-Type with 415)")

    print("Testing 7: POST /api/research - Short topic validation")
    status, headers, body = simulate_request("/api/research", method="POST", body=json.dumps({"topic": "a"}), headers={"Content-Type": "application/json"})
    assert "400" in status
    print("  -> Passed! (Rejected short topic with 400)")

    print("Testing 8: POST /api/research?async=true - Asynchronous submission")
    status, headers, body = simulate_request(
        "/api/research?async=true",
        method="POST",
        body=json.dumps({"topic": "Zero-Trust Architecture in Critical Cloud Healthcare", "gemini_api_key": "test_key"}),
        headers={"Content-Type": "application/json"}
    )
    assert "202" in status
    data = json.loads(body.decode("utf-8"))
    assert data["success"] is True
    assert "job_id" in data
    assert "/api/jobs/" in data["poll_url"]
    job_id = data["job_id"]
    print(f"  -> Passed! (Job queued with ID {job_id})")

    print(f"Testing 9: GET /api/jobs/{job_id}")
    status, headers, body = simulate_request(f"/api/jobs/{job_id}")
    assert status == "200 OK"
    data = json.loads(body.decode("utf-8"))
    assert data["success"] is True
    assert data["job"]["id"] == job_id
    assert "status" in data["job"]
    print("  -> Passed!")

    print("Testing 10: 404 handler with JSON structure")
    status, headers, body = simulate_request("/api/nonexistent_route")
    assert "404" in status
    data = json.loads(body.decode("utf-8"))
    assert data["error"] == "Not Found"
    assert "request_id" in data
    print("  -> Passed!")

    print("Testing 11: POST /api/config/validate (Live credential test)")
    status, headers, body = simulate_request(
        "/api/config/validate",
        method="POST",
        body=json.dumps({"gemini_api_key": "invalid_probe_key"}),
        headers={"Content-Type": "application/json"}
    )
    assert "400" in status
    data = json.loads(body.decode("utf-8"))
    assert data.get("success") is False or data.get("gemini_valid") is False
    assert "error" in data
    print("  -> Passed! (Validated that invalid keys are safely caught)")

    print("Testing 12: GET /api/download/pdf?id=demo")
    status, headers, body = simulate_request("/api/download/pdf?id=demo")
    assert status == "200 OK"
    assert headers.get("Content-Type") == "application/pdf"
    assert len(body) > 1000
    assert body.startswith(b"%PDF")
    print("  -> Passed! (Demo PDF download works)")

    print("Testing 13: GET /api/download/pptx?id=demo")
    status, headers, body = simulate_request("/api/download/pptx?id=demo")
    assert status == "200 OK"
    assert "presentation" in headers.get("Content-Type", "")
    assert len(body) > 10000
    print("  -> Passed! (Demo PPTX download works)")

    print("Testing 14: GET /api/config/status")
    status, headers, body = simulate_request("/api/config/status")
    assert status == "200 OK"
    data = json.loads(body.decode("utf-8"))
    assert "server_gemini_configured" in data
    assert "supported_models" in data
    print("  -> Passed!")

    print("Testing 15: POST /api/config/clear (Session cookie clearance)")
    status, headers, body = simulate_request("/api/config/clear", method="POST")
    assert status == "200 OK"
    data = json.loads(body.decode("utf-8"))
    assert data["success"] is True
    print("  -> Passed!")

    print("Testing 16: POST /api/config/gemini - Rejects invalid key")
    status, headers, body = simulate_request(
        "/api/config/gemini",
        method="POST",
        body=json.dumps({"gemini_api_key": "bad_key"}),
        headers={"Content-Type": "application/json"}
    )
    assert "400" in status
    data = json.loads(body.decode("utf-8"))
    assert data["success"] is False
    assert "error" in data
    print("  -> Passed! (Invalid Gemini key rejected with 400)")

    print("Testing 17: POST /api/config/gemini - Action delete clears Gemini key")
    status, headers, body = simulate_request(
        "/api/config/gemini",
        method="POST",
        body=json.dumps({"action": "delete"}),
        headers={"Content-Type": "application/json"}
    )
    assert status == "200 OK"
    data = json.loads(body.decode("utf-8"))
    assert data["success"] is True
    assert data["gemini_valid"] is False
    print("  -> Passed! (Gemini deletion endpoint works)")

    print("Testing 18: POST /api/config/tavily - Action delete clears Tavily key")
    status, headers, body = simulate_request(
        "/api/config/tavily",
        method="POST",
        body=json.dumps({"action": "delete"}),
        headers={"Content-Type": "application/json"}
    )
    assert status == "200 OK"
    data = json.loads(body.decode("utf-8"))
    assert data["success"] is True
    assert data["tavily_valid"] is False
    print("  -> Passed! (Tavily deletion endpoint works)")

    print("Testing 19: POST /api/jobs - Job queue endpoint")
    status, headers, body = simulate_request(
        "/api/jobs",
        method="POST",
        body=json.dumps({"topic": "Zero-Trust Architecture in Critical Cloud Healthcare", "gemini_api_key": "test_key"}),
        headers={"Content-Type": "application/json"}
    )
    assert "202" in status
    data = json.loads(body.decode("utf-8"))
    assert data["success"] is True
    assert "job_id" in data
    print("  -> Passed! (Jobs endpoint returned 202 Accepted)")

    print("\nALL 19 SIMULATION TESTS PASSED!")

if __name__ == "__main__":
    run_tests()
