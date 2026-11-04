import * as THREE from 'three'
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js'

type Asset = {role:'fern'|'flower'|'grass'|'rock'; path:string; provider:string; license:string; commercialUse:boolean; bytes:number}
const manifests=import.meta.glob<Asset[]>('./botanical-manifest.json',{eager:true,import:'default'})
const placements={
  fern:[[-1.53,-1.48,1.52,.68],[1.37,-1.5,1.38,.63],[-.71,-1.62,.4,.45]],
  flower:[[1.58,-1.41,1.52,.47],[-1.25,-1.45,1.35,.46],[.46,-1.63,.25,.30]],
  grass:[[-1.1,-1.58,1.0,.32],[.7,-1.64,.53,.38],[1.03,-1.55,1.16,.37],[-.35,-1.65,.46,.27]],
  rock:[[-1.27,-1.6,1.55,.35],[1.23,-1.61,1.14,.4]],
} satisfies Record<Asset['role'],number[][]>

function release(root:THREE.Object3D){
  const resources=new Set<THREE.BufferGeometry|THREE.Material|THREE.Texture>()
  root.traverse(node=>{
    if(!(node instanceof THREE.Mesh))return
    resources.add(node.geometry)
    for(const material of Array.isArray(node.material)?node.material:[node.material]){
      resources.add(material)
      for(const value of Object.values(material))if(value instanceof THREE.Texture)resources.add(value)
    }
  })
  resources.forEach(resource=>resource.dispose())
}

export function botanicalAssets(scene:THREE.Scene,onReady:(role:Asset['role'])=>void){
  const group=new THREE.Group()
  scene.add(group)
  const originals:THREE.Object3D[]=[]
  const plants:{pivot:THREE.Group; moving:boolean; phase:number; depth:number}[]=[]
  const controller=new AbortController()
  const loader=new GLTFLoader()
  const windTime={value:0}
  for(const asset of Object.values(manifests).flat()){
    if(asset.provider!=='Poly Haven'||asset.license!=='CC0-1.0'||asset.commercialUse!==true||
      !Object.hasOwn(placements,asset.role)||!/^\/assets\/bio-[a-z]+-[a-f0-9]{12}\.glb$/.test(asset.path)||
      !Number.isInteger(asset.bytes)||asset.bytes<=0||asset.bytes>4_000_000)continue
    void (async()=>{
      try{
        const response=await fetch(asset.path,{signal:controller.signal})
        if(!response.ok)throw Error(`HTTP ${response.status}`)
        const data=await response.arrayBuffer()
        if(data.byteLength!==asset.bytes||new DataView(data).getUint32(0,true)!==0x46546c67)throw Error('Invalid GLB')
        const {scene:model}=await loader.parseAsync(data,'')
        if(controller.signal.aborted){release(model);return}
        const bounds=new THREE.Box3().setFromObject(model)
        const size=bounds.getSize(new THREE.Vector3())
        const height=Math.max(size.x,size.y,size.z)
        if(!Number.isFinite(height)||height<=0){release(model);return}
        if(asset.role!=='rock'){
          const replaced=new Set<THREE.Material>()
          const retained=new Set<THREE.Material>()
          model.traverse(node=>{
            if(!(node instanceof THREE.Mesh))return
            node.geometry.computeBoundingBox()
            const bounds=node.geometry.boundingBox
            const materials:THREE.Material[]=Array.isArray(node.material)?node.material:[node.material]
            if(!bounds||bounds.max.y-bounds.min.y<.0001){materials.forEach(material=>retained.add(material));return}
            const animated=materials.map(source=>{
              replaced.add(source)
              const material=source.clone()
              const low=bounds.min.y.toFixed(6)
              const range=(bounds.max.y-bounds.min.y).toFixed(6)
              material.customProgramCacheKey=()=>`botanical-wind-${low}-${range}`
              material.onBeforeCompile=shader=>{
                shader.uniforms.botanicalTime=windTime
                shader.vertexShader='uniform float botanicalTime;\n'+shader.vertexShader.replace(
                  '#include <begin_vertex>',
                  `#include <begin_vertex>
                   vec3 origin=(modelMatrix*vec4(0.,0.,0.,1.)).xyz;
                   float tip=clamp((position.y-${low})/${range},0.,1.);
                   float breeze=sin(botanicalTime*.74+origin.x*2.2)+.34*sin(botanicalTime*1.19+origin.z*4.);
                   transformed.x+=breeze*tip*tip*${range}*.028;`)
              }
              return material
            })
            node.material=Array.isArray(node.material)?animated:animated[0]
          })
          replaced.forEach(material=>{if(!retained.has(material))material.dispose()})
        }
        originals.push(model)
        const center=bounds.getCenter(new THREE.Vector3())
        placements[asset.role].forEach(([x,y,z,scale],index)=>{
          const pivot=new THREE.Group()
          const clone=model.clone(true)
          const normalized=scale/height
          clone.scale.multiplyScalar(normalized)
          clone.position.sub(new THREE.Vector3(center.x,bounds.min.y,center.z).multiplyScalar(normalized))
          pivot.add(clone)
          pivot.position.set(x,y,z)
          pivot.rotation.y=index*1.8
          group.add(pivot)
          plants.push({pivot,moving:asset.role!=='rock',phase:index*1.53+x,depth:z})
        })
        onReady(asset.role)
      }catch(error){
        if(!controller.signal.aborted)console.warn('Botanical asset fallback',asset.role,error)
      }
    })()
  }
  return {
    update(time:number,x:number,y:number){
      windTime.value=time
      group.position.set(-x*.18,-y*.06,0)
      for(const {pivot,moving,phase,depth} of plants){
        if(moving)pivot.rotation.z=Math.sin(time*.61+pivot.position.x)*.025+
          Math.sin(time*(.70+depth*.12)+phase)*.018
      }
    },
    dispose(){
      controller.abort()
      scene.remove(group)
      originals.forEach(release)
    },
  }
}
