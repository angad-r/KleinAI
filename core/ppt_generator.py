"""
Klein AI - PowerPoint Presentation (.pptx) Generator
Generates modern 16:9 widescreen presentation decks using python-pptx with stylized cards and color themes.
"""
import io
from typing import Dict, Any, List
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

# Professional Color Palette
COLOR_NAVY = RGBColor(15, 23, 42)       # #0F172A
COLOR_INDIGO = RGBColor(79, 70, 229)    # #4F46E5
COLOR_TEAL = RGBColor(13, 148, 136)     # #0D9488
COLOR_SLATE = RGBColor(71, 85, 105)     # #475569
COLOR_LIGHT_BG = RGBColor(248, 250, 252)# #F8FAFC
COLOR_BORDER = RGBColor(226, 232, 240)  # #E2E8F0
COLOR_WHITE = RGBColor(255, 255, 255)   # #FFFFFF
COLOR_ACCENT_BG = RGBColor(238, 242, 255) # #EEF2FF

def add_slide_header(slide, title_text: str, subtitle_text: str):
    """Adds a standard top banner with badge, title and subtitle."""
    # Top badge
    badge_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(8.0), Inches(0.4))
    tf_b = badge_box.text_frame
    tf_b.word_wrap = True
    p_b = tf_b.paragraphs[0]
    p_b.text = "KLEIN AI • AUTONOMOUS RESEARCH DECK"
    p_b.font.size = Pt(9)
    p_b.font.bold = True
    p_b.font.color.rgb = COLOR_INDIGO

    # Main Title
    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.7), Inches(11.7), Inches(0.8))
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title_text
    p.font.size = Pt(24)
    p.font.bold = True
    p.font.color.rgb = COLOR_NAVY

    # Subtitle
    if subtitle_text:
        p_sub = tf.add_paragraph()
        p_sub.text = subtitle_text
        p_sub.font.size = Pt(13)
        p_sub.font.color.rgb = COLOR_SLATE
        p_sub.space_before = Pt(4)

def build_pptx_deck(research_data: Dict[str, Any], slides_data: List[Dict[str, Any]]) -> bytes:
    """Builds a modern 16:9 widescreen PowerPoint presentation."""
    prs = Presentation()
    # 16:9 Widescreen dimensions
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6] # completely blank layout for custom placement

    topic = research_data.get("topic", "Research Presentation")
    blueprint = research_data.get("blueprint", {})

    for idx, slide_info in enumerate(slides_data):
        slide = prs.slides.add_slide(blank_layout)
        slide_type = slide_info.get("slide_type", "content")
        title = slide_info.get("title", f"Slide {idx+1}")
        subtitle = slide_info.get("subtitle", "")
        bullets = slide_info.get("bullets", [])

        if slide_type == "title" or idx == 0:
            # Dark Modern Title Slide
            bg_rect = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
            bg_rect.fill.solid()
            bg_rect.fill.fore_color.rgb = COLOR_NAVY
            bg_rect.line.fill.background()

            # Accent color bar
            accent_bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(1.5), Inches(0.15), Inches(3.8))
            accent_bar.fill.solid()
            accent_bar.fill.fore_color.rgb = COLOR_INDIGO
            accent_bar.line.fill.background()

            # Content box
            box = slide.shapes.add_textbox(Inches(1.4), Inches(1.5), Inches(10.5), Inches(4.5))
            tf = box.text_frame
            tf.word_wrap = True

            # Badge
            p0 = tf.paragraphs[0]
            p0.text = "AUTONOMOUS RESEARCH INVESTIGATION"
            p0.font.size = Pt(12)
            p0.font.bold = True
            p0.font.color.rgb = COLOR_TEAL

            # Main Topic
            p1 = tf.add_paragraph()
            p1.text = blueprint.get("topic_normalized", topic)
            p1.font.size = Pt(32)
            p1.font.bold = True
            p1.font.color.rgb = COLOR_WHITE
            p1.space_before = Pt(12)

            # Subtitle
            p2 = tf.add_paragraph()
            p2.text = subtitle if subtitle else "Comprehensive Empirical Synthesis, Gaps Analysis & Proposed Methodology"
            p2.font.size = Pt(16)
            p2.font.color.rgb = RGBColor(203, 213, 225)
            p2.space_before = Pt(8)

            # Presenter Metadata
            p3 = tf.add_paragraph()
            p3.text = "Author: Klein AI Autonomous Research Engine  •  Presented by: 4-Member Research Team"
            p3.font.size = Pt(12)
            p3.font.color.rgb = RGBColor(148, 163, 184)
            p3.space_before = Pt(36)

        else:
            # Standard Content Slide
            add_slide_header(slide, title, subtitle)

            # Card shape background
            card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.9), Inches(11.733), Inches(4.8))
            card.fill.solid()
            card.fill.fore_color.rgb = COLOR_LIGHT_BG
            card.line.color.rgb = COLOR_BORDER
            card.line.width = Pt(1)

            # Bullet text frame
            bullet_box = slide.shapes.add_textbox(Inches(1.2), Inches(2.2), Inches(10.9), Inches(4.2))
            tf = bullet_box.text_frame
            tf.word_wrap = True

            for b_idx, bullet in enumerate(bullets):
                p = tf.paragraphs[0] if b_idx == 0 else tf.add_paragraph()
                p.text = f"•  {bullet}"
                p.font.size = Pt(15)
                p.font.color.rgb = COLOR_NAVY
                p.space_after = Pt(14)
                p.line_spacing = 1.25

            # Slide Footer
            footer_box = slide.shapes.add_textbox(Inches(0.8), Inches(6.9), Inches(11.733), Inches(0.4))
            tff = footer_box.text_frame
            pf = tff.paragraphs[0]
            pf.text = f"Klein AI Academic Research System  |  Slide {idx+1} of {len(slides_data)}"
            pf.font.size = Pt(9)
            pf.font.color.rgb = COLOR_SLATE

    buffer = io.BytesIO()
    prs.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
