import asyncio
from typing import List, Dict, Optional
from playwright.async_api import async_playwright
from langchain_core.tools import tool
from ddgs import DDGS
import html2text
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse

class BrowserTools:
    """Tools for browser automation and searching."""

    @staticmethod
    def check_robots(url: str, user_agent: str = "*") -> bool:
        """Check if robots.txt allows scraping this URL."""
        try:
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            robots_url = f"{base_url}/robots.txt"
            
            rp = RobotFileParser()
            rp.set_url(robots_url)
            # Set a short timeout for robots.txt to avoid hanging
            rp.read()
            can_fetch = rp.can_fetch(user_agent, url)
            if not can_fetch:
                print(f"🚫 robots.txt disallowed access to: {url}")
            return can_fetch
        except Exception as e:
            # If robots.txt is unreachable (404, etc), usually implies allowed.
            print(f"⚠️ Could not check robots.txt for {url}: {e} (Assuming Allowed)")
            return True
    
    @staticmethod
    @tool("search_web")
    def search_web(query: str) -> List[Dict[str, str]]:
        """
        Search the web for funding opportunities using DuckDuckGo.
        Returns a list of results with 'title', 'href', and 'body'.
        """
        print(f"🔍 Searching web for: {query}")
        try:
            results = DDGS().text(query, max_results=5)
            # Standardize keys to match what our agent expects
            clean_results = []
            for r in results:
                clean_results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")
                })
            return clean_results
        except Exception as e:
            print(f"❌ Search failed: {e}")
            return []

    @staticmethod
    @tool("visit_page")
    async def visit_page(url: str) -> str:
        """
        Visit a webpage using a headless browser and extract its text content.
        Useful for reading details about a specific funding program.
        """
        print(f"🌍 Visiting page: {url}")
        
        # 1. Check robots.txt first
        if not BrowserTools.check_robots(url):
            return "❌ Access Denied by robots.txt. The site owner does not allow bots to scrape this page. Please try a different source."

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            # Create a context with a realistic user agent to avoid blocking
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            try:
                # Go to URL with a timeout
                await page.goto(url, timeout=20000, wait_until="domcontentloaded")
                
                # Get the HTML content
                html_content = await page.content()
                
                # Convert HTML to clean text
                h = html2text.HTML2Text()
                h.ignore_links = True
                h.ignore_images = True
                text_content = h.handle(html_content)
                
                # Limit content length to avoid confusing the LLM with too much footer/nav noise
                return text_content[:15000]  # First 15k chars is usually enough
                
            except Exception as e:
                return f"❌ Error visiting page: {e}"
            finally:
                await browser.close()
