import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database import save_session, init_db
from core.demo_dataset import VERIFIED_DEMO_DATA
from scripts.test_wsgi_sim import simulate_request

init_db()
sid = str(uuid.uuid4())
save_session(
    session_id=sid,
    topic="Zero-Trust Healthcare Architecture",
    status="completed",
    source_count=4,
    summary="Test summary",
    data=VERIFIED_DEMO_DATA
)

status_pdf, headers_pdf, body_pdf = simulate_request(f"/api/download/pdf?id={sid}")
assert status_pdf == "200 OK", f"PDF status: {status_pdf}"
assert body_pdf.startswith(b"%PDF"), "Not a valid PDF header"
assert "attachment" in headers_pdf.get("Content-Disposition", "")

status_ppt, headers_ppt, body_ppt = simulate_request(f"/api/download/pptx?id={sid}")
assert status_ppt == "200 OK", f"PPT status: {status_ppt}"
assert len(body_ppt) > 5000, "PPTX too short"

print(f"DELIVERABLE DOWNLOADS VERIFIED! PDF: {len(body_pdf)} bytes, PPTX: {len(body_ppt)} bytes")
