"""
DOCX generation service for Apply Workspace.

Generates downloadable DOCX files for tailored resume and cover note.
Creates professional, ATS-friendly documents with proper formatting.
"""

from typing import Dict, Optional, Any, List, Tuple
from io import BytesIO
import re
import zipfile

try:
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches, Twips
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
    from docx.enum.style import WD_STYLE_TYPE
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


# ==================== Resume Section Parsing ====================

def _parse_resume_into_structure(resume_text: str) -> Dict[str, Any]:
    """
    Parse resume text into a structured format with proper sections.
    Returns a dict with: header, contact, summary, skills, experience, projects, education, certifications, etc.
    """
    result = {
        "name": "",
        "title": "",
        "location": "",
        "contact": [],  # List of {type, value, url}
        "summary": "",
        "skills": [],  # List of skill strings or {category: [skills]}
        "experience": [],  # List of {title, company, location, dates, bullets}
        "projects": [],  # List of {name, description, url, bullets}
        "education": [],  # List of {degree, school, dates}
        "certifications": [],  # List of {name, issuer, date}
        "achievements": [],  # List of strings
        "languages": [],
        "other_sections": {},  # Any unrecognized sections
    }
    
    lines = resume_text.strip().split('\n')
    if not lines:
        return result
    
    # First line is usually the name
    result["name"] = lines[0].strip()
    
    # Second line is often title/headline
    if len(lines) > 1:
        second_line = lines[1].strip()
        if not _is_contact_line(second_line) and not _is_section_header(second_line):
            result["title"] = second_line
    
    # Parse contact info from early lines
    for i, line in enumerate(lines[1:10]):  # Check first 10 lines for contact
        line = line.strip()
        if _is_contact_line(line):
            contact_items = _extract_contact_items(line)
            result["contact"].extend(contact_items)
        elif _looks_like_location(line):
            result["location"] = line
    
    # Now parse sections
    current_section = None
    current_content = []
    section_start_idx = 0
    
    # Find where sections start (after header/contact area)
    for i, line in enumerate(lines):
        if _is_section_header(line):
            section_start_idx = i
            break
    
    # Parse sections
    for i, line in enumerate(lines[section_start_idx:], section_start_idx):
        line_stripped = line.strip()
        
        if _is_section_header(line_stripped):
            # Save previous section
            if current_section:
                _save_section(result, current_section, current_content)
            current_section = _normalize_section_name(line_stripped)
            current_content = []
        elif current_section:
            current_content.append(line_stripped)
    
    # Save last section
    if current_section:
        _save_section(result, current_section, current_content)
    
    return result


def _is_contact_line(line: str) -> bool:
    """Check if line contains contact information."""
    contact_patterns = [
        r'@', r'linkedin\.com', r'github\.com', r'upwork\.com',
        r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # Phone
        r'http[s]?://', r'www\.',
    ]
    line_lower = line.lower()
    return any(re.search(p, line_lower) for p in contact_patterns)


def _looks_like_location(line: str) -> bool:
    """Check if line looks like a location."""
    location_keywords = ['remote', 'dubai', 'new york', 'london', 'berlin', 'singapore', 
                        'united states', 'united kingdom', 'uae', 'emirates', 'india']
    line_lower = line.lower()
    return any(kw in line_lower for kw in location_keywords) and len(line) < 100


def _extract_contact_items(line: str) -> List[Dict[str, str]]:
    """Extract contact items from a line."""
    items = []
    
    # Email
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', line)
    if email_match:
        items.append({"type": "email", "value": email_match.group(), "url": f"mailto:{email_match.group()}"})
    
    # LinkedIn
    linkedin_match = re.search(r'https?://(?:www\.)?linkedin\.com/[\w\-/]+', line)
    if linkedin_match:
        items.append({"type": "linkedin", "value": "LinkedIn", "url": linkedin_match.group()})
    
    # GitHub
    github_match = re.search(r'https?://(?:www\.)?github\.com/[\w\-]+', line)
    if github_match:
        items.append({"type": "github", "value": "GitHub", "url": github_match.group()})
    
    # Other URLs
    url_match = re.search(r'https?://[^\s]+', line)
    if url_match and not linkedin_match and not github_match:
        items.append({"type": "website", "value": url_match.group(), "url": url_match.group()})
    
    # Phone
    phone_match = re.search(r'\+?\d[\d\s\-\.]{8,}\d', line)
    if phone_match:
        items.append({"type": "phone", "value": phone_match.group().strip()})
    
    return items


def _is_section_header(line: str) -> bool:
    """Check if line is a section header."""
    line = line.strip()
    if not line:
        return False
    
    # Check for common section markers
    section_markers = ['◆', '■', '●', '►', '⚫', '★', '▶', '━', '═', '—']
    if any(line.startswith(m) for m in section_markers):
        return True
    
    # Check for common section names
    section_keywords = [
        'profile', 'summary', 'objective', 'about',
        'experience', 'employment', 'work history', 'career',
        'education', 'academic', 'qualification',
        'skills', 'technical', 'competencies', 'expertise',
        'projects', 'portfolio',
        'certifications', 'certificates', 'licenses',
        'achievements', 'accomplishments', 'awards', 'honors',
        'languages', 'interests', 'hobbies',
    ]
    line_lower = line.lower().strip('◆■●►⚫★▶━═—: ')
    return any(kw in line_lower for kw in section_keywords) and len(line) < 50


def _normalize_section_name(line: str) -> str:
    """Normalize section header to standard name."""
    line_lower = line.lower().strip('◆■●►⚫★▶━═—: ')
    
    if any(kw in line_lower for kw in ['profile', 'summary', 'objective', 'about']):
        return 'summary'
    if any(kw in line_lower for kw in ['experience', 'employment', 'work', 'career']):
        return 'experience'
    if any(kw in line_lower for kw in ['education', 'academic', 'qualification']):
        return 'education'
    if any(kw in line_lower for kw in ['skill', 'technical', 'competenc', 'expertise', 'stack']):
        return 'skills'
    if any(kw in line_lower for kw in ['project', 'portfolio']):
        return 'projects'
    if any(kw in line_lower for kw in ['certification', 'certificate', 'license']):
        return 'certifications'
    if any(kw in line_lower for kw in ['achievement', 'accomplishment', 'award', 'honor', 'notable']):
        return 'achievements'
    if 'language' in line_lower:
        return 'languages'
    return 'other'


def _save_section(result: Dict, section_name: str, content: List[str]) -> None:
    """Save parsed section content to result dict."""
    content_text = '\n'.join(content).strip()
    if not content_text:
        return
    
    if section_name == 'summary':
        result['summary'] = content_text
    elif section_name == 'skills':
        result['skills'] = _parse_skills(content)
    elif section_name == 'experience':
        result['experience'] = _parse_experience(content)
    elif section_name == 'projects':
        result['projects'] = _parse_projects(content)
    elif section_name == 'education':
        result['education'] = _parse_education(content)
    elif section_name == 'certifications':
        result['certifications'] = _parse_certifications(content)
    elif section_name == 'achievements':
        result['achievements'] = _parse_bullets(content)
    elif section_name == 'languages':
        result['languages'] = _parse_bullets(content)
    else:
        result['other_sections'][section_name] = content_text


def _parse_skills(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse skills section into categorized skills."""
    skills = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('—') or line.startswith('━'):
            continue
        # Check if it's a categorized skill line (Category: skill1, skill2)
        if ':' in line:
            parts = line.split(':', 1)
            category = parts[0].strip('•-* ')
            skill_list = [s.strip() for s in parts[1].split(',')]
            skills.append({"category": category, "items": skill_list})
        else:
            # Single skill or bullet point
            skill = line.strip('•-* ')
            if skill:
                skills.append({"category": None, "items": [skill]})
    return skills


def _parse_experience(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse experience section into structured entries."""
    experiences = []
    current_exp = None
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('—') or line.startswith('━'):
            continue
        
        # Check if this is a new job entry (starts with marker or contains date pattern)
        if line.startswith('⚙') or line.startswith('►') or _looks_like_job_header(line):
            if current_exp:
                experiences.append(current_exp)
            current_exp = _parse_job_header(line)
        elif current_exp:
            # This is a bullet point
            bullet = line.strip('•-* ')
            if bullet:
                current_exp['bullets'].append(bullet)
    
    if current_exp:
        experiences.append(current_exp)
    
    return experiences


def _looks_like_job_header(line: str) -> bool:
    """Check if line looks like a job title/company header."""
    # Contains date patterns like "2023 – Present", "Jan 2022 – Dec 2023"
    date_patterns = [
        r'\b20\d{2}\b',  # Year
        r'\bpresent\b',
        r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b',
    ]
    line_lower = line.lower()
    has_date = any(re.search(p, line_lower) for p in date_patterns)
    has_separator = '|' in line or '—' in line or '–' in line or ' - ' in line
    return has_date or (has_separator and len(line) < 150)


def _parse_job_header(line: str) -> Dict[str, Any]:
    """Parse a job header line into structured data."""
    result = {
        "title": "",
        "company": "",
        "location": "",
        "dates": "",
        "bullets": []
    }
    
    # Remove markers
    line = line.strip('⚙►■● ')
    
    # Try to extract dates
    date_match = re.search(r'(\w+\s+20\d{2}|\b20\d{2})\s*[–—-]\s*(\w+\s+20\d{2}|Present|\b20\d{2})', line, re.IGNORECASE)
    if date_match:
        result['dates'] = date_match.group().strip()
        line = line.replace(date_match.group(), '').strip()
    
    # Split by common separators
    separators = ['|', '—', '–', ' - ']
    parts = [line]
    for sep in separators:
        new_parts = []
        for part in parts:
            new_parts.extend(part.split(sep))
        parts = [p.strip() for p in new_parts if p.strip()]
    
    # Assign parts
    if len(parts) >= 2:
        result['title'] = parts[0].strip()
        result['company'] = parts[1].strip()
        if len(parts) >= 3:
            result['location'] = parts[2].strip()
    elif len(parts) == 1:
        result['title'] = parts[0].strip()
    
    return result


def _parse_projects(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse projects section."""
    projects = []
    current_project = None
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('—') or line.startswith('━'):
            continue
        
        # Check if this is a new project (starts with marker)
        if line.startswith('⧉') or line.startswith('►') or line.startswith('•'):
            if current_project:
                projects.append(current_project)
            project_name = line.strip('⧉►•- ')
            # Check for URL
            url_match = re.search(r'https?://[^\s]+', project_name)
            url = url_match.group() if url_match else None
            if url:
                project_name = project_name.replace(url, '').strip()
            current_project = {
                "name": project_name,
                "description": "",
                "url": url,
                "bullets": []
            }
        elif current_project:
            # This is description or bullet
            if line.startswith('URL:') or line.startswith('http'):
                url_match = re.search(r'https?://[^\s]+', line)
                if url_match:
                    current_project['url'] = url_match.group()
            else:
                current_project['bullets'].append(line.strip('•-* '))
    
    if current_project:
        projects.append(current_project)
    
    return projects


def _parse_education(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse education section."""
    education = []
    for line in lines:
        line = line.strip('•-* ')
        if not line or line.startswith('—'):
            continue
        
        entry = {"degree": "", "school": "", "dates": ""}
        
        # Extract dates
        date_match = re.search(r'\(?(\d{4})\s*[–—-]\s*(\d{4}|Present)?\)?', line, re.IGNORECASE)
        if date_match:
            entry['dates'] = date_match.group().strip('()')
            line = line.replace(date_match.group(), '').strip()
        
        # Split by common separators
        if '—' in line:
            parts = line.split('—')
        elif ' - ' in line:
            parts = line.split(' - ')
        else:
            parts = [line]
        
        if len(parts) >= 2:
            entry['degree'] = parts[0].strip()
            entry['school'] = parts[1].strip()
        else:
            entry['degree'] = line.strip()
        
        if entry['degree']:
            education.append(entry)
    
    return education


def _parse_certifications(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse certifications section."""
    certs = []
    for line in lines:
        line = line.strip('•-* ')
        if not line or line.startswith('—'):
            continue
        
        entry = {"name": "", "issuer": "", "date": ""}
        
        # Extract date
        date_match = re.search(r'\(?(Issued\s+)?\w+\s+20\d{2}\)?', line, re.IGNORECASE)
        if date_match:
            entry['date'] = date_match.group().strip('()')
            line = line.replace(date_match.group(), '').strip()
        
        # Split by separator
        if '—' in line:
            parts = line.split('—')
            entry['name'] = parts[0].strip()
            if len(parts) > 1:
                entry['issuer'] = parts[1].strip()
        else:
            entry['name'] = line.strip()
        
        if entry['name']:
            certs.append(entry)
    
    return certs


def _parse_bullets(lines: List[str]) -> List[str]:
    """Parse a list of bullet points."""
    bullets = []
    for line in lines:
        line = line.strip('•-* ')
        if line and not line.startswith('—'):
            bullets.append(line)
    return bullets


# ==================== DOCX Generation ====================

def _set_cell_margins(cell, top=0, start=0, bottom=0, end=0):
    """Set cell margins in twips."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for margin_name, margin_value in [('top', top), ('start', start), ('bottom', bottom), ('end', end)]:
        margin = OxmlElement(f'w:{margin_name}')
        margin.set(qn('w:w'), str(margin_value))
        margin.set(qn('w:type'), 'dxa')
        tcMar.append(margin)
    tcPr.append(tcMar)


def _add_horizontal_line(doc):
    """Add a horizontal line to the document."""
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(6)
    para.paragraph_format.space_after = Pt(6)
    
    # Create bottom border
    pPr = para._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '6')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), '4A4A4A')
    pBdr.append(bottom)
    pPr.append(pBdr)


def _add_section_header(doc, title: str):
    """Add a styled section header."""
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(14)
    para.paragraph_format.space_after = Pt(6)
    
    run = para.add_run(title.upper())
    run.bold = True
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(0x2C, 0x3E, 0x50)  # Dark blue
    
    # Add underline effect via border
    pPr = para._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '4')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), '2C3E50')
    pBdr.append(bottom)
    pPr.append(pBdr)


def generate_resume_docx(
    tailored_summary: str,
    tailored_bullets: list[Dict[str, Any]],
    original_resume_text: Optional[str] = None,
) -> BytesIO:
    """
    Generate a complete ATS-friendly tailored resume DOCX.
    
    Creates a professionally formatted resume with:
    - Proper header with name and contact info
    - Tailored summary section
    - Tailored key achievements
    - Original experience, education, skills formatted properly
    
    Returns:
        BytesIO object containing the DOCX file
    """
    if not DOCX_AVAILABLE:
        raise ImportError("python-docx not installed. Install with: pip install python-docx")
    
    doc = Document()
    
    # Set up document margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.5)
        section.bottom_margin = Inches(0.5)
        section.left_margin = Inches(0.6)
        section.right_margin = Inches(0.6)
    
    # Set default font
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(10.5)
    font.color.rgb = RGBColor(0x33, 0x33, 0x33)
    
    # Parse original resume if provided
    parsed = _parse_resume_into_structure(original_resume_text) if original_resume_text else {}
    
    # ==================== HEADER ====================
    # Name
    name = parsed.get('name', 'Your Name')
    name_para = doc.add_paragraph()
    name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = name_para.add_run(name.upper())
    name_run.bold = True
    name_run.font.size = Pt(18)
    name_run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)
    name_para.paragraph_format.space_after = Pt(2)
    
    # Title/Headline
    title = parsed.get('title', '')
    if title:
        title_para = doc.add_paragraph()
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_run = title_para.add_run(title)
        title_run.font.size = Pt(11)
        title_run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
        title_para.paragraph_format.space_after = Pt(4)
    
    # Contact info (single line, centered)
    contact_items = parsed.get('contact', [])
    location = parsed.get('location', '')
    
    contact_parts = []
    if location:
        contact_parts.append(location)
    for item in contact_items:
        if item['type'] == 'email':
            contact_parts.append(item['value'])
        elif item['type'] == 'phone':
            contact_parts.append(item['value'])
        elif item['type'] in ['linkedin', 'github']:
            contact_parts.append(item.get('url', item['value']))
    
    if contact_parts:
        contact_para = doc.add_paragraph()
        contact_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        contact_text = '  •  '.join(contact_parts[:4])  # Limit to 4 items
        contact_run = contact_para.add_run(contact_text)
        contact_run.font.size = Pt(9)
        contact_run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
        contact_para.paragraph_format.space_after = Pt(8)
    
    _add_horizontal_line(doc)
    
    # ==================== PROFESSIONAL SUMMARY ====================
    _add_section_header(doc, 'Professional Summary')
    
    # Use tailored summary if provided, otherwise original
    summary_text = tailored_summary if tailored_summary else parsed.get('summary', '')
    if summary_text:
        summary_para = doc.add_paragraph(summary_text)
        summary_para.paragraph_format.space_after = Pt(8)
        summary_para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    
    # ==================== KEY ACHIEVEMENTS (Tailored) ====================
    if tailored_bullets:
        _add_section_header(doc, 'Key Achievements')
        for bullet in tailored_bullets:
            bullet_text = bullet.get('text', '') if isinstance(bullet, dict) else str(bullet)
            if bullet_text:
                para = doc.add_paragraph(style='List Bullet')
                para.add_run(bullet_text)
                para.paragraph_format.space_after = Pt(3)
                para.paragraph_format.left_indent = Inches(0.25)
    
    # ==================== SKILLS ====================
    skills = parsed.get('skills', [])
    if skills:
        _add_section_header(doc, 'Technical Skills')
        for skill_group in skills:
            if isinstance(skill_group, dict) and skill_group.get('category'):
                para = doc.add_paragraph()
                cat_run = para.add_run(f"{skill_group['category']}: ")
                cat_run.bold = True
                para.add_run(', '.join(skill_group.get('items', [])))
                para.paragraph_format.space_after = Pt(2)
            elif isinstance(skill_group, dict) and skill_group.get('items'):
                for item in skill_group['items']:
                    para = doc.add_paragraph(style='List Bullet')
                    para.add_run(item)
                    para.paragraph_format.space_after = Pt(2)
                    para.paragraph_format.left_indent = Inches(0.25)
    
    # ==================== EXPERIENCE ====================
    experience = parsed.get('experience', [])
    if experience:
        _add_section_header(doc, 'Professional Experience')
        
        for exp in experience:
            # Job title and company row
            job_para = doc.add_paragraph()
            job_para.paragraph_format.space_before = Pt(8)
            job_para.paragraph_format.space_after = Pt(2)
            
            # Title (bold)
            title_run = job_para.add_run(exp.get('title', 'Position'))
            title_run.bold = True
            title_run.font.size = Pt(11)
            
            # Company
            company = exp.get('company', '')
            if company:
                job_para.add_run(f"  —  {company}")
            
            # Location
            location = exp.get('location', '')
            if location:
                job_para.add_run(f"  |  {location}")
            
            # Dates (right-aligned effect using tab)
            dates = exp.get('dates', '')
            if dates:
                date_para = doc.add_paragraph()
                date_para.paragraph_format.space_after = Pt(4)
                date_run = date_para.add_run(dates)
                date_run.font.size = Pt(10)
                date_run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
                date_run.italic = True
            
            # Bullets
            for bullet in exp.get('bullets', []):
                if bullet:
                    bullet_para = doc.add_paragraph(style='List Bullet')
                    bullet_para.add_run(bullet)
                    bullet_para.paragraph_format.space_after = Pt(2)
                    bullet_para.paragraph_format.left_indent = Inches(0.25)
    
    # ==================== PROJECTS ====================
    projects = parsed.get('projects', [])
    if projects:
        _add_section_header(doc, 'Projects')
        
        for proj in projects:
            proj_para = doc.add_paragraph()
            proj_para.paragraph_format.space_before = Pt(6)
            proj_para.paragraph_format.space_after = Pt(2)
            
            # Project name (bold)
            name_run = proj_para.add_run(proj.get('name', 'Project'))
            name_run.bold = True
            
            # URL
            url = proj.get('url', '')
            if url:
                proj_para.add_run(f"  —  {url}")
            
            # Description/Bullets
            for bullet in proj.get('bullets', []):
                if bullet:
                    bullet_para = doc.add_paragraph(style='List Bullet')
                    bullet_para.add_run(bullet)
                    bullet_para.paragraph_format.space_after = Pt(2)
                    bullet_para.paragraph_format.left_indent = Inches(0.25)
    
    # ==================== EDUCATION ====================
    education = parsed.get('education', [])
    if education:
        _add_section_header(doc, 'Education')
        
        for edu in education:
            edu_para = doc.add_paragraph()
            edu_para.paragraph_format.space_after = Pt(4)
            
            # Degree (bold)
            degree_run = edu_para.add_run(edu.get('degree', ''))
            degree_run.bold = True
            
            # School
            school = edu.get('school', '')
            if school:
                edu_para.add_run(f"  —  {school}")
            
            # Dates
            dates = edu.get('dates', '')
            if dates:
                edu_para.add_run(f"  ({dates})")
    
    # ==================== CERTIFICATIONS ====================
    certifications = parsed.get('certifications', [])
    if certifications:
        _add_section_header(doc, 'Certifications')
        
        for cert in certifications:
            cert_para = doc.add_paragraph(style='List Bullet')
            cert_para.paragraph_format.left_indent = Inches(0.25)
            
            # Cert name (bold)
            name_run = cert_para.add_run(cert.get('name', ''))
            name_run.bold = True
            
            # Issuer and date
            issuer = cert.get('issuer', '')
            date = cert.get('date', '')
            if issuer:
                cert_para.add_run(f"  —  {issuer}")
            if date:
                cert_para.add_run(f"  ({date})")
            
            cert_para.paragraph_format.space_after = Pt(2)
    
    # ==================== ACHIEVEMENTS ====================
    achievements = parsed.get('achievements', [])
    if achievements:
        _add_section_header(doc, 'Notable Achievements')
        
        for achievement in achievements:
            if achievement:
                ach_para = doc.add_paragraph(style='List Bullet')
                ach_para.add_run(achievement)
                ach_para.paragraph_format.space_after = Pt(2)
                ach_para.paragraph_format.left_indent = Inches(0.25)
    
    # Save to BytesIO
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def generate_cover_note_docx(
    cover_note: str,
    job_title: Optional[str] = None,
    company_name: Optional[str] = None,
    applicant_name: Optional[str] = None,
    applicant_email: Optional[str] = None,
    applicant_phone: Optional[str] = None,
    applicant_location: Optional[str] = None,
    applicant_linkedin: Optional[str] = None,
) -> BytesIO:
    """
    Generate a professionally formatted cover letter DOCX.
    
    Includes applicant's contact information in header - ready to use with no edits needed.
    
    Returns:
        BytesIO object containing the DOCX file
    """
    if not DOCX_AVAILABLE:
        raise ImportError("python-docx not installed. Install with: pip install python-docx")
    
    doc = Document()
    
    # Set up margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)
    
    # Set default font
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)
    font.color.rgb = RGBColor(0x33, 0x33, 0x33)
    
    # ==================== APPLICANT HEADER ====================
    # Name
    name = applicant_name or 'Applicant'
    name_para = doc.add_paragraph()
    name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = name_para.add_run(name)
    name_run.bold = True
    name_run.font.size = Pt(14)
    name_para.paragraph_format.space_after = Pt(2)
    
    # Contact info line
    contact_parts = []
    if applicant_location:
        contact_parts.append(applicant_location)
    if applicant_email:
        contact_parts.append(applicant_email)
    if applicant_phone:
        contact_parts.append(applicant_phone)
    if applicant_linkedin:
        contact_parts.append(applicant_linkedin)
    
    if contact_parts:
        contact_para = doc.add_paragraph()
        contact_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        contact_text = '  |  '.join(contact_parts)
        contact_run = contact_para.add_run(contact_text)
        contact_run.font.size = Pt(10)
        contact_run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
        contact_para.paragraph_format.space_after = Pt(18)
    else:
        doc.add_paragraph().paragraph_format.space_after = Pt(12)
    
    # ==================== DATE ====================
    from datetime import datetime
    date_para = doc.add_paragraph(datetime.now().strftime('%B %d, %Y'))
    date_para.paragraph_format.space_after = Pt(18)
    
    # ==================== RECIPIENT (Company) ====================
    if company_name:
        company_para = doc.add_paragraph()
        company_para.add_run(company_name)
        company_para.paragraph_format.space_after = Pt(2)
    
    # Subject line (if provided)
    if job_title:
        subject_para = doc.add_paragraph()
        subject_para.add_run('Re: Application for ')
        subject_run = subject_para.add_run(job_title)
        subject_run.bold = True
        subject_para.paragraph_format.space_after = Pt(18)
    
    # ==================== GREETING ====================
    greeting_para = doc.add_paragraph('Dear Hiring Manager,')
    greeting_para.paragraph_format.space_after = Pt(12)
    
    # ==================== BODY ====================
    # Cover note content - split into paragraphs
    paragraphs = cover_note.split('\n\n')
    for para_text in paragraphs:
        para_text = para_text.strip()
        if para_text:
            # Skip if it's a greeting or closing we'll add ourselves
            if para_text.lower().startswith('dear') or para_text.lower().startswith('sincerely'):
                continue
            # Also skip if it looks like a signature line
            if para_text.startswith('[') and para_text.endswith(']'):
                continue
            para = doc.add_paragraph(para_text)
            para.paragraph_format.space_after = Pt(12)
            para.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
            para.paragraph_format.line_spacing = 1.15
    
    # ==================== CLOSING ====================
    closing_para = doc.add_paragraph()
    closing_para.paragraph_format.space_before = Pt(12)
    closing_para.add_run('Sincerely,')
    
    # Signature with actual name
    sig_para = doc.add_paragraph()
    sig_para.paragraph_format.space_before = Pt(24)
    sig_run = sig_para.add_run(name)
    sig_run.bold = True
    
    # Add email below signature
    if applicant_email:
        email_para = doc.add_paragraph()
        email_para.add_run(applicant_email)
        email_para.paragraph_format.space_before = Pt(2)
    
    # Save to BytesIO
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def generate_apply_pack_zip(
    tailored_summary: str,
    tailored_bullets: list[Dict[str, Any]],
    cover_note: str,
    job_title: Optional[str] = None,
    company_name: Optional[str] = None,
    original_resume_text: Optional[str] = None,
) -> BytesIO:
    """
    Generate a ZIP file containing separate resume and cover letter DOCX files.
    
    This is the preferred format for apply packs - users get two ready-to-use documents.
    
    Returns:
        BytesIO object containing the ZIP file with:
        - resume.docx (tailored resume)
        - cover_letter.docx (personalized cover letter)
    """
    if not DOCX_AVAILABLE:
        raise ImportError("python-docx not installed. Install with: pip install python-docx")
    
    # Parse resume to get applicant info
    parsed = _parse_resume_into_structure(original_resume_text) if original_resume_text else {}
    
    # Extract applicant contact info
    applicant_name = parsed.get('name', '')
    applicant_location = parsed.get('location', '')
    applicant_email = None
    applicant_phone = None
    applicant_linkedin = None
    
    for contact in parsed.get('contact', []):
        if contact.get('type') == 'email' and not applicant_email:
            applicant_email = contact.get('value')
        elif contact.get('type') == 'phone' and not applicant_phone:
            applicant_phone = contact.get('value')
        elif contact.get('type') == 'linkedin' and not applicant_linkedin:
            applicant_linkedin = contact.get('url', contact.get('value'))
    
    # Generate resume DOCX
    resume_buffer = generate_resume_docx(
        tailored_summary=tailored_summary,
        tailored_bullets=tailored_bullets,
        original_resume_text=original_resume_text,
    )
    
    # Generate cover letter DOCX with applicant info
    cover_buffer = generate_cover_note_docx(
        cover_note=cover_note,
        job_title=job_title,
        company_name=company_name,
        applicant_name=applicant_name,
        applicant_email=applicant_email,
        applicant_phone=applicant_phone,
        applicant_location=applicant_location,
        applicant_linkedin=applicant_linkedin,
    )
    
    # Create ZIP file
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add resume
        resume_buffer.seek(0)
        zf.writestr('resume.docx', resume_buffer.read())
        
        # Add cover letter
        cover_buffer.seek(0)
        zf.writestr('cover_letter.docx', cover_buffer.read())
    
    zip_buffer.seek(0)
    return zip_buffer


# Keep the old function for backwards compatibility, but make it use ZIP
def generate_combined_docx(
    tailored_summary: str,
    tailored_bullets: list[Dict[str, Any]],
    cover_note: str,
    job_title: Optional[str] = None,
    company_name: Optional[str] = None,
    original_resume_text: Optional[str] = None,
) -> BytesIO:
    """
    Generate a ZIP file containing separate resume and cover letter DOCX files.
    
    Note: This function now returns a ZIP file instead of a combined DOCX for better usability.
    
    Returns:
        BytesIO object containing the ZIP file
    """
    return generate_apply_pack_zip(
        tailored_summary=tailored_summary,
        tailored_bullets=tailored_bullets,
        cover_note=cover_note,
        job_title=job_title,
        company_name=company_name,
        original_resume_text=original_resume_text,
    )
