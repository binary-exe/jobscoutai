"""
DOCX generation service for Apply Workspace.

Generates downloadable DOCX files for tailored resume and cover note.
"""

from typing import Dict, Optional, Any
from io import BytesIO

try:
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


def generate_resume_docx(
    tailored_summary: str,
    tailored_bullets: list[Dict[str, Any]],
    original_resume_text: Optional[str] = None,
) -> BytesIO:
    """
    Generate a DOCX file with tailored resume content.
    
    Returns:
        BytesIO object containing the DOCX file
    """
    if not DOCX_AVAILABLE:
        raise ImportError("python-docx not installed. Install with: pip install python-docx")
    
    doc = Document()
    
    # Set default font
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)
    
    # Add title
    title = doc.add_heading('Professional Summary', level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    
    # Add tailored summary
    summary_para = doc.add_paragraph(tailored_summary)
    summary_para.space_after = Pt(12)
    
    # Add key achievements section
    if tailored_bullets:
        doc.add_heading('Key Achievements', level=1)
        
        for bullet in tailored_bullets:
            bullet_text = bullet.get('text', '')
            if bullet_text:
                para = doc.add_paragraph(bullet_text, style='List Bullet')
                para.space_after = Pt(6)
    
    # Add original resume content if provided (as reference)
    if original_resume_text:
        doc.add_page_break()
        doc.add_heading('Full Resume (Reference)', level=1)
        
        # Split into paragraphs
        paragraphs = original_resume_text.split('\n\n')
        for para_text in paragraphs[:20]:  # Limit to first 20 paragraphs
            if para_text.strip():
                para = doc.add_paragraph(para_text.strip())
                para.space_after = Pt(6)
    
    # Save to BytesIO
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def generate_cover_note_docx(
    cover_note: str,
    job_title: Optional[str] = None,
    company_name: Optional[str] = None,
) -> BytesIO:
    """
    Generate a DOCX file with cover note.
    
    Returns:
        BytesIO object containing the DOCX file
    """
    if not DOCX_AVAILABLE:
        raise ImportError("python-docx not installed. Install with: pip install python-docx")
    
    doc = Document()
    
    # Set default font
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)
    
    # Add header (optional)
    if job_title and company_name:
        header = doc.add_paragraph()
        header.add_run(f'Re: {job_title} at {company_name}').bold = True
        header.space_after = Pt(12)
    
    # Add date
    from datetime import datetime
    date_para = doc.add_paragraph(datetime.now().strftime('%B %d, %Y'))
    date_para.space_after = Pt(12)
    
    # Add cover note content
    # Split into paragraphs
    paragraphs = cover_note.split('\n\n')
    for para_text in paragraphs:
        if para_text.strip():
            para = doc.add_paragraph(para_text.strip())
            para.space_after = Pt(12)
    
    # Add closing
    doc.add_paragraph('Sincerely,')
    doc.add_paragraph('[Your Name]')
    
    # Save to BytesIO
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def generate_combined_docx(
    tailored_summary: str,
    tailored_bullets: list[Dict[str, Any]],
    cover_note: str,
    job_title: Optional[str] = None,
    company_name: Optional[str] = None,
) -> BytesIO:
    """
    Generate a combined DOCX with both resume and cover note.
    
    Returns:
        BytesIO object containing the DOCX file
    """
    if not DOCX_AVAILABLE:
        raise ImportError("python-docx not installed. Install with: pip install python-docx")
    
    doc = Document()
    
    # Set default font
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)
    
    # Add cover note first
    if job_title and company_name:
        header = doc.add_paragraph()
        header.add_run(f'Re: {job_title} at {company_name}').bold = True
        header.space_after = Pt(12)
    
    from datetime import datetime
    date_para = doc.add_paragraph(datetime.now().strftime('%B %d, %Y'))
    date_para.space_after = Pt(12)
    
    cover_paragraphs = cover_note.split('\n\n')
    for para_text in cover_paragraphs:
        if para_text.strip():
            para = doc.add_paragraph(para_text.strip())
            para.space_after = Pt(12)
    
    doc.add_paragraph('Sincerely,')
    doc.add_paragraph('[Your Name]')
    
    # Page break
    doc.add_page_break()
    
    # Add resume content
    title = doc.add_heading('Professional Summary', level=1)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    
    summary_para = doc.add_paragraph(tailored_summary)
    summary_para.space_after = Pt(12)
    
    if tailored_bullets:
        doc.add_heading('Key Achievements', level=1)
        
        for bullet in tailored_bullets:
            bullet_text = bullet.get('text', '')
            if bullet_text:
                para = doc.add_paragraph(bullet_text, style='List Bullet')
                para.space_after = Pt(6)
    
    # Save to BytesIO
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
