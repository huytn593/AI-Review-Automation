export type Source = {url:string; title:string; claim:string; evidence:string; checked_at:string}
export type Scene = {narration:string; caption:string; seconds:number; visual_type:'demo'|'original_text_card'; citations:number[]}
export type Editorial = {sources:Source[]; scenes:Scene[]; synthetic_disclosure_reviewed:boolean}
export type Job = Editorial & {id:string; topic:string; format:'short'|'long'; state:string; verification:string; issues?:string[]; render_id?:string; technical?:{encoder:string}; demo?:unknown}
export type Segment = Scene & {start:number; duration:number}

export async function api<T>(path:string, method='GET', body?:unknown, signal?:AbortSignal):Promise<T> {
  const response=await fetch(path,{method,signal,headers:body===undefined?undefined:{'Content-Type':'application/json'},body:JSON.stringify(body)})
  const data=await response.json()
  if(!response.ok) throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail ?? data))
  return data
}

export function parseEditorial(text:string):Editorial {
  const value=JSON.parse(text)
  const strings=(record:unknown,keys:string[])=>!!record&&typeof record==='object'&&keys.every(key=>typeof (record as Record<string,unknown>)[key]==='string')
  if(!value||!Array.isArray(value.sources)||value.sources.length>20||
     !value.sources.every((source:unknown)=>strings(source,['url','title','claim','evidence','checked_at']))||
     !Array.isArray(value.scenes)||value.scenes.length<1||value.scenes.length>60||
     !value.scenes.every((scene:Scene)=>strings(scene,['narration','caption','visual_type'])&&
       ['demo','original_text_card'].includes(scene.visual_type)&&Number.isFinite(scene.seconds)&&
       Array.isArray(scene.citations)&&scene.citations.length<=10&&
       scene.citations.every(n=>Number.isInteger(n)&&n>=1&&n<=value.sources.length))) {
    throw Error('JSON không đúng cấu trúc nguồn và storyboard.')
  }
  return {...value,synthetic_disclosure_reviewed:value.synthetic_disclosure_reviewed===true}
}
