const {chromium} = require('../.venv/browser/node_modules/playwright');
const fs = require('fs');
(async () => {
  const edge = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
  const browser = await chromium.launch(fs.existsSync(edge) ? {executablePath:edge} : {});
  const context = await browser.newContext({viewport:{width:1440,height:1000},colorScheme:'light'});
  const page = await context.newPage();
  const base = process.env.BASE_URL || 'http://127.0.0.1:8000';
  const errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  const assert=(value,message)=>{if(!value)throw new Error(message)};
  const theme=()=>page.locator('html').getAttribute('data-theme');
  async function screenshot(name){
    await page.emulateMedia({reducedMotion:'reduce'});
    await page.screenshot({path:`artifacts/${name}.png`,fullPage:true});
  }
  fs.mkdirSync('artifacts',{recursive:true});
  await page.goto(base+'/materials/');
  assert(await theme()==='light','System light theme');
  await screenshot('catalog-light-v2');
  await page.getByRole('button',{name:'Включить тёмную тему'}).click();
  assert(await theme()==='dark','Toggle dark theme');
  await screenshot('catalog-dark-v2');
  await page.reload();
  assert(await theme()==='dark','Persist after reload');
  await page.getByRole('link',{name:'Чтение',exact:true}).click();
  assert(await theme()==='dark','Persist across navigation');
  assert(await page.locator('.material-card').count()===3,'Direction shortcut filters');
  await page.goto(base+'/materials/?age=5-7&page=2');
  await page.getByRole('link',{name:'Математика',exact:true}).click();
  assert(page.url().includes('age=5-7')&&!page.url().includes('page='),'Direction preserves other filters and resets page');
  for(const width of [360,768,1440]){
    await page.setViewportSize({width,height:900});
    for(const path of ['/materials/','/materials/reading-1/','/about/','/accounts/login/','/accounts/signup/']){
      await page.goto(base+path);
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`No overflow: ${width} ${path}`);
      const bg=await page.locator('body').evaluate(el=>getComputedStyle(el).backgroundColor);
      assert(bg==='rgb(16, 22, 19)',`Dark background: ${path}`);
    }
  }
  await page.setViewportSize({width:360,height:800});
  await page.goto(base+'/materials/');
  await screenshot('catalog-dark-mobile-v2');
  await page.getByRole('button',{name:'Включить светлую тему'}).focus();
  await page.keyboard.press('Enter');
  assert(await theme()==='light','Keyboard toggle');
  await screenshot('catalog-light-mobile-v2');
  await page.emulateMedia({reducedMotion:'reduce'});
  assert(await page.locator('.art-note').first().evaluate(el=>getComputedStyle(el).animationName)==='none','Reduced motion stops decorative animation');
  await page.evaluate(()=>localStorage.removeItem('shag-theme'));
  await page.emulateMedia({colorScheme:'dark'});
  await page.reload();
  assert(await theme()==='dark','System dark preference');
  await page.emulateMedia({colorScheme:'light'});
  await page.waitForFunction(()=>document.documentElement.dataset.theme==='light');
  assert(await theme()==='light','Respond to system theme changes');
  const noStorage=await browser.newContext({colorScheme:'light'});
  await noStorage.addInitScript(()=>{
    Object.defineProperty(Storage.prototype,'getItem',{value(){throw new Error('blocked')}});
    Object.defineProperty(Storage.prototype,'setItem',{value(){throw new Error('blocked')}});
  });
  const blockedPage=await noStorage.newPage();
  await blockedPage.goto(base+'/materials/');
  await blockedPage.getByRole('button',{name:'Включить тёмную тему'}).click();
  assert(await blockedPage.locator('html').getAttribute('data-theme')==='dark','Toggle works when storage blocked');
  const noJs=await browser.newContext({javaScriptEnabled:false});
  const fallback=await noJs.newPage();
  await fallback.goto(base+'/materials/');
  assert(await fallback.locator('.material-card').count()===12,'Content works without JS');
  assert(!await fallback.locator('.theme-toggle').isVisible(),'No dead theme button without JS');
  assert(errors.length===0,'No JS errors');
  fs.writeFileSync('artifacts/theme-results.json',JSON.stringify({passed:true,widths:[360,768,1440],checks:['theme persistence','system preference','keyboard toggle','blocked storage','no-JS fallback','direction shortcuts','reduced motion','overflow'],jsErrors:errors.length},null,2));
  console.log('Theme and layout checks passed.');
  await browser.close();
})().catch(error=>{console.error(error);process.exit(1)});
