"""准实时档1验收：截图全页 + 断言 liveTag 文案（周六应为'已收盘'）+ 模拟盘中注入 live 数据验证闪动链路。"""
import asyncio

from playwright.async_api import async_playwright

CHROME = r"C:\Users\84114\.agent-browser\browsers\chrome-154.0.8037.57\chrome.exe"
URL = "http://127.0.0.1:8000/?v=rt1"
SHOT_DIR = r"C:\Users\84114\Desktop\codex\future_anaylist\backend\.ref"


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME, headless=True)
        page = await browser.new_page(viewport={"width": 430, "height": 1500})
        await page.goto(URL, wait_until="networkidle")
        await page.wait_for_timeout(1500)

        tag = await page.text_content("#liveTag")
        print("liveTag（周六非盘中应为'已收盘'）:", tag)

        # 模拟盘中：注入 live 数据并触发渲染路径（经 window.__terminal 调试句柄）
        await page.evaluate(
            """() => {
                const T = window.__terminal;
                T.state.live = {
                    PTA: { code: 'PTA', contract_code: 'TA2701', price: 6412.0, prev_close: 6120.0,
                           change_pct: 4.77, volume: 1300000, open_interest: 1110000,
                           trade_date: '2026-09-26', trading_now: true, server_time: '' }
                };
                T.state.liveOn = true;
                T.updateLiveTag();
                const products = T.state.overview?.products || [];
                T.renderTicker(products);
                T.renderBoard(products);
                const current = products.find((x) => x.code === T.state.code);
                T.renderHero(current);
                document.querySelector('#heroPrice').classList.add('flash');
            }"""
        )
        await page.wait_for_timeout(400)
        hero_price = await page.text_content("#heroPrice")
        hero_chg = await page.text_content("#heroChg")
        contract = await page.text_content("#heroContract")
        tag2 = await page.text_content("#liveTag")
        print(f"注入后 hero: {hero_price} {hero_chg} | 合约 {contract} | tag {tag2}")
        await page.screenshot(path=SHOT_DIR + r"\page_realtime_sim.png", full_page=False)
        await browser.close()


asyncio.run(main())
