import * as THREE from 'three'
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js'

function fernGeometry(){
  const parts:THREE.BufferGeometry[]=[]
  for(let pair=1;pair<=10;pair++){
    const height=pair/11
    const span=Math.sin(height*Math.PI)*.24
    for(const side of [-1,1]){
      const leaflet=new THREE.SphereGeometry(1,8,4)
      leaflet.scale(span,.033,.018)
      leaflet.rotateZ(side*.40)
      leaflet.translate(side*span*.7+height*height*.19,height,.05*Math.sin(height*Math.PI))
      parts.push(leaflet)
    }
  }
  const spine=new THREE.TubeGeometry(new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(),new THREE.Vector3(0,.55,.04),new THREE.Vector3(.19,1,0)),12,.009,5,false)
  parts.push(spine)
  const result=mergeGeometries(parts)
  parts.forEach(part=>part.dispose())
  return result
}

export function botanicalDetails(scene:THREE.Scene){
  const fern=fernGeometry()
  const green=new THREE.MeshStandardMaterial({color:0x438b69,roughness:.78})
  const stem=new THREE.TubeGeometry(new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(),new THREE.Vector3(-.06,.48,0),new THREE.Vector3(.08,.88,.02)),12,.009,5,false)
  const fibers:number[]=[]
  const head=new THREE.Vector3(.08,.88,.02)
  for(let i=0;i<90;i++){
    const y=1-2*(i+.5)/90
    const angle=i*2.399963
    const radial=Math.sqrt(1-y*y)
    const direction=new THREE.Vector3(Math.cos(angle)*radial,y,Math.sin(angle)*radial)
    const end=head.clone().addScaledVector(direction,.09)
    const tangent=new THREE.Vector3(-direction.z,0,direction.x).normalize()
    fibers.push(...head.toArray(),...end.toArray())
    for(const side of [-1,1]){
      const tuft=end.clone().addScaledVector(direction,.018).addScaledVector(tangent,side*.018)
      fibers.push(...end.toArray(),...tuft.toArray())
    }
  }
  const fluff=new THREE.BufferGeometry().setAttribute('position',new THREE.Float32BufferAttribute(fibers,3))
  const silk=new THREE.LineBasicMaterial({color:0xe0ebbe,transparent:true,opacity:.62})
  const rock=new THREE.IcosahedronGeometry(1,2)
  const moss=new THREE.MeshStandardMaterial({roughness:1,color:0x315b40,flatShading:true})
  const banks=new THREE.InstancedMesh(rock,moss,14)
  const transform=new THREE.Object3D()
  for(let i=0;i<14;i++){
    const x=(i-6.5)*.39
    transform.position.set(x,-1.60+Math.sin(i*1.7)*.075,.75+Math.cos(i*1.4)*.55)
    transform.rotation.set(i*.12,i*.31,Math.sin(i)*.27)
    transform.scale.set(.27+i%3*.12,.14+i%4*.035,.28+i%5*.055)
    transform.updateMatrix()
    banks.setMatrixAt(i,transform.matrix)
    banks.setColorAt(i,new THREE.Color(i%3===0?0x6b9360:0x476957))
  }
  const garden=new THREE.Group()
  garden.add(banks)
  const plants=[
    [-1.52,-1.38,1.58,.79],[-1.18,-1.33,1.62,.58], [1.48,-1.40,1.5,.74],
    [1.15,-1.37,1.57,.53],[-.72,-1.55,.73,.49],[.83,-1.52,.83,.54],
    [-.91,-1.37,1.32,.70],[1.42,-1.38,1.39,.93],[.53,-1.48,.88,.53],
  ].map(([x,y,z,size],index)=>{
    const plant=new THREE.Group()
    plant.position.set(x,y,z)
    plant.scale.setScalar(size)
    plant.add(new THREE.Mesh(index<6?fern:stem,green))
    if(index>=6)plant.add(new THREE.LineSegments(fluff,silk))
    garden.add(plant)
    return plant
  })
  scene.add(garden)
  return {
    update(time:number,x:number,y:number){
      garden.position.set(-x*.20,-y*.085,0)
      plants.forEach((plant,i)=>{
        const wind=Math.sin(time*.62+plant.position.x*1.5)
        plant.rotation.z=(i%2?.17:-.14)+wind*.05+Math.sin(time*(.74+i*.03)+i)*.021
        plant.rotation.y=Math.sin(i*2.1)*.75+Math.sin(time*.44+i)*.045
      })
    },
    hide(role:string){
      if(role==="fern")plants.slice(0,6).forEach(plant=>plant.visible=false)
      if(role==="rock")banks.visible=false
    },
    dispose(){
      scene.remove(garden)
      banks.dispose()
      for(const resource of [fern,green,stem,fluff,silk,rock,moss])resource.dispose()
    },
  }
}
