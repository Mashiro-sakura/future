"""验收波动率区块：真实数据渲染截图"""
import asyncio
from playwright.async_api import async_playwright

CHROME = r"C:/Program Files/Google/Chrome/Application/chrome.exe"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME, headless=True)
        page = await browser.new_page(viewport={"width": 430, "height": 900})
        await page.goto("http://localhost:8000/", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        visible = await page.is_visible("#volBox")
        zone = await page.text_content("#volZone") if visible else None
        note = await page.text_content("#volNote") if visible else None
        print(f"volBox visible={visible}")
        print(f"volZone={zone!r}")
        print(f"volNote={note!r}")
        if visible:
            box = await page.query_selector("#volBox")
            await box.screenshot(path=".ref/vol_block.png")
        # 切到无期权品种应自动隐藏
        await page.evaluate("() => window.__terminal && window.__terminal.selectProduct('PVC')")
        await page.wait_for_timeout(1500)
        visible2 = await page.is_visible("#volBox")
        print(f"切PVC后 volBox visible={visible2}（应为 False）")
        await browser.close()

asyncio.run(main())
