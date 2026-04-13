"""
URL Scraper Service
Scrapes web pages and extracts clean text for RAG ingestion.
Uses trafilatura for high-quality text extraction.
Falls back to Playwright (headless browser) for JS-rendered pages.
"""

import logging
import tempfile
import os
from typing import Dict, Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

try:
    import trafilatura
    from trafilatura.settings import use_config
    TRAFILATURA_AVAILABLE = True
except ImportError:
    logger.warning("trafilatura not installed — URL scraping unavailable")
    TRAFILATURA_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    logger.warning("playwright not installed — JS-rendered page fallback unavailable")
    PLAYWRIGHT_AVAILABLE = False


def _fetch_with_playwright(url: str, wait_ms: int = 3000) -> str:
    """
    Render a page with headless Chromium and return the full HTML.
    Used as fallback when trafilatura can't extract from static HTML.
    
    Args:
        url: URL to render
        wait_ms: Milliseconds to wait for JS to finish rendering
    
    Returns:
        Rendered HTML string
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("playwright not installed. Run: pip install playwright && python -m playwright install chromium")
    
    logger.info(f"Falling back to Playwright for JS-rendered page: {url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(wait_ms)  # extra wait for lazy-loaded content
        html = page.content()
        browser.close()
    
    return html


def scrape_url(url: str, include_links: bool = False) -> Dict[str, Any]:
    """
    Scrape a single URL and extract clean text content.
    Automatically falls back to headless browser if static fetch fails.
    
    Args:
        url: The URL to scrape
        include_links: Whether to include hyperlinks in output
    
    Returns:
        Dictionary with:
            - text: Extracted text content
            - title: Page title
            - url: Original URL
            - domain: Domain name
            - word_count: Number of words extracted
            - method: "static" or "playwright" (which method succeeded)
    """
    if not TRAFILATURA_AVAILABLE:
        raise RuntimeError("trafilatura not installed. Run: pip install trafilatura")
    
    logger.info(f"Scraping URL: {url}")
    
    # Parse URL for metadata
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)
    
    domain = parsed.netloc
    
    # Configure trafilatura
    config = use_config()
    config.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")
    
    # ── Attempt 1: Static fetch (fast, works for most sites) ──
    downloaded = trafilatura.fetch_url(url, config=config)
    text = None
    method = "static"
    
    if downloaded:
        text = trafilatura.extract(
            downloaded,
            include_links=include_links,
            include_tables=True,
            include_images=False,
            include_formatting=False,
            favor_precision=False,
            config=config,
        )
    
    # ── Attempt 2: Playwright fallback (for JS-rendered pages) ──
    if (not text or len(text.strip()) < 50) and PLAYWRIGHT_AVAILABLE:
        logger.info(f"Static fetch returned insufficient text. Trying Playwright...")
        try:
            rendered_html = _fetch_with_playwright(url)
            text = trafilatura.extract(
                rendered_html,
                include_links=include_links,
                include_tables=True,
                include_images=False,
                include_formatting=False,
                favor_precision=False,
                config=config,
            )
            if text and len(text.strip()) >= 50:
                method = "playwright"
                logger.info(f"Playwright fallback succeeded!")
        except Exception as e:
            logger.warning(f"Playwright fallback failed: {e}")
    
    if not text or len(text.strip()) < 50:
        raise ValueError(
            f"No meaningful content extracted from: {url}. "
            f"The page may require authentication or has very little text content."
        )
    
    # Extract title/metadata
    title = domain  # default
    source_html = downloaded if method == "static" else (rendered_html if method == "playwright" else None)
    if source_html:
        metadata = trafilatura.extract(
            source_html,
            output_format="json",
            config=config,
        )
        if metadata:
            import json
            try:
                meta_dict = json.loads(metadata)
                title = meta_dict.get("title", domain)
            except (json.JSONDecodeError, TypeError):
                pass
    
    word_count = len(text.split())
    
    logger.info(f"Extracted {word_count} words from {url} (method: {method})")
    
    return {
        "text": text,
        "title": title,
        "url": url,
        "domain": domain,
        "word_count": word_count,
        "method": method,
    }


def scrape_url_to_file(url: str) -> Dict[str, Any]:
    """
    Scrape a URL and save the extracted text to a temp file.
    The temp file can be fed directly into the RAG pipeline.
    Automatically uses Playwright fallback for JS-heavy pages.
    
    Args:
        url: The URL to scrape
    
    Returns:
        Dictionary with:
            - file_path: Path to the temp text file
            - title: Page title
            - url: Original URL
            - domain: Domain name
            - word_count: Number of words extracted
            - method: "static" or "playwright"
    """
    result = scrape_url(url)
    
    # Add source header for context
    header = f"Source: {result['url']}\nTitle: {result['title']}\n\n"
    full_text = header + result["text"]
    
    # Save to temp file
    temp_dir = tempfile.gettempdir()
    safe_domain = "".join(c if c.isalnum() or c in ".-_" else "_" for c in result["domain"])
    temp_path = os.path.join(temp_dir, f"scraped_{safe_domain}.txt")
    
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(full_text)
    
    result["file_path"] = temp_path
    logger.info(f"Saved scraped content to: {temp_path}")
    
    return result
