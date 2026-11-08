// npm install --prefix .venv/browser playwright
// node scripts/browser-check.cjs (uses existing Edge, or Playwright Chromium)
const {chromium} = require('../.venv/browser/node_modules/playwright');
const fs = require('fs');
(async () => {
  const edge = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
  const browser = await chromium.launch(fs.existsSync(edge) ? {executablePath: edge, headless:true} : {headless:true});
  const page = await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  const base=process.env.BASE_URL || 'http://127.0.0.1:8000';
  const assert=(value,message)=>{if(!value)throw new Error(message)};
  fs.mkdirSync('artifacts',{recursive:true});
  await page.goto(base+'/materials/');
  assert(await page.locator('.material-card').count()===12,'12 cards on first page');
  await page.screenshot({path:'artifacts/catalog-desktop.png',fullPage:true});
  await page.locator('#id_q').fill('СЛОГИ');
  await page.getByRole('button',{name:'Найти'}).click();
  await page.waitForURL(/q=/);
  assert(await page.locator('.material-card').count()===3,'Cyrillic search');
  await page.goto(base+'/materials/?direction=reading&age=5-7&duration=5');
  assert(await page.locator('.material-card').count()===1,'Combined filters');
  await page.locator('.card-body h3 a').click();
  await page.waitForURL(/reading-1/);
  await page.getByRole('link',{name:'Вернуться к материалам'}).click();
  assert(page.url().includes('direction=reading'),'Return retains filters');
  await page.setViewportSize({width:360,height:800});
  await page.goto(base+'/materials/');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No mobile horizontal overflow');
  await page.getByRole('button',{name:'Фильтры'}).click();
  assert(await page.locator('#filter-fields').isVisible(),'Mobile filters expand');
  await page.selectOption('#id_direction','reading');
  await page.getByRole('button',{name:'Применить',exact:true}).click();
  await page.waitForURL(/direction=reading/);
  assert(await page.locator('.material-card').count()===3,'Mobile filter submission');
  await page.screenshot({path:'artifacts/catalog-mobile.png',fullPage:true});
  await page.goto(base+'/materials/reading-1/');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No detail mobile overflow');
  await page.screenshot({path:'artifacts/material-mobile.png',fullPage:true});
  // Exercise signup, authenticated save and logout with actual CSRF cookies and JS.
  const email=`browser-${Date.now()}@example.test`;
  await page.goto(base+'/accounts/signup/?next=/materials/reading-1/');
  await page.locator('#id_first_name').fill('Проверка интерфейса');
  await page.locator('#id_email').fill(email);
  await page.locator('#id_password1').fill('Browser-test-Password-923!');
  await page.locator('#id_password2').fill('Browser-test-Password-923!');
  await page.getByRole('button',{name:'Создать аккаунт'}).click();
  await page.waitForURL(base+'/materials/reading-1/');
  await page.getByRole('button',{name:'В избранное',exact:false}).click();
  await page.waitForLoadState('networkidle');
  await page.getByRole('link',{name:'Избранное',exact:true}).click();
  assert(await page.locator('.material-card').count()===1,'Saved favorite visible');
  await page.locator('.save-button').click();
  await page.waitForLoadState('networkidle');
  assert(await page.locator('.material-card').count()===0,'Favorite removed');
  await page.getByRole('button',{name:'Выйти'}).click();
  await page.waitForURL(base+'/materials/');
  // Check horizontal fit on secondary pages and keyboard focus.
  for(const path of ['/accounts/login/','/accounts/signup/','/about/']){
    await page.goto(base+path);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`No overflow: ${path}`);
  }
  await page.goto(base+'/materials/');
  await page.keyboard.press('Tab');
  assert(await page.evaluate(()=>document.activeElement.textContent.includes('К содержимому')),'Skip link gets keyboard focus');
  assert(errors.length===0,'No browser JS errors: '+errors.join(';'));
  fs.writeFileSync('artifacts/browser-results.json',JSON.stringify({passed:true,widths:[1440,360],checks:['pagination','Cyrillic search','combined filters','URL restoration','mobile filters','overflow','registration','CSRF forms','favorites','logout','keyboard skip link'],account:email},null,2));
  console.log(JSON.stringify({passed:true,testAccount:email,jsErrors:errors.length}));
  await browser.close();
})().catch(error=>{console.error(error);process.exit(1)});
