"""
HTML content extraction utilities.
"""

from __future__ import annotations

import re
from typing import List

from bs4 import BeautifulSoup, NavigableString


def strip_html(html: str, max_len: int = 8000) -> str:
    """
    Convert HTML to plain text, stripping tags but preserving some structure.
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "lxml")

    # Remove script, style, and other non-content tags
    for tag in soup(["script", "style", "noscript", "iframe", "svg", "canvas"]):
        tag.decompose()

    # Get text with some structure preservation
    text = soup.get_text(" ", strip=True)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text[:max_len]


def extract_text_structured(html: str, max_len: int = 8000) -> str:
    """
    Extract text from HTML while preserving some structure (headings, lists).
    Useful for job descriptions where structure helps with keyword matching.
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "lxml")

    # Remove non-content elements
    for tag in soup(["script", "style", "noscript", "iframe", "svg", "canvas", "nav", "footer", "header"]):
        tag.decompose()

    lines: List[str] = []

    def process_element(element, depth=0):
        if isinstance(element, NavigableString):
            text = str(element).strip()
            if text:
                lines.append(text)
            return

        tag_name = getattr(element, "name", None)
        if tag_name is None:
            return

        # Handle headings
        if tag_name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = element.get_text(strip=True)
            if text:
                lines.append(f"\n## {text}\n")
            return

        # Handle list items
        if tag_name == "li":
            text = element.get_text(strip=True)
            if text:
                lines.append(f"• {text}")
            return

        # Handle paragraphs and divs
        if tag_name in ("p", "div", "section", "article"):
            text = element.get_text(" ", strip=True)
            if text:
                lines.append(text)
                lines.append("")  # Add blank line after
            return

        # Handle line breaks
        if tag_name == "br":
            lines.append("")
            return

        # Recurse for other elements
        for child in element.children:
            process_element(child, depth + 1)

    # Find main content area if possible
    main_content = soup.find("main") or soup.find("article") or soup.find(class_=re.compile(r"content|body|description", re.I))
    if main_content:
        process_element(main_content)
    else:
        process_element(soup.body or soup)

    # Join and clean up
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)  # Max 2 consecutive newlines
    text = re.sub(r" +", " ", text)  # Normalize spaces
    text = text.strip()

    return text[:max_len]


def extract_page_title(html: str) -> str:
    """Extract the page title from HTML."""
    if not html:
        return ""

    soup = BeautifulSoup(html, "lxml")

    # Try og:title first (often more descriptive)
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"].strip()

    # Try regular title
    if soup.title and soup.title.string:
        return soup.title.string.strip()

    # Try h1
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)

    return ""


def extract_meta_description(html: str) -> str:
    """Extract meta description from HTML."""
    if not html:
        return ""

    soup = BeautifulSoup(html, "lxml")

    # Try og:description first
    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content"):
        return og_desc["content"].strip()

    # Try regular meta description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        return meta_desc["content"].strip()

    return ""

