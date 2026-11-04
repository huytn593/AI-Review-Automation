import type {Editorial, Scene, Source} from './api'

type Props = {value:Editorial; change:(value:Editorial)=>void}
export function Research({value,change}:Props) {
  const update=(index:number, source:Source)=>change({...value,sources:value.sources.map((item,i)=>i===index?source:item)})
  function remove(index:number) {
    const citation=index+1
    change({...value,sources:value.sources.filter((_,i)=>i!==index),scenes:value.scenes.map(scene=>({...scene,citations:scene.citations.filter(n=>n!==citation).map(n=>n>citation?n-1:n)}))})
  }
  return <><h2>Nguồn nghiên cứu</h2><p>Đối chiếu và nhập nguồn thủ công.</p>{value.sources.map((source,index)=><fieldset key={index}><legend>Nguồn {index+1}</legend>
    {(['url','title','claim','evidence','checked_at'] as const).map(field=><label key={field}>{field}<input required type={field==='url'?'url':'text'} value={source[field]} onChange={e=>update(index,{...source,[field]:e.target.value})}/></label>)}
    <label>Trạng thái claim<select value={source.status??'UNVERIFIED'} onChange={e=>update(index,{...source,status:e.target.value as Source['status']})}>{['UNVERIFIED','PARTIALLY_VERIFIED','VERIFIED','CONFLICTED','OUTDATED'].map(status=><option key={status}>{status}</option>)}</select></label>
    <label>Giải thích xác minh<textarea maxLength={600} value={source.confidence_reason??''} onChange={e=>update(index,{...source,confidence_reason:e.target.value})}/></label>
    <button type="button" onClick={()=>remove(index)}>Xóa nguồn {index+1}</button></fieldset>)}
    <button type="button" disabled={value.sources.length>=20} onClick={()=>change({...value,sources:[...value.sources,{url:'',title:'',claim:'',evidence:'',checked_at:new Date().toISOString()}]})}>Thêm nguồn</button></>
}

export function Storyboard({value,change,rewrite}:Props&{rewrite?:(index:number)=>void}) {
  const {scenes,sources}=value
  const replace=(next:Scene[])=>change({...value,scenes:next})
  function move(index:number, direction:number) {
    const next=[...scenes]
    const [scene]=next.splice(index,1)
    next.splice(index+direction,0,scene)
    replace(next)
  }
  return <><h2>Storyboard</h2>{scenes.map((scene,index)=>{
    const update=(patch:Partial<Scene>)=>replace(scenes.map((item,i)=>i===index?{...item,...patch}:item))
    return <fieldset key={index}><legend>Cảnh {index+1}</legend>
      <label>Lời đọc<textarea required maxLength={450} value={scene.narration} onChange={e=>update({narration:e.target.value})}/></label>
      <label>Phụ đề<input required maxLength={100} value={scene.caption} onChange={e=>update({caption:e.target.value})}/></label>
      <label>Giây<input required type="number" min={1} max={20} step="any" value={Number.isFinite(scene.seconds)?scene.seconds:''} onChange={e=>update({seconds:e.target.valueAsNumber})}/></label>
      <label>Hình ảnh<select value={scene.visual_type} onChange={e=>update({visual_type:e.target.value as Scene['visual_type']})}><option value="original_text_card">Thẻ chữ</option><option value="demo">Demo</option></select></label>
      <div>{sources.map((source,i)=><label key={i} className="check"><input type="checkbox" checked={scene.citations.includes(i+1)} disabled={scene.citations.length>=10&&!scene.citations.includes(i+1)} onChange={e=>update({citations:e.target.checked?[...scene.citations,i+1]:scene.citations.filter(n=>n!==i+1)})}/>{i+1}. {source.title||'Nguồn chưa đặt tên'}</label>)}</div>
      <button type="button" disabled={!rewrite} onClick={()=>rewrite?.(index)}>Viết lại cảnh bằng Ollama</button>
      <button type="button" disabled={!index} onClick={()=>move(index,-1)}>↑ Lên</button>
      <button type="button" disabled={index===scenes.length-1} onClick={()=>move(index,1)}>↓ Xuống</button>
      <button type="button" disabled={scenes.length>=60} onClick={()=>replace([...scenes.slice(0,index+1),scene,...scenes.slice(index+1)])}>Nhân bản</button>
      <button type="button" disabled={scenes.length===1} onClick={()=>replace(scenes.filter((_,i)=>i!==index))}>Xóa cảnh</button>
    </fieldset>
  })}<button type="button" disabled={scenes.length>=60} onClick={()=>replace([...scenes,{narration:'',caption:'',seconds:6,visual_type:'original_text_card',citations:[]}])}>Thêm cảnh</button></>
}
