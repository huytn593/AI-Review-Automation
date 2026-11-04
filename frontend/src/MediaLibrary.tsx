import {useEffect,useState,type FormEvent} from 'react'
import {api,type Job} from './api'
type Asset={id:string;name:string;kind:'image'|'video'|'audio';bytes:number;source:string;license:string;sha256:string;duration:number}
export default function MediaLibrary({job,dirty,updated}:{job:Job;dirty:boolean;updated:(job:Job)=>void}){
 const [items,setItems]=useState<Asset[]>([])
 const [busy,setBusy]=useState(false)
 const [message,setMessage]=useState('')
 const [selected,setSelected]=useState('')
 const path='/jobs/'+job.id
 const running=['QUEUED','RENDERING','CANCELLING'].includes(job.state)
 async function refresh(){setItems(await api<Asset[]>(path+'/library'))}
 useEffect(()=>{setSelected('');refresh().catch(e=>setMessage(e.message))},[job.id])
 async function upload(event:FormEvent<HTMLFormElement>){
  event.preventDefault();const form=event.currentTarget;const data=new FormData(form);const file=data.get('file') as File
  if(file.size>100_000_000){setMessage('Tệp tối đa 100 MB.');return}
  setBusy(true);setMessage('Đang nhập và kiểm tra media…')
  try{
   const query=new URLSearchParams({name:file.name,source:String(data.get('source')),license:String(data.get('license')),commercial_rights:'true'})
   const response=await fetch(path+'/library?'+query,{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file})
   const result=await response.json();if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:JSON.stringify(result.detail))
   await refresh();form.reset();setMessage(result.reused?'Tệp trùng đã có trong thư viện.':'Đã nhập media và lưu nguồn/quyền sử dụng.')
  }catch(e){setMessage(String(e))}finally{setBusy(false)}
 }
 async function verify(event:FormEvent<HTMLFormElement>){
  event.preventDefault();const data=Object.fromEntries(new FormData(event.currentTarget));setBusy(true)
  try{updated(await api<Job>(path+'/verification','PUT',{...data,asset_id:selected,commercial_rights:true}));setMessage('Đã lưu bằng chứng demo. Bản duyệt trước mất hiệu lực; hãy dựng lại.')}
  catch(e){setMessage(String(e))}finally{setBusy(false)}
 }
 return <><h3>Thư viện media</h3><p>Nhập tệp bạn có quyền sử dụng. Hình AI minh họa không phải bằng chứng đã dùng sản phẩm.</p>
 <form onSubmit={upload}><fieldset disabled={busy||running}><legend>Nhập media · tối đa 100 MB</legend>
 <label>Tệp media<input required type="file" name="file" accept=".mp4,.webm,.wav,.mp3,.png,.jpg,.jpeg"/></label>
 <label>Nguồn / chủ sở hữu<input required name="source" maxLength={500} placeholder="URL nguồn hoặc tên chủ sở hữu"/></label>
 <label>Giấy phép<select name="license"><option value="own">Tôi sở hữu</option><option value="CC0">CC0</option><option value="CC-BY">CC BY · ghi rõ tác giả trong nguồn</option><option value="licensed">Có giấy phép thương mại</option></select></label>
 <label className="check"><input required type="checkbox"/>Tôi đã kiểm tra quyền sử dụng thương mại</label><button>Nhập và kiểm tra tệp</button></fieldset></form>
 <p aria-live="polite">{message}</p><div className="discovery-grid">{items.map(item=><article key={item.id}><h4>{item.name}</h4>{item.kind==='image'?<img style={{maxWidth:'100%'}} src={path+'/library/'+item.id} alt={item.name}/>:item.kind==='video'?<video controls preload="none" style={{maxWidth:'100%'}} src={path+'/library/'+item.id}/>:<audio controls preload="none" src={path+'/library/'+item.id}/>}<p>{(item.bytes/1_000_000).toFixed(2)} MB · {item.license}</p><p>{item.source}</p><details><summary>Checksum</summary><small>{item.sha256}</small></details>{item.kind==='video'&&<button type="button" onClick={()=>setSelected(item.id)}>Chọn làm bằng chứng demo</button>}</article>)}</div>
 {selected&&<form onSubmit={verify}><fieldset disabled={busy||running||dirty}><legend>Xác minh demo đã chọn</legend><p>{items.find(item=>item.id===selected)?.name}</p><label>Kịch bản kiểm thử<textarea required name="scenario" minLength={10} maxLength={600}/></label><label>Kết quả quan sát<textarea required name="result" minLength={10} maxLength={600}/></label><label>URL sản phẩm được ghi hình<input required type="url" name="recording_source"/></label><label className="check"><input required type="checkbox"/>Tôi đã xem video và xác nhận đây là demo thật có quyền sử dụng</label><button>Lưu xác minh demo</button></fieldset>{dirty&&<p>Lưu thay đổi nghiên cứu/kịch bản trước khi xác minh demo.</p>}</form>}
 </>
}
