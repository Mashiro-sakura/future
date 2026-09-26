"""量出页面横向溢出的元凶：viewport vs scrollWidth，逐个找超界元素。"""
import asyncio
import json

from playwright.async_api import async_playwright

CHROME = r"C:\Users\84114\.agent-browser\browsers\chrome-154.0.8037.57\chrome.exe"
URL = "http://127.0.0.1:8000/?v=debug1"


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME, headless=True)
        page = await browser.new_page(viewport={"width": 430, "height": 1500})
        await page.goto(URL, wait_until="networkidle")
        await page.wait_for_timeout(1200)
        info = await page.evaluate(
            """() => {
                const doc = document.documentElement;
                const vw = window.innerWidth;
                const sw = doc.scrollWidth;
                const wide = [];
                document.querySelectorAll('*').forEach((el) => {
                    const r = el.getBoundingClientRect();
                    if (r.right > vw + 0.5 || r.left < -0.5) {
                        wide.push({
                            tag: el.tagName,
                            cls: (el.className && el.className.baseVal !== undefined ? el.className.baseVal : el.className || '').toString().slice(0, 60),
                            id: el.id || '',
                            left: Math.round(r.left),
                            right: Math.round(r.right),
                            width: Math.round(r.width),
                        });
                    }
                });
                return { vw, sw, wide: wide.slice(0, 25) };
            }"""
        )
        print(json.dumps(info, ensure_ascii=False, indent=1))
        await page.screenshot(path=r"C:\Users\84114\Desktop\codex\future_anaylist\backend\.ref\page_v5_top.png", full_page=True)
        await browser.close()


asyncio.run(main())
