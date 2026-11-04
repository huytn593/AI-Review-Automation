import {test,expect} from '@playwright/test'
import {PNG} from 'pngjs'

test.use({reducedMotion:'no-preference',video:'on'})

test('WebGL planet rotates, tracks the pointer and falls back on context loss',async({page},info)=>{
  const errors:string[]=[]
  page.on('response',response=>{
    if(response.status()>=400)errors.push(`HTTP ${response.status()} ${response.url()}`)
  })
  page.on('pageerror',error=>errors.push(error.message))
  page.on('console',message=>{if(message.type()==='error')errors.push(message.text())})
  await page.setViewportSize({width:1366,height:768})
  await page.goto('/?motionDebug=1')
  const stage=page.getByRole('img',{name:'Hành tinh 3D tương tác'})
  const canvas=stage.locator('canvas')
  await expect(canvas).toBeVisible()
  // Compare motion only after asynchronous model loads have settled.
  await expect.poll(async()=>JSON.parse(await canvas.getAttribute('data-motion')||'{}').loadedAssets,{timeout:15000}).toBe(4)
  await page.addStyleTag({content:'.motion-debug{visibility:hidden}'})
  const first=await stage.screenshot()
  const firstTime=JSON.parse(await canvas.getAttribute('data-motion')||'{}').time
  await expect.poll(async()=>JSON.parse(await canvas.getAttribute('data-motion')||'{}').time,{timeout:15000}).toBeGreaterThan(firstTime+.5)
  expect((await stage.screenshot()).equals(first)).toBe(false)
  const box=(await stage.boundingBox())!
  await page.mouse.move(box.x+box.width*.87,box.y+box.height*.25)
  const camera=(axis:string)=>async()=>Number(await canvas.getAttribute('data-camera-'+axis))
  await expect.poll(camera('x')).toBeGreaterThan(.2)
  await expect.poll(camera('y')).toBeGreaterThan(.08)
  await page.screenshot({path:info.outputPath('planet-1366.png')})
  await page.mouse.move(0,0)
  await expect.poll(async()=>Math.abs(await camera('x')())).toBeLessThan(.02)
  await expect.poll(async()=>Math.abs(await camera('y')())).toBeLessThan(.02)
  await page.setViewportSize({width:1920,height:1080})
  await page.screenshot({path:info.outputPath('planet-1920.png')})
  await page.emulateMedia({reducedMotion:'reduce'})
  await expect.poll(async()=>JSON.parse(await canvas.getAttribute('data-motion')||'{}').pauseReason).toBe('reduced motion')
  await expect.poll(async()=>{
    const still=await stage.screenshot()
    const next=await stage.screenshot()
    // Chromium's compositor can round a few background color channels by 1/255.
    // Do not allow displacement or a perceptible color change: max delta 1,
    // and fewer than 0.01% of channels may differ. Isolated plants also have
    // a separate byte-identical reduced-motion test in vegetation.spec.ts.
    const a=PNG.sync.read(still),b=PNG.sync.read(next)
    if(a.width!==b.width||a.height!==b.height)return false
    let changed=0
    for(let i=0;i<a.data.length;i++){
      const delta=Math.abs(a.data[i]-b.data[i])
      if(delta>1)return false
      if(delta)changed++
    }
    return changed<a.data.length*.0001
  }).toBe(true)
  expect(errors).toEqual([])
  const lost=await canvas.evaluate(element=>{
    const extension=(element as HTMLCanvasElement).getContext('webgl2')?.getExtension('WEBGL_lose_context')
    extension?.loseContext()
    return Boolean(extension)
  })
  expect(lost).toBe(true)
  await expect(page.getByRole('img',{name:'Hành tinh minh họa tĩnh'})).toBeVisible()
})
