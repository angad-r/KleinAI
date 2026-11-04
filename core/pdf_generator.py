"""
Klein AI - Academic PDF Report Generator
Built using ReportLab with modern typography, styled tables, callout blocks, and custom headers/footers.
"""
import io
import re
from datetime import datetime
from typing import Dict, Any, List

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and display 'Page X of Y' and running header."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        if self._pageNumber > 1:
            self.saveState()
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#475569"))
            
            # Running header
            self.drawString(54, 755, "KLEIN AI — AUTONOMOUS SCIENTIFIC RESEARCH REPORT")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 747, 558, 747)

            # Footer
            self.line(54, 45, 558, 45)
            self.setFont("Helvetica", 8)
            self.drawString(54, 32, "Confidential & Academic Deliverable • Generated with Klein AI Research Engine")
            page_text = f"Page {self._pageNumber} of {page_count}"
            self.drawRightString(558, 32, page_text)
            self.restoreState()

def clean_text_for_pdf(text: str) -> str:
    """Sanitize markdown tags, smart punctuation, and unicode symbols for clean ReportLab XML parsing."""
    if not text:
        return ""
    # Normalize typographical punctuation
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    text = text.replace("—", " - ").replace("–", "-").replace("…", "...")
    # Strip emojis and unsupported unicode code points that crash standard PDF Helvetica fonts
    text = re.sub(r"[^\x00-\x7F\xA0-\xFF]", "", text)
    # Remove code fences and clean backticks
    text = re.sub(r"```[a-zA-Z]*\n?", "", text)
    text = text.replace("`", "")
    # Escape raw XML characters first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Convert Markdown formatting to allowed ReportLab XML tags
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", text)
    return text

def build_pdf_report(research_data: Dict[str, Any]) -> bytes:
    """Generate professional multi-page PDF research paper as bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=10
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#4338CA"),
        spaceAfter=15
    )
    meta_style = ParagraphStyle(
        'MetaStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155")
    )
    h1_style = ParagraphStyle(
        'HeadingOne',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )
    h2_style = ParagraphStyle(
        'HeadingTwo',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#334155"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=6
    )
    callout_style = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#1E1B4B")
    )
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1E293B")
    )
    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.white
    )

    story = []

    # 1. Document Title & Subtitle Banner
    topic = research_data.get("topic", "Autonomous Academic Research")
    blueprint = research_data.get("blueprint", {})
    normalized_topic = blueprint.get("topic_normalized", topic)
    
    story.append(Paragraph(clean_text_for_pdf(normalized_topic), title_style))
    story.append(Paragraph("Autonomous Comprehensive Research Report & Technical Whitepaper", subtitle_style))
    
    # Metadata Header Box
    created_at = datetime.now().strftime("%B %d, %Y")
    sources = research_data.get("sources", [])
    meta_info = [
        [
            Paragraph(f"<b>Author:</b> Klein AI Autonomous Agent<br/><b>Project Team:</b> 4-Member Research Team", meta_style),
            Paragraph(f"<b>Date:</b> {created_at}<br/><b>Sources Analyzed:</b> {len(sources)} Verified Citations", meta_style),
            Paragraph(f"<b>Domain:</b> {blueprint.get('domain', 'Interdisciplinary AI')}<br/><b>Status:</b> Peer Review Ready", meta_style),
        ]
    ]
    meta_table = Table(meta_info, colWidths=[180, 160, 164])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#E2E8F0")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 14))

    # 2. Executive Abstract Callout
    exec_summary = blueprint.get("executive_summary", "")
    if exec_summary:
        story.append(Paragraph("Executive Abstract", h2_style))
        abstract_cell = [[Paragraph(clean_text_for_pdf(exec_summary), callout_style)]]
        abstract_table = Table(abstract_cell, colWidths=[504])
        abstract_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EEF2FF")),
            ('BOX', (0,0), (-1,-1), 1.5, colors.HexColor("#6366F1")),
            ('PADDING', (0,0), (-1,-1), 10),
        ]))
        story.append(abstract_table)
        story.append(Spacer(1, 14))

    # 3. Research Objectives & Formal Questions
    questions = blueprint.get("research_questions", [])
    if questions:
        story.append(Paragraph("1. Research Objectives & Core Questions", h1_style))
        for idx, q in enumerate(questions, 1):
            story.append(Paragraph(f"<b>RQ{idx}:</b> {clean_text_for_pdf(q)}", body_style))
        story.append(Spacer(1, 10))

    # 4. Comparative Synthesis Matrix
    comparison = research_data.get("comparison", {})
    matrix = comparison.get("comparative_matrix", [])
    if matrix:
        story.append(Paragraph("2. Evidence Synthesis & Comparative Matrix", h1_style))
        matrix_data = [
            [
                Paragraph("Research Dimension", table_header_style),
                Paragraph("Traditional Paradigm", table_header_style),
                Paragraph("State-of-the-Art AI Approach", table_header_style),
                Paragraph("Remaining Limitations", table_header_style),
            ]
        ]
        for row in matrix:
            matrix_data.append([
                Paragraph(clean_text_for_pdf(row.get("dimension", "")), table_cell_style),
                Paragraph(clean_text_for_pdf(row.get("traditional_approach", "")), table_cell_style),
                Paragraph(clean_text_for_pdf(row.get("sota_ai_approach", "")), table_cell_style),
                Paragraph(clean_text_for_pdf(row.get("observed_limitations", "")), table_cell_style),
            ])
        matrix_table = Table(matrix_data, colWidths=[120, 124, 130, 130])
        matrix_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E293B")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(matrix_table)
        story.append(Spacer(1, 14))

    # 5. Literature Review
    lit_review = research_data.get("literature_review", "")
    if lit_review:
        story.append(Paragraph("3. Scholarly Literature Review", h1_style))
        paragraphs = lit_review.split("\n\n")
        for p in paragraphs:
            p_clean = p.strip()
            if not p_clean:
                continue
            if p_clean.startswith("#"):
                p_text = re.sub(r"^#+\s*", "", p_clean)
                story.append(Paragraph(clean_text_for_pdf(p_text), h2_style))
            elif p_clean.startswith("-") or p_clean.startswith("*"):
                story.append(Paragraph(f"• {clean_text_for_pdf(p_clean[1:].strip())}", body_style))
            else:
                story.append(Paragraph(clean_text_for_pdf(p_clean), body_style))
        story.append(Spacer(1, 12))

    # 6. Critical Research Gaps
    gaps = research_data.get("research_gaps", [])
    if gaps:
        story.append(Paragraph("4. Critical Research Gaps & Open Challenges", h1_style))
        gaps_data = [
            [
                Paragraph("ID", table_header_style),
                Paragraph("Research Gap Area", table_header_style),
                Paragraph("Severity", table_header_style),
                Paragraph("Description & Strategic Opportunity", table_header_style),
            ]
        ]
        for g in gaps:
            gaps_data.append([
                Paragraph(g.get("gap_id", "GAP"), table_cell_style),
                Paragraph(f"<b>{clean_text_for_pdf(g.get('title', ''))}</b><br/><i>{clean_text_for_pdf(g.get('category', ''))}</i>", table_cell_style),
                Paragraph(clean_text_for_pdf(g.get("impact_severity", "High")), table_cell_style),
                Paragraph(f"{clean_text_for_pdf(g.get('description', ''))}<br/><b>Opportunity:</b> {clean_text_for_pdf(g.get('opportunity', ''))}", table_cell_style),
            ])
        gaps_table = Table(gaps_data, colWidths=[45, 140, 65, 254])
        gaps_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#4F46E5")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(gaps_table)
        story.append(Spacer(1, 14))

    # 7. Proposed Methodology & Architecture
    methodology = research_data.get("methodology", {})
    if methodology:
        framework_name = methodology.get("framework_name", "Novel Research Architecture")
        story.append(Paragraph(f"5. Proposed Methodology: {clean_text_for_pdf(framework_name)}", h1_style))
        arch = methodology.get("system_architecture", {})
        if arch.get("overview"):
            story.append(Paragraph(f"<b>Architectural Overview:</b> {clean_text_for_pdf(arch.get('overview'))}", body_style))
        
        components = arch.get("components", [])
        if components:
            story.append(Paragraph("Core System Components:", h2_style))
            for c in components:
                story.append(Paragraph(f"• <b>{clean_text_for_pdf(c.get('name', ''))}:</b> {clean_text_for_pdf(c.get('role', ''))}", body_style))
        
        if arch.get("workflow_pipeline"):
            story.append(Paragraph(f"<b>End-to-End Pipeline:</b> {clean_text_for_pdf(arch.get('workflow_pipeline'))}", body_style))
        story.append(Spacer(1, 10))

    # 8. Proposed Experiments & Benchmarks
    experiments = methodology.get("proposed_experiments", [])
    if experiments:
        story.append(Paragraph("6. Experimental Design & Hypotheses", h1_style))
        for exp in experiments:
            story.append(Paragraph(f"<b>{exp.get('experiment_id', 'EXP')}: {clean_text_for_pdf(exp.get('title', ''))}</b>", h2_style))
            story.append(Paragraph(f"<b>Hypothesis:</b> {clean_text_for_pdf(exp.get('hypothesis', ''))}", body_style))
            baselines = ", ".join(exp.get("baselines", []))
            if baselines:
                story.append(Paragraph(f"<b>Baselines:</b> {clean_text_for_pdf(baselines)}", body_style))
            story.append(Paragraph(f"<b>Protocol:</b> {clean_text_for_pdf(exp.get('procedure', ''))}", body_style))
            story.append(Spacer(1, 4))
        story.append(Spacer(1, 10))

    # 9. Evaluation Metrics
    metrics = methodology.get("evaluation_metrics", [])
    if metrics:
        story.append(Paragraph("7. Target Evaluation Metrics", h1_style))
        metrics_data = [
            [Paragraph("Metric", table_header_style), Paragraph("Target Threshold", table_header_style), Paragraph("Scientific Rationale", table_header_style)]
        ]
        for m in metrics:
            metrics_data.append([
                Paragraph(clean_text_for_pdf(m.get("metric", "")), table_cell_style),
                Paragraph(f"<b>{clean_text_for_pdf(m.get('target', ''))}</b>", table_cell_style),
                Paragraph(clean_text_for_pdf(m.get("rationale", "")), table_cell_style),
            ])
        metrics_table = Table(metrics_data, colWidths=[160, 110, 234])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0284C7")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(metrics_table)
        story.append(Spacer(1, 14))

    # 10. Independent Peer Review Audit
    ind_review = research_data.get("independent_review", {})
    if ind_review:
        story.append(Paragraph("8. Independent Peer Review & Verification Audit", h1_style))
        review_data = [
            [Paragraph("Review Metric", table_header_style), Paragraph("Evaluation Assessment", table_header_style)]
        ]
        review_data.append([Paragraph("Completeness Score", table_cell_style), Paragraph(f"<b>{ind_review.get('completeness_score', 'N/A')}</b>", table_cell_style)])
        review_data.append([Paragraph("Citation Quality Rating", table_cell_style), Paragraph(str(ind_review.get('citation_quality_score', 'N/A')), table_cell_style)])
        review_data.append([Paragraph("Verified Citations Count", table_cell_style), Paragraph(str(ind_review.get('verified_citations_count', 0)), table_cell_style)])
        review_data.append([Paragraph("Unsupported Claims", table_cell_style), Paragraph(str(ind_review.get('unsupported_claims_count', 0)), table_cell_style)])
        review_data.append([Paragraph("Verification Verdict", table_cell_style), Paragraph(f"<b>{ind_review.get('verdict', 'REVIEW_COMPLETE')}</b>", table_cell_style)])
        if ind_review.get("critique_summary"):
            review_data.append([Paragraph("Peer Critique Summary", table_cell_style), Paragraph(clean_text_for_pdf(ind_review.get("critique_summary", "")), table_cell_style)])

        rev_table = Table(review_data, colWidths=[170, 334])
        rev_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(rev_table)
        story.append(Spacer(1, 14))

    # 11. References & Citations
    if sources:
        story.append(Paragraph("9. Verified Bibliographic References & Sources", h1_style))
        for idx, s in enumerate(sources, 1):
            title = s.get("title", "Untitled Source")
            url = s.get("url", "")
            domain = s.get("domain", "web")
            engine = s.get("engine", "Web Search")
            status = s.get("quality_badge") or s.get("extraction_status", "Audited Source")
            ref_text = f"[{idx}] <b>{clean_text_for_pdf(title)}</b> ({clean_text_for_pdf(domain)}). Status: <i>{clean_text_for_pdf(status)}</i>. URL: {clean_text_for_pdf(url)}"
            story.append(Paragraph(ref_text, body_style))

    # Build Document
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer.getvalue()
