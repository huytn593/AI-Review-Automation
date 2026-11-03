import * as THREE from 'three'

/** Procedural foliage. Each depth band batches its leaves and blossoms. */
export function botanicalEnvironment(scene: THREE.Scene) {
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
          blooms.setColorAt(i*6+k,new THREE.Color(i%3===0?0xd6c99c:0x78b99d))
        }
      }
    }
    group.add(stems)
    if(bloomCount)group.add(blooms)
    scene.add(group)
    return {group,stems,blooms}
  })
  const dustGeometry=new THREE.BufferGeometry()
  const points=Array.from({length:36},()=>[random()*4.6-2.3,random()*1.35-1.5,random()*2]).flat()
  dustGeometry.setAttribute('position',new THREE.Float32BufferAttribute(points,3))
  const dustMaterial=new THREE.PointsMaterial({color:0xccedaf,size:.018,opacity:.46,transparent:true,depthWrite:false})
  const dust=new THREE.Points(dustGeometry,dustMaterial)
  scene.add(dust)
  return {
    update(time:number){
      layers.forEach(({group},index)=>{
        group.rotation.z=Math.sin(time*.62+index*1.7)*(.007+index*.007)
        group.position.x=Math.sin(time*.47+index)*.022
      })
      dust.position.y=Math.sin(time*.27)*.11
      dust.position.x=Math.sin(time*.22)*.14
    },
    dispose(){
      for(const {group,stems,blooms} of layers){scene.remove(group);stems.dispose();blooms.dispose()}
      scene.remove(dust,light,ambient)
      blade.dispose();leaf.dispose();flower.dispose();petal.dispose()
      dustGeometry.dispose();dustMaterial.dispose()
    },
  }
}
