import {test,expect} from '@playwright/test'
import {PNG} from 'pngjs'
import {writeFileSync} from 'node:fs'

test.use({reducedMotion:'no-preference',video:'on'})
// These are real Poly Haven meshes and the production wind shader, with only
// other scene layers hidden to exclude planet/fog/background false positives.
function band(image:PNG,top:number,bottom:number){
 let mass=0,xsum=0
 for(let y=top;y<bottom;y++)for(let x=0;x<image.width;x++){
  const i=(y*image.width+x)*4
  if(Math.max(image.data[i],image.data[i+1],image.data[i+2])>24){mass++;xsum+=x}
 }
 return {mass,x:mass?xsum/mass:0}
}
function bounds(image:PNG){let lo=image.height,hi=0
 for(let y=0;y<image.height;y++)if(band(image,y,y+1).mass>3){lo=Math.min(lo,y);hi=y}
 return {lo,hi}
}
test('actual leaf pixels move, roots stay anchored; zero wind and reduced motion stop pixels',async({page},info)=>{
 const failures:string[]=[]
 page.on('pageerror',e=>failures.push(e.message))
 page.on('response',r=>{if(r.status()>=400)failures.push(`${r.status()} ${r.url()}`)})
 await page.setViewportSize({width:1920,height:1080})
 await page.goto('/?motionDebug=1&isolate=foliage&specimen=flower')
 const canvas=page.locator('.planet-stage canvas')
 await expect.poll(async()=>JSON.parse(await canvas.getAttribute('data-motion')||'{}').loadedAssets,{timeout:15000}).toBe(4)
 await page.addStyleTag({content:'.motion-debug{visibility:hidden}'})
 await page.waitForTimeout(500)
 const first=await canvas.screenshot({path:info.outputPath('plants-t0.png')})
 await page.waitForTimeout(2000)
 const second=await canvas.screenshot({path:info.outputPath('plants-t2.png')})
 await page.waitForTimeout(3000)
 const third=await canvas.screenshot({path:info.outputPath('plants-t5.png')})
 const images=[first,second,third].map(b=>PNG.sync.read(b))
 const {lo,hi}=bounds(images[0]),height=hi-lo
 expect(height).toBeGreaterThan(60)
 const tips=images.map(i=>band(i,lo,lo+Math.floor(height*.25)))
 const roots=images.map(i=>band(i,hi-3,hi+1))
 expect(Math.min(...tips.map(x=>x.mass))).toBeGreaterThan(10)
 expect(Math.min(...roots.map(x=>x.mass))).toBeGreaterThan(3)
 const displacement=(points:{x:number}[])=>Math.max(...points.map(p=>p.x))-Math.min(...points.map(p=>p.x))
 const tipPixels=displacement(tips),rootPixels=displacement(roots)
 writeFileSync(info.outputPath('pixel-measurements.json'),JSON.stringify({tipPixels,rootPixels,tips,roots},null,2))
 await info.attach('pixel-measurements',{body:JSON.stringify({tipPixels,rootPixels,tips,roots}),contentType:'application/json'})
 expect(tipPixels).toBeGreaterThan(1)
 expect(rootPixels).toBeLessThan(1)
 await page.goto('/?motionDebug=1&isolate=foliage&specimen=flower&wind=0')
 await expect.poll(async()=>JSON.parse(await canvas.getAttribute('data-motion')||'{}').loadedAssets,{timeout:15000}).toBe(4)
 await page.addStyleTag({content:'.motion-debug{visibility:hidden}'})
 const fixed=await canvas.screenshot();await page.waitForTimeout(2100)
 expect((await canvas.screenshot()).equals(fixed)).toBe(true)
 await page.goto('/?motionDebug=1&isolate=foliage&specimen=flower')
 await expect.poll(async()=>JSON.parse(await canvas.getAttribute('data-motion')||'{}').loadedAssets,{timeout:15000}).toBe(4)
 await page.emulateMedia({reducedMotion:'reduce'})
 await expect.poll(async()=>JSON.parse(await canvas.getAttribute('data-motion')||'{}').pauseReason).toBe('reduced motion')
 await page.addStyleTag({content:'.motion-debug{visibility:hidden}'})
 const reduced=await canvas.screenshot();await page.waitForTimeout(2100)
 expect((await canvas.screenshot()).equals(reduced)).toBe(true)
 expect(failures).toEqual([])
})


test('missing or corrupt GLB is reported, remaining assets stay live',async({page})=>{
 for(const corrupt of [false,true]){
  await page.route('**/bio-fern-*.glb',route=>corrupt?route.fulfill({status:200,body:'broken GLB'}):route.fulfill({status:404,body:'not found'}))
  await page.goto('/?motionDebug=1')
  const state=async()=>JSON.parse(await page.locator('canvas').getAttribute('data-motion')||'{}')
  await expect.poll(async()=>(await state()).loadedAssets,{timeout:15000}).toBe(3)
  await expect.poll(async()=>(await state()).errors?.length).toBe(1)
  expect((await state()).errors[0]).toContain(corrupt?'Invalid GLB':'HTTP 404')
  const t=(await state()).time
  await expect.poll(async()=>(await state()).time).toBeGreaterThan(t)
  await page.unroute('**/bio-fern-*.glb')
 }
})
