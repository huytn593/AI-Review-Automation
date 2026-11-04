import * as THREE from 'three'
import {botanicalDetails} from './BotanicalDetails'
import {botanicalAssets} from './BotanicalAssets'

/** Procedural foliage. Each depth band batches its leaves and blossoms. */
export function botanicalEnvironment(scene: THREE.Scene, onAssetReady:()=>void) {
  const blade = new THREE.BufferGeometry()
  blade.setAttribute('position', new THREE.Float32BufferAttribute([
    0,0,0, -.13,.38,.025, 0,.47,.1, .13,.38,.025, .19,1,0,
  ],3))
  blade.setIndex([0,1,2,0,2,3,1,4,2,2,4,3])
  blade.computeVertexNormals()
  const leaf = new THREE.MeshStandardMaterial({side:THREE.DoubleSide,roughness:.82})
  const flower = new THREE.IcosahedronGeometry(1,0)
  const petal = new THREE.MeshStandardMaterial({roughness:.7,emissive:0x315440,emissiveIntensity:.24})
  const transform = new THREE.Object3D()
  const palette = [0x164738,0x22634e,0x327861,0x3c856d].map(value=>new THREE.Color(value))
  const light = new THREE.PointLight(0x79eac0,18,9)
  light.position.set(0,.45,1.5)
  const ambient = new THREE.HemisphereLight(0x8dd5be,0x071712,1.25)
  scene.add(light,ambient)
  let seed=424
  const random=()=>{
    seed=(1664525*seed+1013904223)>>>0
    return seed/4294967296
  }
  const layers=[{z:-1.1,y:-1.84,count:78},{z:.25,y:-1.65,count:86},{z:1.45,y:-1.34,count:105}].map(({z,y,count},band)=>{
    const group=new THREE.Group()
    group.position.z=z
    const stems=new THREE.InstancedMesh(blade,leaf,count)
    const bloomCount=band===0?0:5
    const blooms=new THREE.InstancedMesh(flower,petal,bloomCount*6)
    const petals:THREE.Matrix4[]=[]
    const plants:{matrix:THREE.Matrix4; phase:number; speed:number}[]=[]
    for(let i=0;i<count;i++){
      const side=i%2?1:-1
      const x=side*(.20+Math.pow(random(),.65)*2.3)
      const tall=i<bloomCount
      const height=tall?.38+random()*.32:.08+random()*.34
      transform.position.set(x,y+(random()-.5)*.18,(random()-.5)*.55)
      transform.rotation.set((random()-.5)*.7,random()*Math.PI*2,(random()-.5)*.8)
      transform.scale.set(tall?.16:.28+random()*.32,height,height)
      transform.updateMatrix()
      stems.setMatrixAt(i,transform.matrix)
      plants.push({matrix:transform.matrix.clone(),phase:random()*Math.PI*2,speed:.34+random()*.57})
      stems.setColorAt(i,palette[i%palette.length])
      if(tall){
        const tip=new THREE.Vector3(.19,1,0).applyMatrix4(transform.matrix)
        for(let k=0;k<6;k++){
          const angle=k*Math.PI/3
          transform.position.copy(tip).add(new THREE.Vector3(Math.cos(angle)*.034,Math.sin(angle)*.026,0))
          transform.rotation.set(.3,0,angle)
          transform.scale.set(.026,.012,.018)
          transform.updateMatrix()
          blooms.setMatrixAt(i*6+k,transform.matrix)
          petals.push(transform.matrix.clone())
          blooms.setColorAt(i*6+k,new THREE.Color(i%3===0?0xd6c99c:0x78b99d))
        }
      }
    }
    group.add(stems)
    if(bloomCount)group.add(blooms)
    scene.add(group)
    return {group,stems,blooms,plants,bloomCount,petals}
  })
  const dustGeometry=new THREE.BufferGeometry()
  const points=Array.from({length:36},()=>[random()*4.6-2.3,random()*1.35-1.5,random()*2]).flat()
  dustGeometry.setAttribute('position',new THREE.Float32BufferAttribute(points,3))
  const dustMaterial=new THREE.PointsMaterial({color:0xccedaf,size:.018,opacity:.46,transparent:true,depthWrite:false})
  const dust=new THREE.Points(dustGeometry,dustMaterial)
  scene.add(dust)
  const hazeGeometry=new THREE.PlaneGeometry(7,3)
  const hazeMaterial=new THREE.ShaderMaterial({
    transparent:true,depthWrite:false,
    uniforms:{time:{value:0}},
    vertexShader:'varying vec2 tex; void main(){tex=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
    fragmentShader:`varying vec2 tex; uniform float time;
      void main(){
        float center=.32+.08*sin(tex.x*6.+time*.19);
        float distance=(tex.y-center)*8.;
        float veil=exp(-distance*distance)*sin(tex.x*3.14159);
        gl_FragColor=vec4(.14,.54,.42,veil*.16);
      }`,
  })
  const haze=new THREE.Mesh(hazeGeometry,hazeMaterial)
  haze.position.set(0,-.35,-1.8)
  scene.add(haze)
  const bend=new THREE.Matrix4()
  const instance=new THREE.Matrix4()
  const tip=new THREE.Vector3()
  const originalTip=new THREE.Vector3()
  const positions=dustGeometry.getAttribute('position')
  const details=botanicalDetails(scene)
  const imported=botanicalAssets(scene,role=>{
    onAssetReady()
    details.hide(role)
    if(role==="flower")for(const {blooms} of layers)blooms.visible=false
  })
  return {
    update(time:number,pointerX:number,pointerY:number){
      details.update(time,pointerX,pointerY)
      imported.update(time,pointerX,pointerY)
      layers.forEach(({group,stems,blooms,plants,bloomCount,petals},index)=>{
        group.rotation.z=Math.sin(time*.62+index*1.7)*.008
        group.position.x=-pointerX*(.025+index*.085)
        group.position.y=-pointerY*index*.045
        plants.forEach(({matrix,phase,speed},i)=>{
          bend.makeRotationZ(Math.sin(time*speed+phase)*(.06+index*.025))
          instance.copy(matrix).multiply(bend)
          stems.setMatrixAt(i,instance)
          if(i<bloomCount){
            tip.set(.19,1,0).applyMatrix4(instance)
            originalTip.set(.19,1,0).applyMatrix4(matrix)
            tip.sub(originalTip)
            for(let k=0;k<6;k++){
              const petalIndex=i*6+k
              instance.copy(petals[petalIndex])
              instance.elements[12]+=tip.x
              instance.elements[13]+=tip.y
              instance.elements[14]+=tip.z
              blooms.setMatrixAt(petalIndex,instance)
            }
          }
        })
        stems.instanceMatrix.needsUpdate=true
        if(bloomCount)blooms.instanceMatrix.needsUpdate=true
      })
      for(let i=0;i<positions.count;i++){
        const offset=i*3
        positions.setXYZ(i,points[offset]+Math.sin(time*(.17+i%5*.025)+i)*.12,
          points[offset+1]+Math.sin(time*.29+i*1.9)*.11,points[offset+2])
      }
      positions.needsUpdate=true
      hazeMaterial.uniforms.time.value=time
    },
    dispose(){
      details.dispose()
      imported.dispose()
      for(const {group,stems,blooms} of layers){scene.remove(group);stems.dispose();blooms.dispose()}
      scene.remove(dust,light,ambient,haze)
      hazeGeometry.dispose();hazeMaterial.dispose()
      blade.dispose();leaf.dispose();flower.dispose();petal.dispose()
      dustGeometry.dispose();dustMaterial.dispose()
    },
  }
}
