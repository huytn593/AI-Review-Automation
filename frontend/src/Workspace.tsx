import {useEffect,useState} from 'react'
import {api,type Source} from './api'

type Config={ollama_model:string;tts:'edge'|'espeak';voice:string;rate:number;volume:number;encoder:'auto'|'cpu'}
export function Settings(){
  const [config,setConfig]=useState<Config>()
  const [preview,setPreview]=useState('')
  const [message,setMessage]=useState('')
  const [busy,setBusy]=useState(false)
  useEffect(()=>{api<Config>('/settings').then(setConfig).catch(e=>setMessage(e.message))},[])
  return <><h2>Cấu hình sản xuất</h2><p>Cấu hình được lưu trên máy này. Ollama cần model đã tải; Edge TTS cần mạng và gói edge-tts. eSpeak NG chạy offline khi đã cài.</p>{config&&<form onSubmit={async e=>{e.preventDefault();setBusy(true);try{setConfig(await api<Config>('/settings','PUT',config));setMessage('Đã lưu cấu hình.')}catch(e){setMessage(String(e))}finally{setBusy(false)}}}><fieldset disabled={busy}>
    <label>Model Ollama<input value={config.ollama_model} placeholder="qwen3:1.7b-q4_K_M" onChange={e=>setConfig({...config,ollama_model:e.target.value})}/></label>
    <label>Giọng tiếng Việt<select value={config.voice} onChange={e=>setConfig({...config,voice:e.target.value,tts:e.target.value==='vi'?'espeak':'edge'})}><option value="vi">eSpeak NG · Offline</option><option value="vi-VN-HoaiMyNeural">Edge · Hoài My</option><option value="vi-VN-NamMinhNeural">Edge · Nam Minh</option></select></label>
    <label>Tốc độ ({config.rate}%)<input type="range" min={-40} max={40} value={config.rate} onChange={e=>setConfig({...config,rate:e.target.valueAsNumber})}/></label>
    <label>Âm lượng ({config.volume}%)<input type="range" min={-50} max={20} value={config.volume} onChange={e=>setConfig({...config,volume:e.target.valueAsNumber})}/></label>
    <label>Encoder<select value={config.encoder} onChange={e=>setConfig({...config,encoder:e.target.value as Config['encoder']})}><option value="auto">NVENC nếu khả dụng, dự phòng CPU</option><option value="cpu">CPU · libx264</option></select></label><button>Lưu cấu hình</button><button type="button" onClick={async()=>{setBusy(true);setMessage('Đang tạo giọng đọc theo cấu hình đã lưu…');try{const result=await api<{url:string}>('/voice-preview','POST',{text:'Xin chào, đây là bản nghe thử giọng tiếng Việt trong AI Review Studio.'});setPreview(result.url);setMessage('Đã tạo bản nghe thử.')}catch(e){setMessage(String(e))}finally{setBusy(false)}}}>Nghe giọng đã lưu</button>{preview&&<audio controls src={preview}/>}</fieldset></form>}<p aria-live="polite">{message}</p></>
}
type Item=Source&{id:string;provider:string;freshness_heuristic:number|null}
type Results={items:Item[];providers:{provider:string;status:string}[];checked_at?:string;ranking?:string}
export function Discovery({add}:{add:(source:Source)=>void}){
  const [result,setResult]=useState<Results>({items:[],providers:[]})
  const [query,setQuery]=useState('')
  const [message,setMessage]=useState('')
  const [busy,setBusy]=useState(false)
  useEffect(()=>{api<Results>('/discovery').then(setResult).catch(e=>setMessage(e.message))},[])
  return <><h2>Trend Discovery</h2><p>Thông báo từ RSS chính thức OpenAI và Google AI. Điểm mới chỉ là heuristic theo ngày đăng; chưa có dữ liệu lượng tìm kiếm hoặc mức cạnh tranh. Nguồn được tải chưa có nghĩa claim đã đúng.</p>
    <form onSubmit={async e=>{e.preventDefault();setBusy(true);setMessage('Đang đọc nguồn…');try{setResult(await api<Results>('/discovery','POST',{query}));setMessage('Đã lưu snapshot nguồn.')}catch(e){setMessage(String(e))}finally{setBusy(false)}}}><input aria-label="Lọc chủ đề" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Từ khóa trong feed; để trống xem tất cả"/><button disabled={busy}>Thu thập nguồn mới</button></form>
    <p aria-live="polite">{message}</p>{result.checked_at&&<p>Lần thu thập: {new Date(result.checked_at).toLocaleString()}</p>}{result.providers.map(p=><p key={p.provider} role="alert">{p.provider}: không truy cập được nguồn trong lần này.</p>)}
    <div className="discovery-grid">{result.items.map(item=><article key={item.id}><small>{item.provider} · Điểm mới {item.freshness_heuristic??'chưa rõ'}/100</small><h3><a href={item.url} target="_blank" rel="noreferrer">{item.title}</a></h3><p>{item.evidence}</p><p>UNVERIFIED</p><button type="button" onClick={()=>{add(item);setMessage('Đã đưa nguồn vào bản nháp nghiên cứu. Hãy đối chiếu claim và lưu.')}}>Đưa vào nghiên cứu</button></article>)}</div>{!result.items.length&&<p>Chưa có kết quả phù hợp trong snapshot.</p>}</>
}
export function History({id,state}:{id:string;state:string}){
  const [rows,setRows]=useState<{event:string;at:string;data:unknown}[]>([])
  const [error,setError]=useState('')
  useEffect(()=>{api<typeof rows>('/jobs/'+id+'/history').then(setRows).catch(e=>setError(e.message))},[id,state])
  return <details><summary>Lịch sử thao tác</summary>{error&&<p role="alert">{error}</p>}{rows.map((row,i)=><p key={i}>{new Date(row.at).toLocaleString()} · {row.event}<small> {JSON.stringify(row.data)}</small></p>)}</details>
}
