"""
Klein AI 2.0 - Security, Citation Auditing, Database Persistence & Job Queue Test Suite
"""
import uuid
import json
import pytest
from datetime import datetime, timezone

from core.search_engine import SearchEngine
from core.database import (
    init_db,
    save_session,
    get_session,
    list_sessions,
    delete_session,
    check_db_health,
)
from core.citation_auditor import (
    CitationAuditor,
    STATUS_METADATA_MATCHED,
    STATUS_CLAIM_SUPPORTED,
    STATUS_VERIFICATION_FAILED
)
from core.job_queue import JobManager
from app import InMemoryRateLimiter


# 1. SSRF & NETWORK SECURITY TESTS
def test_ssrf_blocks_private_and_metadata_ips():
    """Verify that private IP ranges, loopback, and cloud metadata endpoints are strictly blocked."""
    unsafe_targets = [
        "http://localhost:8080/admin",
        "http://127.0.0.1:8000/keys",
        "http://127.0.0.2:80",
        "http://169.254.169.254/latest/meta-data/",  # AWS/GCP/Azure IMDS
        "http://10.0.0.1/internal-api",
        "http://192.168.1.1/router",
        "http://172.16.0.1/private",
        "http://[::1]/ipv6-loopback",
        "file:///etc/passwd",
        "ftp://internal.repo/data",
        "javascript:alert(1)"
    ]
    for url in unsafe_targets:
        is_safe, reason = SearchEngine.is_safe_url(url)
        assert not is_safe, f"Expected unsafe for {url}, got safe! Reason: {reason}"
        assert reason is not None


def test_ssrf_permits_safe_public_fqdns():
    """Verify that legitimate public domains are permitted through the security filter."""
    safe_targets = [
        "https://www.nature.com/articles/nature12345",
        "https://doi.org/10.1016/j.array.2025.100586",
        "https://arxiv.org/abs/2301.00001",
        "https://api.crossref.org/works"
    ]
    for url in safe_targets:
        is_safe, reason = SearchEngine.is_safe_url(url)
        assert is_safe, f"Expected safe for {url}, got rejected with reason: {reason}"


# 2. DATABASE PERSISTENCE & MIGRATION TESTS
def test_database_persistence_crud_and_uuid():
    """Verify full UUIDv4 session persistence, UTC timestamps, and data integrity."""
    init_db()
    health = check_db_health()
    assert health["connected"] is True

    test_session_id = str(uuid.uuid4())
    test_topic = "Post-Quantum Cryptography in Distributed Ledger Infrastructure"
    test_payload = {
        "blueprint": {"topic_normalized": "Post-Quantum Cryptography"},
        "summary": "Synthesized quantum-resistant cryptographic validation."
    }

    # Save session
    saved = save_session(
        session_id=test_session_id,
        topic=test_topic,
        status="completed",
        source_count=5,
        summary=test_payload["summary"],
        data=test_payload,
        user_id="researcher-001"
    )
    assert saved is True

    # Retrieve session
    fetched = get_session(test_session_id)
    assert fetched is not None
    assert fetched["id"] == test_session_id
    assert fetched["topic"] == test_topic
    assert fetched["data"]["summary"] == test_payload["summary"]

    # Verify UTC timestamp structure
    created_at = fetched["created_at"]
    assert "T" in created_at

    # Delete session
    deleted = delete_session(test_session_id)
    assert deleted is True
    assert get_session(test_session_id) is None


# 3. CITATION VERIFICATION & CLAIM MAPPING TESTS
def test_citation_doi_metadata_negotiation():
    """Verify authentic DOI resolves real metadata from official DOI registries."""
    doi = "10.6028/NIST.SP.800-207"
    meta = CitationAuditor.query_doi_metadata(doi)
    assert meta is not None
    assert meta["doi"] == doi
    assert "Rose" in str(meta["authors"]) or "NIST" in str(meta)


def test_claim_to_evidence_mapping():
    """Verify empirical claim-to-passage matching with semantic keyword correlation."""
    claims = [
        "Zero-Trust Architecture eliminates implicit trust from enterprise medical networks.",
        "Completely unrelated fabricated claim about Martian atmospheric pressure."
    ]
    sources = [
        {
            "title": "NIST SP 800-207 Zero Trust Architecture",
            "url": "https://doi.org/10.6028/NIST.SP.800-207",
            "content": "Zero-Trust Architecture eliminates implicit trust in enterprise medical networks and requires continuous validation."
        }
    ]
    mapped = CitationAuditor.map_claims_to_evidence(claims, sources)
    assert len(mapped) == 2
    assert mapped[0]["status"] == STATUS_CLAIM_SUPPORTED
    assert mapped[1]["status"] in ("UNVERIFIED", "NO_EVIDENCE_FOUND")


# 4. BACKGROUND ASYNCHRONOUS JOB QUEUE TESTS
def test_job_queue_lifecycle():
    """Verify asynchronous job manager lifecycle: create, update, log, complete."""
    jm = JobManager()
    job_id = jm.create_job(topic="Test Investigation Job", user_id="test-user")
    assert job_id is not None
    assert len(job_id) == 36  # UUID format

    job = jm.get_job(job_id)
    assert job["status"] == "queued"
    assert job["progress"] == 0

    jm.update_progress(job_id, stage="Synthesizing Literature", progress=45, log_msg="Processing Step 8")
    job = jm.get_job(job_id)
    assert job["status"] == "running"
    assert job["progress"] == 45
    assert any("Processing Step 8" in l for l in job["logs"])

    jm.mark_completed(job_id, result={"findings": "verified"})
    job = jm.get_job(job_id)
    assert job["status"] == "completed"
    assert job["progress"] == 100
    assert job["result"]["findings"] == "verified"


# 5. RATE LIMITER SECURITY TESTS
def test_rate_limiter_enforces_threshold():
    """Verify sliding-window rate limiter rejects requests that exceed the allocated limit."""
    limiter = InMemoryRateLimiter()
    client = "198.51.100.42"

    # Allow up to 5 requests in window
    for _ in range(5):
        assert limiter.is_allowed(client, limit=5, window_seconds=10) is True

    # 6th request must be rejected
    assert limiter.is_allowed(client, limit=5, window_seconds=10) is False
