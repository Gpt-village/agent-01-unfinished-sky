"""Version 8: almanac cycle, festival-derived stories, privacy and accessibility."""
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
if ROOT.name=='source':ROOT=ROOT.parent
HTML=(ROOT/'play-the-unfinished-sky.html').read_text(encoding='utf-8')
STORAGE="""() => {if (!window.__testStorage) window.__testStorage=new Map();Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem(k){return window.__testStorage.get(k)??null},setItem(k,v){window.__testStorage.set(k,String(v))},clear(){window.__testStorage.clear()}}});}"""
def load(page):
    page.evaluate(STORAGE)
    page.set_content(HTML,wait_until='domcontentloaded',timeout=25000)

def complete_festivals(page,first_choice=0):
    for idx in [3,2,5]:
        page.locator('#location-nav button').nth(idx).click()
        page.locator('#dialog-choices button').first.click()
        page.locator('#dialog-continue').click()
    for idx in range(4):
        page.locator('#weather-presets button').nth(idx).click()
        page.locator('#visitor-grid .visitor-card').nth(idx).locator('.visitor-choices button').first.click()
    for idx in range(6):
        page.locator('#community-grid .community-card').nth(idx).locator('button').first.click()
    for idx in range(3):
        page.locator('#commons-grid .commons-card').nth(idx).locator('button').first.click()
    for idx in range(3):
        page.locator('#festival-grid .festival-card').nth(idx).locator('button').nth(first_choice).click()

with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-gpu','--disable-dev-shm-usage'])
    try:
        page=browser.new_page(viewport={'width':1200,'height':900},reduced_motion='reduce');errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        load(page)
        assert page.locator('#almanac-days button').count()==7
        assert page.locator('#almanac-days [aria-pressed="true"]').count()==1
        assert page.locator('#almanac-days .is-active').count()==0
        assert 'still unwritten' in page.locator('#almanac-story').inner_text()
        assert page.locator('#exchange').count()==1, 'existing exchange landmark must remain accessible'
        before=page.evaluate('JSON.stringify(window.__testStorage && [...window.__testStorage])')
        first=page.locator('#almanac-range').inner_text()
        page.locator('#almanac-next').click();assert page.locator('#almanac-range').inner_text()!=first
        page.locator('#almanac-prev').click();assert page.locator('#almanac-range').inner_text()==first
        page.locator('#almanac-days button').nth(3).click()
        assert page.locator('#almanac-days [aria-pressed="true"]').count()==1
        assert page.evaluate('document.activeElement === document.querySelectorAll("#almanac-days button")[3]'), 'keyboard focus should survive rerender'
        page.locator('#almanac-today').click();assert page.locator('#almanac-days button').first.get_attribute('aria-pressed')=='true'
        after=page.evaluate('JSON.stringify(window.__testStorage && [...window.__testStorage])')
        assert before==after, 'calendar browsing must not write local storage'
        print('PASS seven days, accessible buttons, week navigation, no storage writes',flush=True)
        complete_festivals(page,0)
        assert page.locator('#almanac-days .is-active').count()==7
        texts=[]
        for i in range(7):
            page.locator('#almanac-days button').nth(i).click()
            texts.append(page.locator('#almanac-story').inner_text())
        assert len(set(texts))==7, 'seven distinct rites'
        assert any('slowest traveler' in t for t in texts)
        assert any('quietest raindrops' in t for t in texts)
        assert any('open table' in t for t in texts)
        print('PASS seven distinct unlocked rituals reflecting chosen festival endings',flush=True)
        page.locator('#copy-code').click();sky7=page.locator('#sky-code').input_value()
        assert sky7.startswith('SKY7-')
        mobile=browser.new_page(viewport={'width':375,'height':812},is_mobile=True,has_touch=True,reduced_motion='reduce')
        mobile.on('pageerror',lambda e:errors.append(str(e)))
        load(mobile)
        mobile.locator('#sky-code').fill(sky7)
        mobile.locator('#import-code').click();mobile.locator('#import-confirm').click()
        assert mobile.locator('#almanac-days .is-active').count()==7
        assert mobile.locator('#journal .journal-entry').count()==1
        assert mobile.evaluate('document.documentElement.scrollWidth-window.innerWidth')<5
        mobile.locator('#almanac-days button').nth(3).click()
        assert mobile.locator('#almanac-days button').nth(3).get_attribute('aria-pressed')=='true'
        assert not errors,errors
        print('PASS SKY7 import, private journal exclusion, mobile layout, no page errors',flush=True)
        load(page)
        assert page.locator('#almanac-days .is-active').count()==7
        assert page.locator('#almanac-days button').first.get_attribute('aria-pressed')=='true'
        print('PASS reload derives almanac from saved festivals without new fields',flush=True)
        alternate=browser.new_page(viewport={'width':1100,'height':800},reduced_motion='reduce')
        alternate.on('pageerror',lambda e:errors.append(str(e)))
        load(alternate);complete_festivals(alternate,1)
        assert alternate.locator('#almanac-days .is-active').count()==7
        alt_texts=[]
        for i in range(7):
            alternate.locator('#almanac-days button').nth(i).click()
            alt_texts.append(alternate.locator('#almanac-story').inner_text())
        assert all(a!=b for a,b in zip(texts,alt_texts))
        assert any('signposts improvise' in t for t in alt_texts)
        print('PASS alternate festival decisions yield seven different almanac stories',flush=True)
    finally:browser.close()
