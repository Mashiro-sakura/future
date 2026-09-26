"""验收 quote-note 延迟明示：收盘态文案 + 注入盘中态文案"""
import asyncio
from playwright.async_api import async_playwright

# agent-browser 独立 chrome 已不在 binaries 下（2026-09-26 环境变化），回落系统 Chrome
CHROME = r"C:/Program Files/Google/Chrome/Application/chrome.exe"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME, headless=True)
        page = await browser.new_page(viewport={"width": 430, "height": 900})
        await page.goto("http://localhost:8000/", wait_until="networkidle")
        await page.wait_for_timeout(2500)
        note1 = await page.text_content("#quoteNote")
        tag1 = await page.text_content("#liveTag")
        print(f"[收盘态] liveTag={tag1!r} quoteNote={note1!r}")
        await page.screenshot(path=".ref/quote_note_closed.png", clip={"x":0,"y":0,"width":430,"height":420})
        # 注入盘中态
        await page.evaluate("""() => {
          const t = window.__terminal
          if (t) { t.state.liveOn = true; t.updateLiveTag() }
        }""")
        await page.wait_for_timeout(300)
        note2 = await page.text_content("#quoteNote")
        tag2 = await page.text_content("#liveTag")
        print(f"[盘中态] liveTag={tag2!r} quoteNote={note2!r}")
        await page.screenshot(path=".ref/quote_note_live.png", clip={"x":0,"y":0,"width":430,"height":420})
        await browser.close()

asyncio.run(main())
