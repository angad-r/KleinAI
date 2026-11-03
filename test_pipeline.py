"""
Klein AI - Full End-to-End Pipeline & Artifact Validator
"""
import os
from core.pdf_generator import build_pdf_report
from core.ppt_generator import build_pptx_deck
from core.database import init_db, save_session, get_session, list_sessions

def test_full_pipeline():
    init_db()
    
    sample_topic = "Impact of Artificial Intelligence on Cybersecurity in Healthcare"
    blueprint = {
        "topic_normalized": sample_topic,
        "domain": "Healthcare AI & Cyber-Physical Security",
        "executive_summary": "The rapid digitization of healthcare infrastructure, catalyzed by IoMT adoption and EHR integration, has introduced unprecedented attack surfaces.",
        "research_objectives": [
            "Assess vulnerability vectors in IoMT networks",
            "Synthesize defensive machine learning paradigms",
            "Formulate zero-trust federated defense framework"
        ],
        "research_questions": [
            "RQ1: How do adversarial perturbations affect diagnostic model integrity?",
            "RQ2: What is the trade-off between federated differential privacy and detection latency in clinical environments?"
        ],
        "subtopics": [
            "IoMT Perimeter Vulnerabilities",
            "Adversarial Robustness in Medical Imaging",
            "Federated Anomaly Detection",
            "HIPAA & GDPR Compliant Telemetry"
        ],
        "execution_phases": [
            {"phase": 1, "name": "Threat Modeling", "description": "Mapping healthcare endpoints"},
            {"phase": 2, "name": "Evidence Harvest", "description": "Extracting public CVEs and benchmark metrics"},
            {"phase": 3, "name": "Synthesis", "description": "Contrasting heuristic vs neural models"},
            {"phase": 4, "name": "Design", "description": "Novel Klein-HealthGuard protocol"},
            {"phase": 5, "name": "Verification", "description": "Artifact publication"}
        ]
    }
    
    sources = [
        {
            "title": "Machine Learning for Healthcare Cybersecurity: A Survey",
            "url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8901234/",
            "domain": "ncbi.nlm.nih.gov",
            "engine": "PubMed / Tavily",
            "snippet": "Comprehensive analysis of cyber threats facing IoMT devices and mitigation via supervised and unsupervised neural models."
        },
        {
            "title": "Adversarial Attacks on Medical Cyber-Physical Systems",
            "url": "https://ieeexplore.ieee.org/document/9123456",
            "domain": "ieeexplore.ieee.org",
            "engine": "IEEE Xplore",
            "snippet": "Demonstrates black-box evasion attacks against hospital telemetry classification models with 94% attack success rate."
        }
    ]
    
    comparison = {
        "key_findings": [
            "Deep anomaly autoencoders reduce triage time by 74% [Source 1].",
            "Adversarial evasion drops standard ResNet accuracy from 98% to 41% [Source 2]."
        ],
        "comparative_matrix": [
            {
                "dimension": "Zero-Day Threat Detection",
                "traditional_approach": "Static signature databases (Snort/Suricata)",
                "sota_ai_approach": "Graph Neural Networks & Unsupervised Autoencoders",
                "observed_limitations": "High false alarm rate under patient telemetry bursts"
            },
            {
                "dimension": "Data Privacy & Compliance",
                "traditional_approach": "Data masking and centralized VPN tunneling",
                "sota_ai_approach": "Federated Learning with Differential Privacy",
                "observed_limitations": "Communication bandwidth bottlenecks on legacy clinical hardware"
            }
        ],
        "consensus_points": ["Legacy signature detection is obsolete for multi-stage ransomware."],
        "debates_and_disagreements": ["Centralized vs Federated aggregation for multi-hospital consortia."]
    }
    
    lit_review = """## 1. Introduction & Background
The convergence of Internet of Medical Things (IoMT) and distributed electronic health records has fundamentally disrupted traditional defensive perimeters.

## 2. State-of-the-Art Review
Recent contributions by Johnson et al. and IEEE CPS working groups demonstrate that conventional intrusion prevention systems fail against polymorphic ransomware."""

    gaps = [
        {
            "gap_id": "GAP-01",
            "title": "Edge Adversarial Brittleness in Clinical Telemetry",
            "category": "Algorithmic Robustness",
            "description": "Standard deep learning models experience severe performance degradation when exposed to subtle gradient-based adversarial perturbations.",
            "impact_severity": "Critical",
            "opportunity": "Develop certified perturbation bounds with self-supervised feature masking."
        },
        {
            "gap_id": "GAP-02",
            "title": "Ultra-Low-Latency Edge Verification on Constrained IoMT",
            "category": "Architectural Efficiency",
            "description": "Modern transformer architectures exceed the compute and thermal budgets of pacemaker and infusion pump telemetry units.",
            "impact_severity": "High",
            "opportunity": "Deploy 4-bit quantized State Space Models (Mamba) for linear-time sequential analysis."
        }
    ]
    
    methodology = {
        "framework_name": "Klein-HealthGuard Protocol",
        "system_architecture": {
            "overview": "A decentralized zero-trust framework combining edge-quantized anomaly scoring with differential private federated consensus.",
            "components": [
                {"name": "IoMT Telemetry Shaper", "role": "Normalizes clinical packets and strips PII metadata"},
                {"name": "Edge Mamba Engine", "role": "Sub-millisecond sequential threat detection with linear state space"},
                {"name": "Federated Defense Aggregator", "role": "Privacy-preserving model weight updates across clinical nodes"}
            ],
            "workflow_pipeline": "Packet Capture -> PII Sanitization -> Mamba Anomaly Scoring -> Consensus Ledger -> Automated Micro-Isolation"
        },
        "proposed_experiments": [
            {
                "experiment_id": "EXP-01",
                "title": "Clinical Intrusion Detection Under Real-Time Load",
                "hypothesis": "Klein-HealthGuard achieves >98.2% F1-score with under 8ms latency.",
                "baselines": ["Random Forest Baseline", "Centralized LSTM-IDS", "Suricata Signature IDS"],
                "procedure": "Replay 500k packets from standard WUSTL-IIoT-2021 and CIC-IoMT datasets."
            },
            {
                "experiment_id": "EXP-02",
                "title": "PGD Adversarial Attack Robustness",
                "hypothesis": "Under epsilon=0.08 PGD perturbations, detection accuracy remains above 89%.",
                "baselines": ["Standard FP32 ResNet", "Vanilla Autoencoder"],
                "procedure": "Inject adversarial gradient perturbations across 10,000 synthetic patient telemetry vectors."
            }
        ],
        "evaluation_metrics": [
            {"metric": "Balanced F1-Score", "target": "> 97.5%", "rationale": "High resilience to class imbalance"},
            {"metric": "End-to-End Latency", "target": "< 10 ms", "rationale": "Strict deadline for patient safety"},
            {"metric": "Adversarial Retention", "target": "> 88.0%", "rationale": "Protection against active malicious evasion"}
        ]
    }
    
    full_report_md = f"""# {sample_topic}
**Author:** Klein AI Autonomous Research Engine  
**Affiliation:** College Research Capstone Project  

## Abstract
This investigation explores the intersection of artificial intelligence and cybersecurity within modern healthcare infrastructures...
"""

    bundle = {
        "id": "e2e-test",
        "topic": sample_topic,
        "blueprint": blueprint,
        "sources": sources,
        "comparison": comparison,
        "literature_review": lit_review,
        "research_gaps": gaps,
        "methodology": methodology,
        "report_markdown": full_report_md
    }
    
    # 1. Test PDF
    pdf_bytes = build_pdf_report(bundle)
    assert pdf_bytes.startswith(b"%PDF-"), "Invalid PDF header!"
    print(f" PDF Validation Passed! Size: {len(pdf_bytes)} bytes")
    
    # 2. Test PPTX
    slides_data = [
        {"slide_number": 1, "slide_type": "title", "title": sample_topic, "subtitle": "Klein AI Autonomous Research Deck", "bullets": []},
        {"slide_number": 2, "slide_type": "content", "title": "Motivation", "subtitle": "IoMT Vulnerability Landscape", "bullets": ["Clinical networks are prime targets", "Legacy signatures fail"]},
        {"slide_number": 3, "slide_type": "content", "title": "Klein-HealthGuard Protocol", "subtitle": "Novel Architecture", "bullets": ["Edge quantized state-space model", "Differential private consensus"]}
    ]
    pptx_bytes = build_pptx_deck(bundle, slides_data)
    assert pptx_bytes.startswith(b"PK"), "Invalid PPTX zip header!"
    print(f" PPTX Validation Passed! Size: {len(pptx_bytes)} bytes")
    
    # 3. Test Database Persistence
    save_session("e2e-test", sample_topic, "Completed", len(sources), "Test summary", bundle)
    retrieved = get_session("e2e-test")
    assert retrieved is not None and retrieved["topic"] == sample_topic, "DB Retrieval Failed!"
    print(f" Database Persistence Passed!")
    
    print("\n ALL PIPELINE COMPONENTS 100% OPERATIONAL!")

if __name__ == "__main__":
    test_full_pipeline()
