import * as THREE from 'three'
import sprigUrl from './assets/cosmos-sprig.webp'
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js'

type Role='fern'|'flower'|'grass'|'rock'
type Asset={role:Role;path:string;provider:string;license:string;commercialUse:boolean;bytes:number}
const manifests=import.meta.glob<Asset[]>('./botanical-manifest.json',{eager:true,import:'default'})
// Coordinates are in stage space. Roots sit inside the frustum, above the meadow lip.
const placements:Record<Role,number[][]>={
 fern:[[-2.8,-1.3,.4,.58],[2.8,-1.3,.4,.55],[-2.3,-1.3,.2,.4],[2.3,-1.3,.2,.4]],
 flower:[[1.13,-1.13,1.0,.83],[-2.15,-1.14,.85,.78],[2.45,-1.22,.3,.68],[-1.45,-1.22,.3,.53],[1.8,-1.22,.3,.57]],
 grass:[[-2.48,-1.2,.6,.65],[.75,-1.22,.35,.38],[2.5,-1.18,.7,.7],[-1.45,-1.24,.35,.5],[-.75,-1.24,.35,.3]],
 rock:[[-2.7,-1.5,.1,.22],[2.7,-1.5,.1,.2]],
}
export function botanicalAssets(scene:THREE.Scene,onReady:(role:Role)=>void){
 const group=new THREE.Group();scene.add(group)
 const controller=new AbortController(), loader=new GLTFLoader()
 const time={value:0},strength={value:1}
 let horizontalScale=1
 const resources=new Set<THREE.BufferGeometry|THREE.Material|THREE.Texture>()
 const stats={loaded:0,animatedMeshes:0,errors:[] as string[],variants:[] as string[],requests:[] as {url:string;status:number;bytes:number}[]}
 const specimens:{role:Role;root:THREE.Group;height:number}[]=[]
 // Each alpha-cutout has its own segmented stem mesh and spatial wind phase.
 const sprigGeometry=new THREE.PlaneGeometry(.68,1,6,24);sprigGeometry.translate(0,.5,0);resources.add(sprigGeometry)
 const sprigTexture=new THREE.TextureLoader().load(sprigUrl,()=>{if(!controller.signal.aborted){stats.loaded++;onReady('flower')}},undefined,()=>{if(!controller.signal.aborted)stats.errors.push('Flower texture unavailable')})
 sprigTexture.colorSpace=THREE.SRGBColorSpace;resources.add(sprigTexture)
 const sprigMaterial=new THREE.MeshBasicMaterial({map:sprigTexture,alphaTest:.38,side:THREE.DoubleSide,color:0xd5c6c9})
 resources.add(sprigMaterial)
 sprigMaterial.onBeforeCompile=shader=>{
  shader.uniforms.windTime=time;shader.uniforms.windStrength=strength
  shader.vertexShader='uniform float windTime;uniform float windStrength;\n'+shader.vertexShader.replace('#include <begin_vertex>',`#include <begin_vertex>
   vec3 origin=(modelMatrix*instanceMatrix*vec4(0.,0.,0.,1.)).xyz;
   float h=clamp(position.y,0.,1.);float phase=origin.x*2.7+origin.z*3.1;
   float gust=sin(windTime*.87+origin.x*.65);
   transformed.x+=windStrength*h*h*(.085*gust+.028*sin(windTime*1.43+phase+position.x*3.));
   transformed.z+=windStrength*h*h*.018*sin(windTime*.69+phase);`)
 }
 const flowers=[[1.13,-1.4,1,.65],[-2.25,-1.47,.8,.9],[-1.95,-1.5,.5,.65],[-2.65,-1.4,1,.85],[-1.65,-1.5,.4,.48],[2.35,-1.45,.7,.8],[2.7,-1.4,1,.95],[1.95,-1.5,.4,.55],[1.65,-1.5,.3,.42]]
 const sprigs=new THREE.InstancedMesh(sprigGeometry,sprigMaterial,flowers.length)
 const pose=new THREE.Object3D()
 flowers.forEach(([x,y,z,scale],i)=>{pose.position.set(x,y,z);pose.rotation.set(0,(i%3-1)*.15,0);pose.scale.set(scale*(i%2?1:-1),scale,scale);pose.updateMatrix();sprigs.setMatrixAt(i,pose.matrix)})
 sprigs.frustumCulled=false;sprigs.userData.role='flower';group.add(sprigs);stats.animatedMeshes++
 for(const asset of Object.values(manifests).flat()){
  if(asset.role==='flower')continue

  if(asset.provider!=='Poly Haven'||asset.license!=='CC0-1.0'||!asset.commercialUse||!Object.hasOwn(placements,asset.role)||!/^\/assets\/bio-[a-z]+-[a-f0-9]{12}\.glb$/.test(asset.path)||asset.bytes>4_000_000)continue
  void(async()=>{try{
   const response=await fetch(asset.path,{signal:controller.signal})
   stats.requests.push({url:asset.path,status:response.status,bytes:asset.bytes})
   if(!response.ok)throw Error(`HTTP ${response.status}: ${asset.path}`)
   const data=await response.arrayBuffer()
   if(data.byteLength!==asset.bytes||data.byteLength<12||new DataView(data).getUint32(0,true)!==0x46546c67)throw Error('Invalid GLB')
   const {scene:pack}=await loader.parseAsync(data,'');pack.updateMatrixWorld(true)
   // Poly Haven publishes specimen libraries, not a single plant. Select the
   // tallest individual variant; never normalize the spatially spread library.
   const candidates=pack.children.filter(child=>!child.name.includes('dead'))
   candidates.sort((a,b)=>new THREE.Box3().setFromObject(b).getSize(new THREE.Vector3()).y-new THREE.Box3().setFromObject(a).getSize(new THREE.Vector3()).y)
   const model=candidates[0]??pack
   stats.variants.push(`${asset.role}: ${model.name}`)
   const bounds=new THREE.Box3().setFromObject(model),size=bounds.getSize(new THREE.Vector3()),center=bounds.getCenter(new THREE.Vector3())
   const span=Math.max(size.x*.65,size.y,size.z*.65)
   if(!Number.isFinite(span)||span<=0)throw Error('Invalid model bounds')
   const template=new THREE.Group()
   model.traverse(node=>{
    if(!(node instanceof THREE.Mesh))return
    // Bake glTF node transforms: all mesh parts share one root/height instead of
    // bending every leaflet about its own local bounding-box minimum.
    const geometry=node.geometry.clone().applyMatrix4(node.matrixWorld)
    geometry.translate(-center.x,-bounds.min.y,-center.z);geometry.scale(1/span,1/span,1/span)
    resources.add(geometry);node.geometry.dispose()
    const source:THREE.Material[]=Array.isArray(node.material)?node.material:[node.material]
    const materials=source.map(original=>{
     const material=original.clone();resources.add(material)
     for(const value of Object.values(original))if(value instanceof THREE.Texture)resources.add(value)
     if(material instanceof THREE.MeshStandardMaterial){
      material.roughness=1
      if(asset.role!=='rock'){material.alphaTest=.45;material.side=THREE.DoubleSide;material.color.set(0xaab9a2)}
     }
     if(asset.role!=='rock'){
      material.customProgramCacheKey=()=>`anchored-wind-v3-${size.y/span}`
      material.onBeforeCompile=shader=>{
       shader.uniforms.windTime=time;shader.uniforms.windStrength=strength
       // This legacy grass GLB embeds an RGB atlas with a black matte, not alpha.
       if(asset.role==='grass')shader.fragmentShader=shader.fragmentShader.replace('#include <map_fragment>',`#include <map_fragment>
        if(max(diffuseColor.r,max(diffuseColor.g,diffuseColor.b))<.012)discard;`)
       shader.vertexShader='uniform float windTime;uniform float windStrength;\n'+shader.vertexShader.replace('#include <begin_vertex>',`#include <begin_vertex>
        vec3 origin=(modelMatrix*instanceMatrix*vec4(0.,0.,0.,1.)).xyz;
        float h=clamp(position.y/${Math.max(size.y/span,.001).toFixed(6)},0.,1.);
        float phase=origin.x*2.7+origin.z*3.1;
        float gust=sin(windTime*.87+origin.x*.65);
        float flutter=sin(windTime*1.43+phase+position.x*3.);
        transformed.x+=windStrength*h*h*(.085*gust+.028*flutter);
        transformed.z+=windStrength*h*h*.018*sin(windTime*.69+phase+position.z*2.);`)
      }
     }
     return material
    })
    const mesh=new THREE.Mesh(geometry,Array.isArray(node.material)?materials:materials[0])
    mesh.frustumCulled=false // shader displacement extends beyond the original bounds
    template.add(mesh)
   })
   if(controller.signal.aborted){resources.forEach(r=>r.dispose());return}
   const matrices=placements[asset.role].map(([x,y,z,scale],i)=>{
    const root=new THREE.Group();root.position.set(x*horizontalScale,y-.28,z);root.scale.setScalar(scale);root.rotation.y=i*1.8;root.updateMatrix()
    specimens.push({role:asset.role,root,height:size.y/span*scale});return root.matrix
   })
   for(const child of template.children){
    const mesh=child as THREE.Mesh
    const batch=new THREE.InstancedMesh(mesh.geometry,mesh.material,matrices.length)
    matrices.forEach((matrix,i)=>batch.setMatrixAt(i,matrix));batch.frustumCulled=false;batch.userData.role=asset.role;group.add(batch)
    if(asset.role!=='rock')stats.animatedMeshes++
   }
   pack.traverse(node=>{if(node instanceof THREE.Mesh){node.geometry.dispose();for(const mat of Array.isArray(node.material)?node.material:[node.material])mat.dispose()}})
   stats.loaded++;onReady(asset.role)
  }catch(error){if(!controller.signal.aborted){stats.errors.push(`${asset.role}: ${String(error)}`);console.warn('Botanical asset unavailable',asset.role,error)}}})()
 }
 return {group,stats,specimens,
  fitWidth(scale:number){
   const ratio=scale/horizontalScale;horizontalScale=scale
   const matrix=new THREE.Matrix4()
   group.children.forEach(child=>{if(child instanceof THREE.InstancedMesh){for(let i=0;i<child.count;i++){child.getMatrixAt(i,matrix);matrix.elements[12]*=ratio;child.setMatrixAt(i,matrix)}child.instanceMatrix.needsUpdate=true}})
  },
  update(t:number,x:number,y:number,intensity=1){time.value=t;strength.value=intensity;group.position.set(-x*.16,-y*.04,0)},
  dispose(){controller.abort();scene.remove(group);group.children.forEach(child=>{if(child instanceof THREE.InstancedMesh)child.dispose()});resources.forEach(r=>r.dispose())},
 }
}
