# Loads one page twice with XSLT on and twice with it off, waiting 10s, and saves the four
# viewport screenshots side by side (on, on, off, off) to tell page timing from real changes.
# Usage: recheck.py <chrome-executable> <url> <viewport-width: 360 for mobile, 1366 for desktop> <out.png>
import asyncio, sys
from playwright.async_api import async_playwright
from PIL import Image

chrome, url, width, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
mobile = width == 360
FLAGS = {
    'on': ['--enable-features=XSLT', '--disable-features=GenerateXSLTWarningBanner'],
    'off': ['--disable-features=XSLT'],
}


async def main():
    shots = []
    async with async_playwright() as p:
        for name in ('on', 'off'):
            browser = await p.chromium.launch(executable_path=chrome, args=FLAGS[name])
            for run in range(2):
                ctx = await browser.new_context(viewport={'width': width, 'height': 640 if mobile else 768},
                                                is_mobile=mobile, has_touch=mobile)
                page = await ctx.new_page()
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)[:100]))
                await page.goto(url, wait_until='load', timeout=45000)
                await page.wait_for_timeout(10000)
                path = f'{out}.{name}{run}.png'
                await page.screenshot(path=path)
                shots.append(path)
                print(name, run, errors)
                await ctx.close()
            await browser.close()
    ims = [Image.open(s) for s in shots]
    grid = Image.new('RGB', (len(ims) * (ims[0].width + 10), ims[0].height), 'red')
    for k, im in enumerate(ims):
        grid.paste(im, (k * (im.width + 10), 0))
    grid.thumbnail((1600, 900))
    grid.save(out)

asyncio.run(main())
