import {test,expect} from '@playwright/test'

test.use({reducedMotion:'no-preference',video:'on'})

test('WebGL planet rotates, tracks the pointer and falls back on context loss',async({page},info)=>{
  const errors:string[]=[]
  page.on('response',response=>{
    if(response.status()>=400)errors.push(`HTTP ${response.status()} ${response.url()}`)
  })
  page.on('pageerror',error=>errors.push(error.message))
  page.on('console',message=>{if(message.type()==='error')errors.push(message.text())})
  await page.setViewportSize({width:1366,height:768})
  await page.goto('/')
  const stage=page.getByRole('img',{name:'Hành tinh 3D tương tác'})
  const canvas=stage.locator('canvas')
  await expect(canvas).toBeVisible()
  const first=await stage.screenshot()
  await expect.poll(async()=>(await stage.screenshot()).equals(first)).toBe(false)
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
  await expect.poll(async()=>{
    const still=await stage.screenshot()
    return (await stage.screenshot()).equals(still)
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
