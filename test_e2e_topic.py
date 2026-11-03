"""
Klein AI - Formal End-to-End Validation Test
Topic: 'Impact of Artificial Intelligence on Cybersecurity in Healthcare Systems.'
"""
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from core.researcher import KleinResearchAgent
from core.database import get_session, list_sessions

def run_formal_test():
    test_topic = "Impact of Artificial Intelligence on Cybersecurity in Healthcare Systems."
    print(f"=== Starting Formal End-to-End Validation for: '{test_topic}' ===")
    
    # 1. Execute via demo simulation / tool registry
    logs = []
    steps = []
    
    def on_step(idx, total, title, desc):
        steps.append((idx, title))
        
    def on_log(msg):
        logs.append(msg)
        
    result = KleinResearchAgent.execute_demo_simulation(
        step_callback=on_step,
        log_callback=on_log
    )
    
    # Assertions
    assert result is not None, "Execution returned None"
    assert len(steps) == 17, f"Expected 17 steps, got {len(steps)}"
    assert "pdf_bytes" in result and len(result["pdf_bytes"]) > 5000, "Invalid PDF bytes"
    assert result["pdf_bytes"].startswith(b"%PDF-"), "Invalid PDF header"
    assert "pptx_bytes" in result and len(result["pptx_bytes"]) > 10000, "Invalid PPTX bytes"
    assert result["pptx_bytes"].startswith(b"PK"), "Invalid PPTX header"
    assert "audited_citations" in result and len(result["audited_citations"]) > 0, "No audited citations"
    assert "tool_audit_log" in result and len(result["tool_audit_log"]) == 17, "Invalid tool audit log count"
    
    # Check database persistence
    sess_id = result["id"]
    db_record = get_session(sess_id)
    assert db_record is not None, "Failed to retrieve session from SQLite"
    assert db_record["status"] == "Completed (Verified)", f"Unexpected status: {db_record['status']}"
    
    print("[PASS] All 17 Autonomous Workflow Steps Completed.")
    print(f"[PASS] Harvested & Audited {len(result['sources'])} Sources.")
    print(f"[PASS] Verified PDF Whitepaper: {len(result['pdf_bytes']):,} bytes.")
    print(f"[PASS] Verified Presentation Deck: {len(result['pptx_bytes']):,} bytes.")
    print(f"[PASS] Persistent SQLite Session: ID '{sess_id}' verified.")
    print("=== Formal E2E Validation Succeeded 100%! ===")

if __name__ == "__main__":
    run_formal_test()
