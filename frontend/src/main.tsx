import {lazy,Suspense,useEffect,useState,type FormEvent} from 'react'
import {createRoot} from 'react-dom/client'
import {api,parseEditorial,type Editorial,type Job} from './api'
import {Research,Storyboard} from './editors'
import './style.css'

const Video=lazy(()=>import('./Video'))
const tabs=['Research','Storyboard','Video Studio','Media','QC'] as const
function App(){
  const [jobs,setJobs]=useState<Job[]>([])
  const [job,setJob]=useState<Job>()
  const [value,setValue]=useState<Editorial>()
  const [tab,setTab]=useState<typeof tabs[number]>('Research')
  const [busy,setBusy]=useState('')
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [health,setHealth]=useState<unknown>()
  const [checks,setChecks]=useState([false,false,false])
  const [json,setJson]=useState<string>()
  const dirty=!!job&&!!value&&JSON.stringify(value)!==JSON.stringify(editorial(job))
  function editorial(item:Job):Editorial {
    return {sources:item.sources??[],scenes:item.scenes??[],synthetic_disclosure_reviewed:!!item.synthetic_disclosure_reviewed}
  }
  function select(item:Job){
    setJob(item);setValue(editorial(item));setChecks([false,false,false]);setJson(undefined)
    setJobs(old=>old.some(row=>row.id===item.id)?old.map(row=>row.id===item.id?item:row):[item,...old])
  }
  useEffect(()=>{
    api<Job[]>('/jobs').then(items=>{setJobs(items);if(items[0])select(items[0])}).catch(e=>setError(e.message))
    api<unknown>('/health').then(setHealth).catch(e=>setError(e.message))
  },[])
  async function act(label:string,operation:()=>Promise<void>){
    setBusy(label);setError('');setNotice('')
    try{await operation();setNotice('Thao tác đã hoàn tất.')}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy('')}
  }
  function create(event:FormEvent<HTMLFormElement>){
    event.preventDefault()
    const payload=Object.fromEntries(new FormData(event.currentTarget))
    if(dirty&&!confirm('Bỏ thay đổi chưa lưu?'))return
    void act('Đang tạo dự án',async()=>select(await api<Job>('/jobs','POST',payload)))
  }
  const path=job?'/jobs/'+job.id:''
  const change=(next:Editorial)=>{setValue(next);setChecks([false,false,false])}
  async function save(){
    if(!value)return
    if(value.sources.some(source=>!source.title.trim()||!source.claim.trim()||!source.evidence.trim()||!/^https?:\/\//i.test(source.url)||!Number.isFinite(Date.parse(source.checked_at))))throw Error('Kiểm tra URL, tiêu đề, claim, bằng chứng và thời gian của các nguồn.')
    if(value.scenes.some(scene=>!scene.caption.trim()||!scene.narration.trim()||!Number.isFinite(scene.seconds)||scene.seconds<1||scene.seconds>20))throw Error('Mỗi cảnh cần lời đọc, phụ đề và thời lượng từ 1 đến 20 giây.')
    select(await api<Job>(path+'/editorial','PUT',value))
  }
  return <div className="layout"><nav><strong>◉ AI REVIEW STUDIO</strong><a href="#overview">Overview</a><a href="#projects">Projects</a>{tabs.map(item=><a key={item} aria-current={job&&tab===item?"page":undefined} href="#studio" onClick={()=>setTab(item)}>{item}</a>)}<a href="#settings">Settings</a></nav>
    <main><header>LOCAL WORKSPACE <span>{health?'● Backend online':'○ Đang kiểm tra backend'}</span></header>
    <div className="hero" id="overview"><small>CREATE · RESEARCH · RENDER</small><h1>Create smarter.<br/><em>Publish beautifully.</em></h1><a className="cta" href="#projects">Tạo review mới ↗</a></div>
    <section id="projects"><h2>Dự án</h2>{!jobs.length&&<p>Chưa có dự án. Tạo review đầu tiên để bắt đầu.</p>}<form onSubmit={create}><input aria-label="Chủ đề" name="topic" minLength={2} maxLength={100} required placeholder="Tên chủ đề"/><select aria-label="Định dạng" name="format"><option value="short">Shorts</option><option value="long">Landscape</option></select><button disabled={!!busy}>Tạo dự án</button></form>
    <label>Chọn dự án<select value={job?.id??''} disabled={!!busy} onChange={e=>{const id=e.target.value;if(!dirty||confirm('Bỏ thay đổi chưa lưu?'))void act('Đang tải dự án',async()=>select(await api<Job>('/jobs/'+id)))}}><option value="" disabled>Chọn dự án</option>{jobs.map(item=><option key={item.id} value={item.id}>{item.topic}</option>)}</select></label></section>
    <div className="feedback">{error&&<p role="alert">{error}</p>}<p role="status">{busy||notice}</p></div>
    {job&&value&&<section id="studio"><h2>{job.topic}</h2><p>{job.state} · Demo {job.verification} {dirty&&'· Có thay đổi chưa lưu'}</p>
      <div className="tabs">{tabs.map(item=><button key={item} aria-pressed={tab===item} onClick={()=>setTab(item)}>{item}</button>)}</div>
      {(tab==='Research'||tab==='Storyboard')&&<form onSubmit={e=>{e.preventDefault();void act('Đang lưu',save)}}><fieldset disabled={!!busy}>
        {tab==='Research'?<Research value={value} change={change}/>:<Storyboard value={value} change={change}/>}
        <label className="check"><input type="checkbox" checked={value.synthetic_disclosure_reviewed} onChange={e=>change({...value,synthetic_disclosure_reviewed:e.target.checked})}/>Đã rà soát disclosure</label><p><button>Lưu nội dung</button><button type="button" disabled={dirty} onClick={()=>void act('Đang tạo bản nháp',async()=>change(await api<Editorial>(path+'/draft','POST')))}>Ollama Draft</button></p>
        <button type="button" onClick={()=>setJson(json===undefined?JSON.stringify(value,null,2):undefined)}>Advanced JSON</button>
        {json!==undefined&&<><textarea aria-label="Advanced JSON" value={json} onChange={e=>setJson(e.target.value)}/><button type="button" onClick={()=>{try{change(parseEditorial(json));setJson(undefined)}catch(e){setError(String(e))}}}>Áp dụng JSON</button></>}
      </fieldset></form>}
      {(tab==='Video Studio'||tab==='QC')&&<Suspense fallback={<p>Đang tải studio…</p>}><Video key={job.id+job.render_id} job={job}/></Suspense>}
      {tab==='Video Studio'&&<p><button disabled={!!busy||dirty} onClick={()=>void act('Đang render…',async()=>select(await api<Job>(path+'/render','POST')))}>Render video</button>
      <button disabled={!!busy&&busy!=='Đang render…'} onClick={()=>{const cancel=async()=>{const updated=await api<Job>(path+'/cancel','POST');select(updated);setNotice('Đã gửi yêu cầu hủy.')};if(busy)void cancel().catch(e=>setError(e.message));else void act('Đang hủy',cancel)}}>Hủy job</button></p>}
      {tab==='Media'&&<><h3>Media của dự án</h3>{job.render_id?<><img alt="Thumbnail bản dựng" width="240" src={path+'/artifacts/thumbnail.jpg?v='+job.render_id}/><p><a href={path+'/artifacts/manifest.json'}>Metadata nguồn và quyền sử dụng</a></p><a href={path+'/artifacts/video.mp4'}>Mở MP4</a></>:<p>Chưa có artifact từ bản dựng.</p>}<p>Demo {job.verification}</p>{!!job.demo&&<video controls preload="none" src={path+'/media/demo'} onError={e=>{e.currentTarget.hidden=true;setError('Không tải được demo')}}/>}{job.render_id&&job.scenes.map((scene,i)=><div key={i}><p>{i+1}. {scene.caption}</p><audio aria-label={'Lời đọc cảnh '+(i+1)} controls preload="none" src={path+'/media/narration?scene='+i+'&v='+job.render_id} onError={()=>setError('Không tải được audio cảnh '+(i+1))}/></div>)}{job.demo!==undefined&&<pre>{JSON.stringify(job.demo,null,2)}</pre>}</>}
      {(tab==='QC'||tab==='Video Studio')&&<ul>{job.issues?.map((issue,i)=><li key={i}>{issue}</li>)}</ul>}
      {tab==='QC'&&<><p>Render ID {job.render_id??'chưa có'}</p><p>Disclosure {job.synthetic_disclosure_reviewed?'đã rà soát':'chưa rà soát'}</p><ul>{job.sources.map((source,i)=><li key={i}>{source.title} · {source.claim}<p>{source.evidence}</p></li>)}</ul>
        {['Tôi đã xem video','Tôi đã rà soát dữ kiện','Tôi đã kiểm tra quyền sử dụng'].map((label,i)=><label className="check" key={label}><input type="checkbox" checked={checks[i]} onChange={e=>setChecks(checks.map((value,j)=>i===j?e.target.checked:value))}/>{label}</label>)}
        <button disabled={!!busy||dirty||job.state!=='AWAITING_APPROVAL'||!job.render_id||!checks.every(Boolean)} onClick={()=>void act('Đang duyệt',async()=>select(await api<Job>(path+'/approve','POST',{render_id:job.render_id,preview_reviewed:true,facts_reviewed:true,rights_reviewed:true})))}>Duyệt bản dựng</button></>}
    </section>}
    <section id="settings"><h2>Environment</h2><pre>{health?JSON.stringify(health,null,2):'Chưa có dữ liệu health'}</pre></section>
    </main></div>
}

createRoot(document.getElementById('root')!).render(<App/>)
