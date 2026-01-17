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
    Generate a complete ATS-friendly tailored resume DOCX.
    Rebuilds the resume from extracted text + tailored content.
    
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
    
    # 1. PROFESSIONAL SUMMARY (tailored)
    doc.add_heading('Professional Summary', level=1)
    summary_para = doc.add_paragraph(tailored_summary)
    summary_para.space_after = Pt(12)
    
    # 2. KEY ACHIEVEMENTS (tailored)
    if tailored_bullets:
        doc.add_heading('Key Achievements', level=1)
        for bullet in tailored_bullets:
            bullet_text = bullet.get('text', '')
            if bullet_text:
                para = doc.add_paragraph(bullet_text, style='List Bullet')
                para.space_after = Pt(6)
        doc.add_paragraph()  # Spacing
    
    # 3. FULL RESUME CONTENT (structured from original text)
    if original_resume_text:
        # Parse resume text into structured sections
        sections = _parse_resume_sections(original_resume_text)
        
        # Render each section
        for section_name, section_content in sections.items():
            if section_content.strip():
                doc.add_heading(section_name, level=1)
                
                # Process section content
                lines = section_content.split('\n')
                current_para = None
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        if current_para:
                            current_para = None
                        continue
                    
                    # Check if it's a bullet point
                    if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                        bullet_text = line.lstrip('•-* ').strip()
                        if bullet_text:
                            para = doc.add_paragraph(bullet_text, style='List Bullet')
                            para.space_after = Pt(4)
                    # Check if it's a heading (all caps or title case)
                    elif line.isupper() or (len(line) < 50 and ':' not in line):
                        if current_para:
                            doc.add_paragraph()  # Spacing
                        para = doc.add_paragraph(line)
                        para.runs[0].bold = True
                        para.space_after = Pt(6)
                        current_para = para
                    else:
                        # Regular paragraph
                        if current_para:
                            current_para.add_run(' ' + line)
                        else:
                            para = doc.add_paragraph(line)
                            para.space_after = Pt(6)
                            current_para = para
                
                doc.add_paragraph()  # Section spacing
    
    # Save to BytesIO
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def _parse_resume_sections(resume_text: str) -> Dict[str, str]:
    """
    Parse resume text into structured sections (EXPERIENCE, EDUCATION, SKILLS, etc.).
    Uses heuristics to detect section headers.
    """
    sections = {}
    current_section = None
    current_content = []
    
    # Common section headers (case-insensitive)
    section_keywords = {
        'experience': ['EXPERIENCE', 'WORK EXPERIENCE', 'PROFESSIONAL EXPERIENCE', 'EMPLOYMENT', 'CAREER'],
        'education': ['EDUCATION', 'ACADEMIC', 'QUALIFICATIONS'],
        'skills': ['SKILLS', 'TECHNICAL SKILLS', 'COMPETENCIES', 'CORE COMPETENCIES'],
        'projects': ['PROJECTS', 'KEY PROJECTS'],
        'certifications': ['CERTIFICATIONS', 'CERTIFICATES', 'LICENSES'],
        'awards': ['AWARDS', 'HONORS', 'ACHIEVEMENTS'],
        'languages': ['LANGUAGES', 'LANGUAGE'],
    }
    
    lines = resume_text.split('\n')
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            if current_section and current_content:
                current_content.append('')
            continue
        
        # Check if line is a section header
        line_upper = line_stripped.upper()
        detected_section = None
        
        for section_name, keywords in section_keywords.items():
            for keyword in keywords:
                if keyword in line_upper or line_upper.startswith(keyword):
                    detected_section = section_name
                    break
            if detected_section:
                break
        
        # Also check if line is all caps and short (likely a header)
        if not detected_section and len(line_stripped) < 50 and line_stripped.isupper() and len(line_stripped.split()) <= 5:
            # Try to match common patterns
            if any(kw in line_upper for kw in ['EXPERIENCE', 'EDUCATION', 'SKILL', 'PROJECT', 'CERT', 'AWARD', 'LANGUAGE']):
                detected_section = 'other'
        
        if detected_section:
            # Save previous section
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            # Start new section
            current_section = detected_section
            current_content = []
        else:
            # Add to current section
            if current_section:
                current_content.append(line_stripped)
            else:
                # Content before first section -> add to "header" or "summary"
                if 'header' not in sections:
                    sections['header'] = ''
                sections['header'] += line_stripped + '\n'
    
    # Save last section
    if current_section:
        sections[current_section] = '\n'.join(current_content).strip()
    
    # If no sections detected, return all as "content"
    if not sections:
        sections['content'] = resume_text
    
    return sections


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
