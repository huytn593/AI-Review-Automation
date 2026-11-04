/* Real FastAPI build capture. Run from frontend; no fixture server or mocked assets. */
const {chromium}=require('playwright');const{spawn,execFileSync}=require('node:child_process');const fs=require('node:fs');const path=require('node:path');
(async()=>{
 const out=path.resolve('../evidence/living');fs.mkdirSync(out,{recursive:true});
 const python=process.env.STUDIO_PYTHON||path.resolve('../.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
 const server=spawn(python,['-m','uvicorn','factory.app:app','--port','8013'],{cwd:'..',env:{...process.env,FACTORY_DATA:fs.mkdtempSync(path.join(require('node:os').tmpdir(),'motion-'))},stdio:'ignore'});
 let browser;try{
  let ready=false;for(let i=0;i<40;i++){try{ready=(await fetch('http://127.0.0.1:8013/health')).ok}catch{}if(ready)break;await new Promise(r=>setTimeout(r,250))}if(!ready)throw Error('FastAPI did not start')
  browser=await chromium.launch({executablePath:process.env.STUDIO_CHROMIUM,channel:!process.env.STUDIO_CHROMIUM&&process.platform==='win32'?'chrome':undefined,headless:true});
  const context=await browser.newContext({viewport:{width:1920,height:1080},reducedMotion:'no-preference'});
  await context.tracing.start({screenshots:true,snapshots:true});const page=await context.newPage(),events=[];
  page.on('console',m=>events.push({type:m.type(),text:m.text()}));page.on('pageerror',e=>events.push({error:String(e)}));page.on('response',r=>{if(r.url().includes('.glb')||r.status()>=400)events.push({url:r.url(),status:r.status()})});
  const waitAssets=()=>page.waitForFunction(()=>JSON.parse(document.querySelector('canvas')?.dataset.motion||'{}').loadedAssets===4);
  await page.goto('http://127.0.0.1:8013/?motionDebug=1');await waitAssets();
  const samples=[];for(let i=0;i<10;i++){await page.waitForTimeout(1000);samples.push(JSON.parse(await page.locator('canvas').getAttribute('data-motion')))}
  await page.screenshot({path:path.join(out,'after-debug.png')});
  const gpu=await page.locator('canvas').evaluate(c=>{const gl=c.getContext('webgl2'),ext=gl?.getExtension('WEBGL_debug_renderer_info');return ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):'not exposed'});
  fs.writeFileSync(path.join(out,'diagnostics.json'),JSON.stringify({events,gpu,samples},null,2));
  await page.goto('http://127.0.0.1:8013/');await page.waitForTimeout(3000);await page.screenshot({path:path.join(out,'after.png')});await page.locator('.planet-stage').screenshot({path:path.join(out,'planet.png')});
  await page.setViewportSize({width:1366,height:768});await page.waitForTimeout(1000);await page.screenshot({path:path.join(out,'after-1366.png')});
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(500);await page.screenshot({path:path.join(out,'after-mobile.png')});
  await page.setViewportSize({width:1920,height:1080});await page.goto('http://127.0.0.1:8013/?motionDebug=1&isolate=foliage&specimen=flower');await waitAssets();await page.addStyleTag({content:'.motion-debug{visibility:hidden}'});
  for(const [name,delay] of [['t0',0],['t2',2000],['t5',3000]]){await page.waitForTimeout(delay);await page.locator('canvas').screenshot({path:path.join(out,`foliage-${name}.png`)})}
  await context.tracing.stop({path:path.join(out,'capture-trace.zip')});await context.close();
  const videoContext=await browser.newContext({viewport:{width:1920,height:1080},reducedMotion:'no-preference',recordVideo:{dir:out,size:{width:1920,height:1080}}});
  const videoPage=await videoContext.newPage();await videoPage.goto('http://127.0.0.1:8013/');const start=Date.now();for(const second of [0,3,6,10,15]){await videoPage.waitForTimeout(Math.max(0,second*1000-(Date.now()-start)));await videoPage.screenshot({path:path.join(out,`motion-${second}s.png`)})}
  const video=videoPage.video();await videoContext.close();await video.saveAs(path.join(out,'production-motion.webm'));await video.delete();
  // Portable, compact review artifacts alongside the lossless/raw captures.
  for(const name of fs.readdirSync(out).filter(name=>name.endsWith('.png')&&!name.startsWith('foliage-'))){
   execFileSync('ffmpeg',['-nostdin','-y','-v','error','-i',path.join(out,name),'-q:v','3',path.join(out,name.replace(/\.png$/,'.jpg'))]);
  }
  execFileSync('ffmpeg',['-nostdin','-y','-v','error','-i',path.join(out,'production-motion.webm'),'-vf','scale=1280:-2','-c:v','libx264','-crf','28','-preset','fast','-movflags','+faststart','-an',path.join(out,'production-motion.mp4')]);
  for(const second of [0,3,6,10,15])execFileSync('ffmpeg',['-nostdin','-y','-v','error','-ss',String(second),'-i',path.join(out,'production-motion.mp4'),'-frames:v','1','-q:v','3',path.join(out,`motion-${second}s.jpg`)]);
  console.log(JSON.stringify({gpu,samples:samples.map(s=>s.fps),errors:events.filter(e=>e.type==='error'||e.error||e.status>=400)}));
 }finally{await browser?.close();server.kill()}
})().catch(e=>{console.error(e);process.exitCode=1})
