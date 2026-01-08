"""
Playwright-based browser fetcher for JS-rendered pages.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Optional

from jobscout.fetchers.http import FetchResult


@dataclass
class BrowserConfig:
    """Browser configuration."""
    headless: bool = True
    timeout_ms: int = 30000
    wait_for_selector: Optional[str] = None
    wait_for_network_idle: bool = True
    block_resources: bool = True  # Block images/fonts/media for speed


class BrowserFetcher:
    """
    Playwright-based fetcher for JavaScript-rendered pages.
    
    Falls back gracefully if Playwright is not installed.
    """

    def __init__(self, config: Optional[BrowserConfig] = None):
        self.config = config or BrowserConfig()
        self._browser = None
        self._context = None
        self._playwright = None
        self._available: Optional[bool] = None

    async def __aenter__(self) -> "BrowserFetcher":
        await self.start()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    @property
    def is_available(self) -> bool:
        """Check if Playwright is available."""
        if self._available is None:
            try:
                from playwright.async_api import async_playwright  # noqa
                self._available = True
            except ImportError:
                self._available = False
        return self._available

    async def start(self) -> bool:
        """
        Initialize the browser.
        Returns True if successful, False if Playwright not available.
        """
        if not self.is_available:
            return False

        if self._browser is not None:
            return True

        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.config.headless,
            )
            self._context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                java_script_enabled=True,
            )

            # Block unnecessary resources for speed
            if self.config.block_resources:
                await self._context.route(
                    "**/*.{png,jpg,jpeg,gif,webp,svg,ico,woff,woff2,ttf,eot}",
                    lambda route: route.abort(),
                )
                await self._context.route(
                    "**/*{analytics,tracking,ads,facebook,google-analytics}*",
                    lambda route: route.abort(),
                )

            return True

        except Exception as e:
            print(f"[BrowserFetcher] Failed to start browser: {e}")
            self._available = False
            return False

    async def close(self) -> None:
        """Close the browser."""
        try:
            if self._context:
                await self._context.close()
                self._context = None
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
        except Exception:
            pass

    async def fetch(
        self,
        url: str,
        wait_for_selector: Optional[str] = None,
    ) -> FetchResult:
        """
        Fetch a page using the browser, waiting for JS to render.
        """
        if not self.is_available:
            return FetchResult(
                url=url,
                error="Playwright not installed. Install with: pip install playwright && playwright install chromium",
            )

        if self._browser is None:
            started = await self.start()
            if not started:
                return FetchResult(
                    url=url,
                    error="Failed to start browser",
                )

        start_time = time.time()
        page = None

        try:
            page = await self._context.new_page()

            # Navigate with timeout
            response = await page.goto(
                url,
                timeout=self.config.timeout_ms,
                wait_until="domcontentloaded",
            )

            status = response.status if response else 0

            # Wait for network to settle if configured
            if self.config.wait_for_network_idle:
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass  # Timeout is OK, page might have long-polling

            # Wait for specific selector if provided
            selector = wait_for_selector or self.config.wait_for_selector
            if selector:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                except Exception:
                    pass  # Selector not found is OK

            # Small delay for any final JS execution
            await asyncio.sleep(0.5)

            # Get rendered HTML
            content = await page.content()

            return FetchResult(
                url=url,
                status=status,
                text=content,
                content_type="text/html",
                elapsed_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            return FetchResult(
                url=url,
                error=f"Browser fetch failed: {str(e)}",
                elapsed_ms=(time.time() - start_time) * 1000,
            )

        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    async def fetch_with_scroll(
        self,
        url: str,
        scroll_count: int = 3,
        scroll_delay_ms: int = 500,
    ) -> FetchResult:
        """
        Fetch a page and scroll to trigger lazy-loaded content.
        Useful for infinite-scroll job listings.
        """
        if not self.is_available or self._browser is None:
            return await self.fetch(url)

        start_time = time.time()
        page = None

        try:
            page = await self._context.new_page()

            response = await page.goto(
                url,
                timeout=self.config.timeout_ms,
                wait_until="domcontentloaded",
            )

            status = response.status if response else 0

            # Wait for initial load
            await page.wait_for_load_state("networkidle", timeout=10000)

            # Scroll to load more content
            for _ in range(scroll_count):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(scroll_delay_ms / 1000)

            # Scroll back to top
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(0.3)

            content = await page.content()

            return FetchResult(
                url=url,
                status=status,
                text=content,
                content_type="text/html",
                elapsed_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            return FetchResult(
                url=url,
                error=f"Browser fetch with scroll failed: {str(e)}",
                elapsed_ms=(time.time() - start_time) * 1000,
            )

        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

