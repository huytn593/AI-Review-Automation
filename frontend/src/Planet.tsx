import {useEffect,useRef,useState} from 'react'
import * as THREE from 'three'
import {botanicalEnvironment} from './BotanicalEnvironment'

export default function Planet({paused}:{paused:boolean}) {
  const host=useRef<HTMLDivElement>(null)
  const inactive=useRef(paused)
  const [fallback,setFallback]=useState(false)
  useEffect(()=>{inactive.current=paused},[paused])
  useEffect(()=>{
    const element=host.current!
    let renderer:THREE.WebGLRenderer
    try {
      renderer=new THREE.WebGLRenderer({alpha:true,antialias:false,powerPreference:'low-power'})
    } catch {
      setFallback(true)
      return
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio,1.35))
    const scene=new THREE.Scene()
    const camera=new THREE.PerspectiveCamera(35,1,.1,30)
    camera.position.set(0,0,5.8)
    const geometry=new THREE.SphereGeometry(1.36,64,40)
    const material=new THREE.ShaderMaterial({
      vertexShader:`
        varying vec3 localPoint;
        varying vec3 normalWorld;
        varying vec3 worldPoint;
        void main(){
          localPoint=position;
          normalWorld=normalize(mat3(modelMatrix)*normal);
          worldPoint=(modelMatrix*vec4(position,1.0)).xyz;
          gl_Position=projectionMatrix*viewMatrix*vec4(worldPoint,1.0);
        }`,
      fragmentShader:`
        varying vec3 localPoint;
        varying vec3 normalWorld;
        varying vec3 worldPoint;
        float hash(vec3 p){return fract(sin(dot(p,vec3(127.1,311.7,74.7)))*43758.5453);}
        float noise(vec3 p){
          vec3 i=floor(p), f=fract(p);
          f=f*f*(3.0-2.0*f);
          return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),
            mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);
        }
        void main(){
          vec3 p=localPoint*3.2;
          float terrain=.57*noise(p)+.28*noise(p*2.4)+.15*noise(p*5.6);
          float land=smoothstep(.43,.60,terrain);
          float clouds=smoothstep(.50,.76,noise(p*1.7+vec3(6.,2.,1.))*.68+noise(p*5.)*.32);
          float detail=noise(p*15.);
          vec3 n=normalize(normalWorld);
          float incidence=dot(n,normalize(vec3(-.55,.75,.43)));
          float daylight=smoothstep(-.18,.86,incidence);
          float rim=pow(1.0-max(dot(n,normalize(cameraPosition-worldPoint)),0.0),3.3);
          vec3 surface=mix(vec3(.012,.057,.061),vec3(.13,.48,.32)*(.68+detail*.65),land);
          float veins=pow(1.0-abs(sin(terrain*32.0)),12.0);
          vec3 color=surface*(.22+daylight*1.15)+vec3(.12,.53,.40)*rim*(.22+daylight)+vec3(.11,.24,.19)*veins*land*daylight;
          color+=vec3(.27,.52,.44)*clouds*daylight*.34;
          color+=vec3(.48,.34,.13)*smoothstep(.82,.98,detail)*land*(1.-daylight)*.26;
          gl_FragColor=vec4(color,1.0);
        }`,
    })
    const globe=new THREE.Mesh(geometry,material)
    globe.rotation.z=.22
    scene.add(globe)
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
    const botanicals=botanicalEnvironment(scene)
    let sceneTime=0
    const canvas=renderer.domElement
    canvas.setAttribute('aria-hidden','true')
    element.append(canvas)
    let frame=0,last=0,dirty=true,visible=true,lost=false,slowFrames=0
    let pointerX=0,pointerY=0
    const motion=matchMedia('(prefers-reduced-motion: reduce)')
    function resize(){
      const {clientWidth:width,clientHeight:height}=element
      if(!width||!height)return
      renderer.setSize(width,height,false)
      camera.aspect=width/height
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
      if(lost||document.hidden||!visible){last=0;return}
      if(motion.matches||inactive.current){
        if(dirty)renderer.render(scene,camera)
        dirty=false
        last=0
        return
      }
      const elapsed=last?now-last:16
      last=now
      slowFrames=elapsed>25?slowFrames+1:0
      if(slowFrames===30&&renderer.getPixelRatio()>1){renderer.setPixelRatio(1);resize()}
      const dt=Math.min(elapsed,45)/1000
      globe.rotation.y+=dt*.19
      sceneTime+=dt
      camera.position.x+=(pointerX*.5-camera.position.x)*Math.min(1,dt*5)
      camera.position.y+=(pointerY*.34-camera.position.y)*Math.min(1,dt*5)
      botanicals.update(sceneTime,camera.position.x/.5,camera.position.y/.34)
      camera.lookAt(0,0,0)
      renderer.render(scene,camera)
      canvas.dataset.cameraX=camera.position.x.toFixed(3)
      canvas.dataset.cameraY=camera.position.y.toFixed(3)
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
      geometry.dispose();material.dispose();stars.dispose();starMaterial.dispose()
      botanicals.dispose()
      renderer.dispose()
      renderer.forceContextLoss()
      canvas.remove()
    }
  },[])
  return <div ref={host} className={'planet-stage'+(fallback?' planet-fallback':'')} role="img" aria-label={fallback?'Hành tinh minh họa tĩnh':'Hành tinh 3D tương tác'}/>
}
