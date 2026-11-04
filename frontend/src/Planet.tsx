import {useEffect,useRef,useState} from 'react'
import * as THREE from 'three'
import cloudUrl from './assets/emerald-clouds.webp'
import surfaceUrl from './assets/living-surface.webp'
import {botanicalAssets} from './BotanicalAssets'

export default function Planet({paused}:{paused:boolean}) {
  const host=useRef<HTMLDivElement>(null)
  const inactive=useRef(paused)
  const [assetCredit,setAssetCredit]=useState(false)
  const [fallback,setFallback]=useState(false)
  useEffect(()=>{inactive.current=paused},[paused])
  useEffect(()=>{
    const element=host.current!
    const query=new URLSearchParams(location.search)
    const debug=(import.meta.env.DEV||import.meta.env.VITE_MOTION_DEBUG==='1')&&query.get('motionDebug')==='1'
    const isolate=debug&&query.get('isolate')==='foliage'
    const wind=debug?Math.max(0,Math.min(3,Number(query.get('wind')??1)||0)):1
    let overlay:HTMLPreElement|undefined
    if(debug){overlay=document.createElement('pre');overlay.className='motion-debug';element.append(overlay)}
    if(isolate)element.closest('.hero')?.classList.add('motion-isolate')
    let renderer:THREE.WebGLRenderer
    try {
      renderer=new THREE.WebGLRenderer({alpha:true,antialias:false,powerPreference:'low-power'})
    } catch {
      setFallback(true)
      if(overlay)overlay.textContent='WebGL unavailable; static fallback.'
      return ()=>overlay?.remove()
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio,1.35))
    const scene=new THREE.Scene()
    const camera=new THREE.PerspectiveCamera(35,1,.1,30)
    camera.position.set(0,0,5.8)
    const geometry=new THREE.SphereGeometry(1.48,80,48)
    const surface=new THREE.TextureLoader().load(surfaceUrl,()=>{dirty=true})
    surface.colorSpace=THREE.SRGBColorSpace
    surface.anisotropy=Math.min(4,renderer.capabilities.getMaxAnisotropy())
    const material=new THREE.MeshStandardMaterial({map:surface,color:0xd3dbda,roughness:.86,metalness:0,
      bumpMap:surface,bumpScale:.003,emissive:0x17322b,emissiveMap:surface,emissiveIntensity:.14})
    const globe=new THREE.Mesh(geometry,material)
    globe.rotation.z=.22
    globe.scale.setScalar(.27)
    globe.position.set(2.5,1.25,-1.8)
    scene.add(globe)
    const cloudMap=new THREE.TextureLoader().load(cloudUrl,()=>{dirty=true})
    cloudMap.wrapS=THREE.RepeatWrapping
    const cloudMaterial=new THREE.MeshStandardMaterial({color:0xe5d8ea,alphaMap:cloudMap,transparent:true,opacity:.62,depthWrite:false,roughness:1})
    const clouds=new THREE.Mesh(geometry,cloudMaterial)
    clouds.scale.setScalar(.276);clouds.position.copy(globe.position);clouds.rotation.z=.22
    scene.add(clouds)
    const fogTime={value:0}
    const fogMaterial=new THREE.ShaderMaterial({transparent:true,depthWrite:false,
      uniforms:{map:{value:cloudMap},time:fogTime},
      vertexShader:`varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
      fragmentShader:`uniform sampler2D map;uniform float time;varying vec2 vUv;
        void main(){float edge=smoothstep(0.,.14,vUv.x)*smoothstep(1.,.86,vUv.x)*sin(vUv.y*3.14159);
        float veil=texture2D(map,vec2(vUv.x+time*.009,vUv.y*.7+.1)).r;
        gl_FragColor=vec4(.65,.63,.72,veil*edge*.28);}`})
    const fogGeometry=new THREE.PlaneGeometry(5.8,1.1)
    const fog=new THREE.Mesh(fogGeometry,fogMaterial);fog.position.set(0,-.96,-.2);scene.add(fog)
    const positions=new Float32Array(140*3)
    for(let i=0;i<positions.length;i+=3){
      positions[i]=Math.sin(i*41.7)*5
      positions[i+1]=Math.sin(i*18.2)*3
      positions[i+2]=-2-Math.abs(Math.sin(i*7.1))*5
    }
    const stars=new THREE.BufferGeometry()
    stars.setAttribute('position',new THREE.BufferAttribute(positions,3))
    const starMaterial=new THREE.PointsMaterial({color:0x9ce5ce,size:.025,transparent:true,opacity:.55})
    scene.add(new THREE.Points(stars,starMaterial))
    const pollen=new THREE.BufferGeometry()
    const seeds=Array.from({length:28},(_,i)=>[Math.sin(i*19.1)*2.6,-1.55+(i%7)*.11,.8+(i%5)*.28])
    const pollenPositions=new THREE.Float32BufferAttribute(seeds.flat(),3)
    pollen.setAttribute('position',pollenPositions)
    const pollenMaterial=new THREE.PointsMaterial({color:0xe7d38a,size:.023,transparent:true,opacity:.55,depthWrite:false})
    scene.add(new THREE.Points(pollen,pollenMaterial))
    const atmosphere=new THREE.ShaderMaterial({
      side:THREE.BackSide,transparent:true,depthWrite:false,blending:THREE.AdditiveBlending,
      vertexShader:`varying vec3 vNormal; varying vec3 vEye;
        void main(){vec4 view=modelViewMatrix*vec4(position,1.);vNormal=normalize(normalMatrix*normal);vEye=-view.xyz;gl_Position=projectionMatrix*view;}`,
      fragmentShader:`varying vec3 vNormal; varying vec3 vEye;
        void main(){vec3 n=normalize(vNormal);float limb=pow(1.-abs(dot(n,normalize(vEye))),4.);
          float key=smoothstep(-.65,.95,dot(n,normalize(vec3(-.55,.75,.32))));
          gl_FragColor=vec4(.67,.73,.83,limb*key*.38);}`,
    })
    const shell=new THREE.Mesh(geometry,atmosphere)
    shell.scale.setScalar(.282)
    shell.position.copy(globe.position)
    scene.add(shell)
    // Separate falling petals: original curved geometry, not pixels from the plate.
    const petalGeometry=new THREE.SphereGeometry(.035,8,5,0,Math.PI);
    petalGeometry.scale(1,1.8,.22)
    const petalMaterial=new THREE.MeshStandardMaterial({color:0xe8afc6,roughness:.9,side:THREE.DoubleSide})
    const petals=new THREE.InstancedMesh(petalGeometry,petalMaterial,26)
    petals.frustumCulled=false;scene.add(petals)
    const petalDummy=new THREE.Object3D()
    function updatePetals(t:number){
      for(let i=0;i<26;i++){
        const seed=i*2.39996
        petalDummy.position.set(Math.sin(seed)*3.7+Math.sin(t*.24+seed)*.18,1.9-((t*.055+i*.173)%3.8),Math.cos(seed)*.8)
        petalDummy.rotation.set(t*.24+seed,seed+t*.18,Math.sin(t*.32+seed)*.7)
        petalDummy.scale.setScalar(.22+(i%4)*.09);petalDummy.updateMatrix();petals.setMatrixAt(i,petalDummy.matrix)
      }
      petals.instanceMatrix.needsUpdate=true
    }
    updatePetals(0)
    let sceneTime=0
    const canvas=renderer.domElement
    canvas.setAttribute('aria-hidden','true')
    element.append(canvas)
    let frame=0,last=0,dirty=true,visible=true,lost=false,slowFrames=0
    const foliage=botanicalAssets(scene,()=>{dirty=true;setAssetCredit(true)})
    scene.add(new THREE.HemisphereLight(0xe2d1e4,0x182525,1.2))
    const meadowLight=new THREE.DirectionalLight(0xffe9cb,3.2)
    meadowLight.position.set(-3,4,3)
    scene.add(meadowLight)
    if(isolate){scene.children.forEach(child=>{if(child!==foliage.group&&!(child instanceof THREE.Light))child.visible=false})}
    const viewFrustum=new THREE.Frustum()
    let sampleStart=0,sampleFrames=0,fps=0
    function diagnostics(now:number,reason:string){
      if(!debug)return
      sampleFrames++
      if(now-sampleStart>1000){fps=sampleFrames*1000/(now-sampleStart);sampleFrames=0;sampleStart=now}
      scene.updateMatrixWorld(true)
      viewFrustum.setFromProjectionMatrix(new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix,camera.matrixWorldInverse))
      const visibleAnimatedMeshes=foliage.group.children.filter(child=>child.visible&&child.userData.role!=='rock'&&viewFrustum.intersectsObject(child)).length
      const state={visibleAnimatedMeshes,running:!reason,time:sceneTime,loadedAssets:foliage.stats.loaded,animatedMeshes:foliage.stats.animatedMeshes,
        wind,pauseReason:reason||'none',webgl:lost?'lost':'ready',fps:Number(fps.toFixed(1)),
        calls:renderer.info.render.calls,triangles:renderer.info.render.triangles,geometries:renderer.info.memory.geometries,textures:renderer.info.memory.textures,
        variants:foliage.stats.variants,assets:foliage.stats.requests,errors:foliage.stats.errors,renderer:renderer.getContext().getParameter(renderer.getContext().RENDERER)}
      canvas.dataset.motion=JSON.stringify(state)
      if(overlay)overlay.textContent=JSON.stringify(state,null,2)
    }
    const hero=element.closest<HTMLElement>('.hero')
    let pointerX=0,pointerY=0
    const motion=matchMedia('(prefers-reduced-motion: reduce)')
    function resize(){
      const {clientWidth:width,clientHeight:height}=element
      if(!width||!height)return
      renderer.setSize(width,height,false)
      camera.aspect=width/height
      foliage.fitWidth(Math.min(1,camera.aspect/1.6))
      const celestialScale=camera.aspect<.8?.65:1
      globe.scale.setScalar(.27*celestialScale);clouds.scale.setScalar(.276*celestialScale);shell.scale.setScalar(.282*celestialScale)
      globe.position.x=Math.min(2.5,camera.aspect*1.35)
      clouds.position.copy(globe.position);shell.position.copy(globe.position)
      camera.updateProjectionMatrix()
      dirty=true
    }
    const resizeObserver=new ResizeObserver(resize)
    const intersection=new IntersectionObserver(([entry])=>{visible=entry.isIntersecting;last=0})
    resizeObserver.observe(element)
    intersection.observe(element)
    resize()
    function draw(now:number){
      frame=requestAnimationFrame(draw)
      if(lost||document.hidden||!visible){diagnostics(now,lost?'context lost':document.hidden?'hidden tab':'outside viewport');last=0;return}
      if(motion.matches||inactive.current){
        diagnostics(now,motion.matches?'reduced motion':'render request / video studio')
        if(dirty)renderer.render(scene,camera)
        dirty=false
        last=0
        return
      }
      const elapsed=last?now-last:16
      last=now
      slowFrames=elapsed>25?slowFrames+1:0
      if(slowFrames===30&&renderer.getPixelRatio()>1){renderer.setPixelRatio(1);resize()}
      const dt=Math.min(elapsed,250)/1000
      globe.rotation.y+=dt*.025
      sceneTime+=Math.min(elapsed,1000)/1000
      clouds.rotation.y+=dt*.033
      fogTime.value=sceneTime
      updatePetals(sceneTime)
      camera.position.x+=(pointerX*.5-camera.position.x)*Math.min(1,dt*5)
      camera.position.y+=(pointerY*.34-camera.position.y)*Math.min(1,dt*5)
      // No whole-scene rocking: roots stay anchored while leaf vertices bend.
      seeds.forEach(([x,y,z],i)=>pollenPositions.setXYZ(i,x+Math.sin(sceneTime*.34+i)*.16,y+Math.sin(sceneTime*.43+i*1.7)*.13,z))
      pollenPositions.needsUpdate=true
      starMaterial.opacity=.47+Math.sin(sceneTime*.39)*.055
      const x=camera.position.x/.5
      const y=camera.position.y/.34
      foliage.update(sceneTime,x,y,wind)
      if(isolate&&query.has('specimen'))foliage.group.children.forEach(child=>{child.visible=child.userData.role===query.get('specimen');if(child instanceof THREE.InstancedMesh)child.count=1})
      hero?.style.setProperty('--foreground-x',`${x*11}px`)
      hero?.style.setProperty('--foreground-y',`${y*5}px`)
      hero?.style.setProperty('--midground-x',`${x*4}px`)
      element.style.setProperty('--scene-x',`${x*5+Math.sin(sceneTime*.23)*19}px`)
      element.style.setProperty('--scene-y',`${y*4+Math.sin(sceneTime*.19)*5}px`)
      camera.lookAt(0,0,0)
      renderer.render(scene,camera)
      canvas.dataset.cameraX=camera.position.x.toFixed(3)
      canvas.dataset.cameraY=camera.position.y.toFixed(3)
      diagnostics(now,'')
      dirty=false
    }
    function move(event:PointerEvent){
      const box=element.getBoundingClientRect()
      pointerX=(event.clientX-box.left)/box.width*2-1
      pointerY=1-(event.clientY-box.top)/box.height*2
    }
    function leave(){pointerX=0;pointerY=0}
    function lose(event:Event){event.preventDefault();lost=true;setFallback(true)}
    function restore(){lost=false;dirty=true;setFallback(false)}
    element.addEventListener('pointermove',move)
    element.addEventListener('pointerleave',leave)
    canvas.addEventListener('webglcontextlost',lose)
    canvas.addEventListener('webglcontextrestored',restore)
    frame=requestAnimationFrame(draw)
    return ()=>{
      cancelAnimationFrame(frame)
      resizeObserver.disconnect()
      intersection.disconnect()
      element.removeEventListener('pointermove',move)
      element.removeEventListener('pointerleave',leave)
      canvas.removeEventListener('webglcontextlost',lose)
      canvas.removeEventListener('webglcontextrestored',restore)
      overlay?.remove();hero?.classList.remove('motion-isolate')
      geometry.dispose();material.dispose();surface.dispose();stars.dispose();starMaterial.dispose()
      foliage.dispose()
      atmosphere.dispose();pollen.dispose();pollenMaterial.dispose()
      petals.dispose();petalGeometry.dispose();petalMaterial.dispose()
      cloudMap.dispose();cloudMaterial.dispose();fogGeometry.dispose();fogMaterial.dispose()
      renderer.dispose()
      renderer.forceContextLoss()
      canvas.remove()
    }
  },[])
  return <div ref={host} className={'planet-stage'+(fallback?' planet-fallback':'')} role="img" aria-label={fallback?'Hành tinh minh họa tĩnh':'Hành tinh 3D tương tác'}><div className="cosmic-mist"/>{assetCredit&&!fallback&&<span className="planet-credit">Powered by Poly Haven</span>}</div>
}
