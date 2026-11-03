import {useEffect,useRef,useState} from 'react'
import {api,type Job,type Segment} from './api'

export default function Video({job}:{job:Job}) {
  const [segments,setSegments]=useState<Segment[]>([])
  const [subtitles,setSubtitles]=useState<{start:number;text:string}[]>([])
  const [error,setError]=useState('')
  const [position,setPosition]=useState(0)
  const player=useRef<HTMLVideoElement>(null)
  const root='/jobs/'+job.id+'/artifacts/'
  const artifact=(name:string)=>root+name+'?v='+encodeURIComponent(job.render_id??'')
  useEffect(()=>{
    if(!job.render_id)return
    const controller=new AbortController()
    api<Segment[]>(root+'timeline.json','GET',undefined,controller.signal).then(setSegments).catch(e=>{if(!controller.signal.aborted)setError(String(e))})
    fetch(root+'subtitles.srt',{signal:controller.signal}).then(async response=>{
      if(!response.ok)throw Error('Không tải được phụ đề')
      const srt=await response.text()
      setSubtitles(srt.trim().split(/\r?\n\r?\n/).flatMap(block=>{
        const [,timing,...lines]=block.split(/\r?\n/)
        const match=timing?.match(/^(\d+):(\d+):(\d+),(\d+)/)
        if(!match)return []
        const [,hours,minutes,seconds,ms]=match.map(Number)
        return [{start:hours*3600+minutes*60+seconds+ms/1000,text:lines.join(' ')}]
      }))
    }).catch(e=>{if(!controller.signal.aborted)setError(String(e))})
    return ()=>controller.abort()
  },[root,job.render_id])
  return <><div className="video-grid"><aside><h3>Cảnh</h3>{job.scenes.map((scene,i)=><details key={i}><summary>{i+1}. {scene.caption}</summary><p>{scene.narration}</p><small>{scene.visual_type}</small></details>)}</aside>
    <div className="screen">{job.render_id?<video ref={player} controls preload="metadata" poster={artifact('thumbnail.jpg')} src={artifact('video.mp4')} onTimeUpdate={e=>setPosition(e.currentTarget.currentTime)}/>:<p>Chưa có bản dựng</p>}</div>
    <aside><h3>Thông tin render</h3><p>{job.format==='short'?'Shorts · 9:16':'Landscape · 16:9'}</p><p>{job.state}</p><p>{job.technical?.encoder??'Chưa có thông tin encoder'}</p>
    {job.render_id&&['video.mp4','thumbnail.jpg','subtitles.srt','timeline.json','manifest.json'].map(name=><a key={name} href={artifact(name)} download>{name}</a>)}</aside></div>
    {error&&<p role="alert">{error}</p>}
    {segments.length>0&&<label>Vị trí phát (giây)<input type="range" min={0} max={segments.at(-1)!.start+segments.at(-1)!.duration} step={0.1} value={position} onChange={e=>{const time=e.target.valueAsNumber;if(player.current)player.current.currentTime=time;setPosition(time)}}/></label>}
    {segments.length>0&&<><h3>Timeline · {position.toFixed(1)} giây</h3><div className="timeline">{segments.map((segment,i)=><button key={i} style={{flexGrow:segment.duration}} onClick={()=>{if(player.current)player.current.currentTime=segment.start}}><small>{segment.start.toFixed(1)}s · {segment.duration.toFixed(1)}s</small><br/>{segment.caption}</button>)}</div></>}
    {subtitles.length>0&&<><h3>Track phụ đề</h3><div className="timeline">{subtitles.map((cue,i)=><button key={i} onClick={()=>{if(player.current)player.current.currentTime=cue.start}}>{cue.start.toFixed(1)}s · {cue.text}</button>)}</div></>}
  </>
}
