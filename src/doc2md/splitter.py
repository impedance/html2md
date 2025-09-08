"""HTML splitting utilities."""

from __future__ import annotations

from typing import List, Tuple
import re

from bs4 import BeautifulSoup, NavigableString


def split_html_by_h1(html_content: str) -> List[str]:
    """Split HTML content into fragments by <h1> headings."""
    return [content for _, content in split_html_by_heading_level(html_content, 1)]


def split_html_by_heading_level(html_content: str, level: int) -> List[Tuple[str, str]]:
    """Split HTML content into chapters by specified heading level.
    
    Args:
        html_content: The HTML content to split
        level: Heading level to split on (1 for h1, 2 for h2, etc.)
    
    Returns:
        List of tuples (heading_title, chapter_content)
    """
    soup = BeautifulSoup(html_content, "lxml")
    
    # Find the body content, or use the whole document if no body
    body = soup.find("body")
    if body is None:
        body = soup
    
    chapters: List[Tuple[str, str]] = []
    heading_tag = f"h{level}"
    
    # Find all headings at the specified level
    headings = body.find_all(heading_tag)
    
    if not headings:
        # No headings found, return the entire content as a single chapter
        return [("", str(body))]
    
    for i, heading in enumerate(headings):
        # Extract heading title (clean text without HTML tags)
        title = heading.get_text().strip()
        
        # Collect content from this heading until the next heading of the same level
        parts = [str(heading)]
        
        # Get all siblings after this heading
        current = heading.next_sibling
        while current:
            # If we encounter another heading of the same level, stop
            if (hasattr(current, 'name') and 
                current.name == heading_tag):
                break
            
            # Include this element in the current chapter
            if hasattr(current, 'name') or isinstance(current, NavigableString):
                parts.append(str(current))
            
            current = current.next_sibling
        
        chapter_content = "".join(parts)
        chapters.append((title, chapter_content))
    
    return chapters


def extract_heading_title(heading_element) -> str:
    """Extract clean title from heading element, handling numbered headings."""
    if not heading_element:
        return ""
    
    title = heading_element.get_text().strip()
    
    # Clean up common heading artifacts
    title = re.sub(r'^\d+(\.\d+)*\s*', '', title)  # Remove leading numbers
    title = re.sub(r'\s+', ' ', title)  # Normalize whitespace
    
    return title.strip()
