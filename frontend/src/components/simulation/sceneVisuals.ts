import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import type { SimulationDirection } from "@/lib/simulation";

export type SceneLighting = "day" | "sunset" | "night";
export type LightColor = "GREEN" | "YELLOW" | "RED";
export const SIGNAL_COLORS = { RED: 0xff424e, YELLOW: 0xffc548, GREEN: 0x39efa2 };
const APPROACHES = [
  { direction: "NORTH", dx: 0, dz: 1, label: "N" },
  { direction: "SOUTH", dx: 0, dz: -1, label: "S" },
  { direction: "EAST", dx: -1, dz: 0, label: "E" },
  { direction: "WEST", dx: 1, dz: 0, label: "W" },
] as const;

/** Presentation assets only. Traffic positions, clocks and decisions live in IntersectionScene. */
export function createSceneVisuals(scene: THREE.Scene, renderer: THREE.WebGLRenderer) {
  const geometries = new Set<THREE.BufferGeometry>();
  const materials = new Set<THREE.Material>();
  const textures = new Set<THREE.Texture>();
  const geometryCache = new Map<string, THREE.BufferGeometry>();
  const materialCache = new Map<number, THREE.MeshStandardMaterial>();
  let seed = 173;
  const random = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
  const mat = (color: number, props: THREE.MeshStandardMaterialParameters = {}) => {
    const m = new THREE.MeshStandardMaterial({ color, roughness: .78, ...props }); materials.add(m); return m;
  };
  const plain = (color: number) => {
    if (!materialCache.has(color)) materialCache.set(color, mat(color));
    return materialCache.get(color)!;
  };
  const shape = (key: string, build: () => THREE.BufferGeometry) => {
    if (!geometryCache.has(key)) { const g = build(); geometries.add(g); geometryCache.set(key, g); }
    return geometryCache.get(key)!;
  };
  const mesh = (geometry: THREE.BufferGeometry, material: THREE.Material, x: number, y: number, z: number, parent: THREE.Object3D = scene) => {
    const item = new THREE.Mesh(geometry, material); item.position.set(x,y,z); item.castShadow = true; item.receiveShadow = true; parent.add(item); return item;
  };
  const box = (w: number, h: number, d: number, color: number | THREE.Material, x: number, y: number, z: number, parent: THREE.Object3D = scene, radius = 0) =>
    mesh(shape(`box:${w}:${h}:${d}:${radius}`, () => radius ? new RoundedBoxGeometry(w,h,d,2,radius) : new THREE.BoxGeometry(w,h,d)), typeof color === "number" ? plain(color) : color, x,y,z,parent);
  const cylinder = (top: number, bottom: number, height: number, color: number | THREE.Material, x: number, y: number, z: number, parent: THREE.Object3D = scene, segments = 12) =>
    mesh(shape(`cyl:${top}:${bottom}:${height}:${segments}`, () => new THREE.CylinderGeometry(top,bottom,height,segments)), typeof color === "number" ? plain(color) : color,x,y,z,parent);
  const canvasTexture = (size: number, paint: (ctx: CanvasRenderingContext2D) => void, height = size) => {
    const canvas = document.createElement("canvas"); canvas.width = size; canvas.height = height;
    const ctx = canvas.getContext("2d"); if (ctx) paint(ctx);
    const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = Math.min(8,renderer.capabilities.getMaxAnisotropy()); textures.add(texture); return texture;
  };
  const grain = (rgb: number[], amplitude: number, paving = false) => {
    const t = canvasTexture(256, ctx => {
      const data = ctx.createImageData(256,256);
      for(let i=0;i<data.data.length;i+=4) { const noise=(random()-.5)*amplitude; for(let c=0;c<3;c++) data.data[i+c]=rgb[c]+noise; data.data[i+3]=255; }
      ctx.putImageData(data,0,0);
      if(paving) { ctx.strokeStyle="rgba(50,60,60,.16)"; ctx.lineWidth=1.3;
        for(let y=0;y<=256;y+=32) {ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(256,y);ctx.stroke();
          for(let x=(y%64?16:0);x<=256;x+=64) {ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x,y+32);ctx.stroke();}}
      }
    }); t.wrapS=t.wrapT=THREE.RepeatWrapping; t.repeat.set(paving?5:14,paving?5:14); return t;
  };
  const asphalt = mat(0xffffff,{map:grain([43,51,59],13),roughness:.96});
  const paving = mat(0xffffff,{map:grain([191,191,179],9,true),roughness:.92});
  const grass = mat(0xffffff,{map:grain([101,130,91],22),roughness:1});
  const roadPaint = mat(0xeee9d7,{roughness:.95});
  const metal = mat(0x343f45,{metalness:.68,roughness:.4});
  const glass = mat(0x4c7380,{metalness:.45,roughness:.2});
  const litWindows = mat(0x58757a,{emissive:0xffc885,emissiveIntensity:0,metalness:.25,roughness:.28});
  const streetBulb = mat(0xffe4ba,{emissive:0xffcf88,emissiveIntensity:.2});
  const headlamp = mat(0xfff3d3,{emissive:0xffeac0,emissiveIntensity:.45,roughness:.22});
  const tailLamp = mat(0xb52035,{emissive:0xff2546,emissiveIntensity:.55,roughness:.22});

  // A compact material batch keeps decorative detail affordable on classroom laptops.
  const batch = (root: THREE.Group | THREE.Scene) => {
    root.updateMatrixWorld(true);
    const rootInverse = new THREE.Matrix4().copy(root.matrixWorld).invert();
    const buckets = new Map<THREE.Material, THREE.Mesh[]>();
    root.traverse(object => {
      if (object instanceof THREE.Mesh && !Array.isArray(object.material)) {
        const list = buckets.get(object.material) ?? []; list.push(object); buckets.set(object.material,list);
      }
    });
    for(const [material,items] of buckets) {
      if(items.length<2) continue;
      const copies = items.map(item => {
        const g = item.geometry.index ? item.geometry.toNonIndexed() : item.geometry.clone();
        return g.applyMatrix4(new THREE.Matrix4().multiplyMatrices(rootInverse,item.matrixWorld));
      });
      const merged = mergeGeometries(copies); copies.forEach(g=>g.dispose());
      if(!merged) continue;
      geometries.add(merged);
      const combined = new THREE.Mesh(merged,material); combined.castShadow=items.some(i=>i.castShadow); combined.receiveShadow=true;
      items.forEach(item=>item.removeFromParent()); root.add(combined);
    }
  };
  const glowTexture = canvasTexture(128, ctx=>{
    const gradient=ctx.createRadialGradient(64,64,1,64,64,64);
    gradient.addColorStop(0,"rgba(255,255,255,.85)");gradient.addColorStop(.22,"rgba(255,255,255,.3)");gradient.addColorStop(1,"rgba(255,255,255,0)");
    ctx.fillStyle=gradient;ctx.fillRect(0,0,128,128);
  });
  const streetPool = new THREE.MeshBasicMaterial({map:glowTexture,color:0xffca86,transparent:true,
    opacity:0,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false});materials.add(streetPool);
  const glow = (color: number, size: number, x: number, y: number, z: number, parent: THREE.Object3D = scene) => {
    const m = new THREE.SpriteMaterial({map:glowTexture,color,transparent:true,opacity:0,depthWrite:false,blending:THREE.AdditiveBlending,toneMapped:false});materials.add(m);
    const sprite=new THREE.Sprite(m);sprite.scale.set(size,size,1);sprite.position.set(x,y,z);parent.add(sprite);return m;
  };
  const sign = (text: string, width: number, height: number, x: number, y: number, z: number, parent: THREE.Object3D, background="#234d57") => {
    const texture=canvasTexture(512,ctx=>{
      ctx.fillStyle=background;ctx.fillRect(0,0,512,96);ctx.strokeStyle="#e5cf9e";ctx.lineWidth=3;ctx.strokeRect(7,7,498,82);
      ctx.fillStyle="#fff3d8";ctx.font=`600 ${text.length>12?37:44}px sans-serif`;ctx.textAlign="center";ctx.textBaseline="middle";ctx.fillText(text,256,50,470);
    },96);
    const material=mat(0xffffff,{map:texture,roughness:.65});
    return mesh(shape(`sign:${width}:${height}`,()=>new THREE.PlaneGeometry(width,height)),material,x,y,z,parent);
  };

  const hemisphere=new THREE.HemisphereLight(0xe4eff9,0x6c7354,2.25);scene.add(hemisphere);
  const sun=new THREE.DirectionalLight(0xffe0ae,3.6);sun.position.set(-28,48,23);sun.castShadow=true;
  sun.shadow.mapSize.set(window.innerWidth<640?1024:2048,window.innerWidth<640?1024:2048);
  Object.assign(sun.shadow.camera,{left:-49,right:49,top:49,bottom:-49,near:1,far:150});sun.shadow.normalBias=.035;sun.shadow.bias=-.00015;sun.shadow.radius=3;scene.add(sun);
  const fill=new THREE.DirectionalLight(0x88b6d2,.65);fill.position.set(35,24,-30);scene.add(fill);
  const pmrem=new THREE.PMREMGenerator(renderer);const room=new RoomEnvironment();
  const environment=pmrem.fromScene(room,.04);scene.environment=environment.texture;room.dispose();pmrem.dispose();
  scene.environmentIntensity=.65;
  const skies = {} as Record<SceneLighting,THREE.CanvasTexture>;
  for(const [name,top,bottom] of [["day","#88b5d0","#dce5d8"],["sunset","#748f9f","#eac7a4"],["night","#101b35","#354b62"]] as const)
    skies[name]=canvasTexture(256,ctx=>{const g=ctx.createLinearGradient(0,0,0,256);g.addColorStop(0,top);g.addColorStop(1,bottom);ctx.fillStyle=g;ctx.fillRect(0,0,256,256)});

  box(500,.15,500,0xa9b5a3,0,-.23,0).castShadow=false;
  box(10,.16,190,asphalt,0,-.01,0).castShadow=false;
  box(190,.16,10,asphalt,0,0,0).castShadow=false;
  box(10,.02,10,asphalt,0,.095,0).castShadow=false;
  for(const sx of [-1,1]) for(const sz of [-1,1]) {
    box(35,.38,35,paving,sx*24,.12,sz*24,scene,.12);
    box(19,.06,15,grass,sx*28,.34,sz*29);
    box(8,.06,12,grass,sx*14,.34,sz*30);
  }
  const arrow = new THREE.Shape();arrow.moveTo(-.15,1.3);arrow.lineTo(.15,1.3);arrow.lineTo(.15,-.4);arrow.lineTo(.55,-.4);arrow.lineTo(0,-1.2);arrow.lineTo(-.55,-.4);arrow.lineTo(-.15,-.4);arrow.closePath();
  const arrowGeometry=new THREE.ShapeGeometry(arrow);geometries.add(arrowGeometry);
  const streetGlows: THREE.SpriteMaterial[]=[];
  for(const a of APPROACHES) {
    const group=new THREE.Group();group.rotation.y=Math.atan2(a.dx,a.dz);scene.add(group);
    for(let d=11;d<90;d+=4) {
      for(const x of [-2.5,2.5])box(.09,.016,1.9,roadPaint,x,.12,-d,group);
      for(const x of [-.15,.15])box(.09,.016,2.2,0xd6b566,x,.13,-d,group);
    }
    for(const x of [-4.8,4.8])box(.09,.014,80,roadPaint,x,.13,-49,group);
    for(let d=8.5;d<41;d+=1.9) for(const x of [-5.25,5.25])box(.35,.26,1.85,Math.round(d/1.9)%2?0xece9dd:0x53615f,x,.21,-d,group);
    for(let x=-4.3;x<5;x+=1.05)box(.61,.014,1.6,roadPaint,x,.14,-6.4,group);
    box(4.55,.02,.24,roadPaint,2.5,.15,-7.7,group);
    for(const x of [1.25,3.65]) {const item=mesh(arrowGeometry,roadPaint,x,.145,-14,group);item.rotation.x=-Math.PI/2;item.castShadow=false;}
    cylinder(.44,.44,.025,0x566064,-3.6,.14,-17,group,20);
    for(let i=0;i<5;i++)box(.42,.01,.025,0x303a40,-3.6,.159,-17-.2+i*.1,group);
    for(const d of [13,30]) for(const side of [-1,1]) {
      const x=side*6.25;
      cylinder(.08,.12,7,metal,x,3.8,-d,group);
      box(1.65,.11,.14,metal,x-side*.7,7.27,-d,group);
      box(.75,.12,.32,metal,x-side*1.35,7.19,-d,group,.04);
      box(.58,.025,.23,streetBulb,x-side*1.35,7.12,-d,group);
      streetGlows.push(glow(0xffcd89,2.4,x-side*1.35,7.08,-d,group));
      const pool=mesh(shape("street-pool",()=>new THREE.PlaneGeometry(7,9)),streetPool,x-side*1.35,.17,-d,group);
      pool.rotation.x=-Math.PI/2;pool.castShadow=false;
    }
    for(const d of [9,11.5]) for(const side of [-1,1]) {
      cylinder(.12,.16,.85,metal,side*6,.8,-d,group);
      cylinder(.13,.13,.09,0xe8c48b,side*6,1.02,-d,group);
    }
    const t=canvasTexture(128,ctx=>{
      ctx.fillStyle="#193f4c";ctx.beginPath();ctx.roundRect(4,4,120,120,32);ctx.fill();ctx.strokeStyle="#d6c39c";ctx.lineWidth=3;ctx.stroke();
      ctx.fillStyle="#f6f2e5";ctx.textAlign="center";ctx.textBaseline="middle";ctx.font="600 70px sans-serif";ctx.fillText(a.label,64,68);
    });
    const m=new THREE.SpriteMaterial({map:t,depthTest:false});materials.add(m);
    const sprite=new THREE.Sprite(m);sprite.scale.set(3.5,3.5,1);sprite.position.set(-a.dx*35,2.2,-a.dz*35);scene.add(sprite);
  }

  // Varied facades, shopfronts and roof furniture give each block a distinct identity.
  const buildings=[
    [-19,-22,8,9,8,0xd4c7aa,"THE CORNER"],[-31,-17,7,5.5,8,0x8baba8,"BOOKS & MORE"],
    [20,-24,9,11,8,0xa4b8bd,"DHAARA"],[32,-17,7,6.5,7,0xd5b39a,"CITY CLINIC"],
    [-23,24,10,7,8,0xba8e7e,"MARKET STREET"],[27,25,9,9,9,0xa5afa0,"CENTRAL PARK"],
  ] as const;
  for(const [x,z,w,h,d,color,name] of buildings) {
    const building=new THREE.Group();building.position.set(x,.35,z);scene.add(building);
    box(w+.6,.35,d+.6,0xc3b9a3,0,.12,0,building,.12);
    box(w,h,d,color,0,h/2+.2,0,building,.1);
    box(w+.5,.25,d+.5,0xeee5d1,0,h+.25,0,building,.06);
    box(w-.55,.05,d-.55,0x8b9693,0,h+.4,0,building);
    for(const side of [-1,1])box(w+.2,.4,.15,0xdbd4be,0,h+.55,side*(d/2+.05),building);
    for(let floor=2.6;floor<h-.5;floor+=2.25) {
      for(let col=-w/2+1.2;col<w/2-.8;col+=2.1) for(const side of [-1,1]) {
        box(1.35,1.55,.12,0xe6ddc9,col,floor,side*(d/2+.03),building);
        box(1.1,1.3,.035,random()>.73?litWindows:glass,col,floor,side*(d/2+.11),building);
        box(1.42,.08,.28,0xb7b6a9,col,floor-.78,side*(d/2+.12),building);
      }
      for(let col=-d/2+1.2;col<d/2-.8;col+=2.1) for(const side of [-1,1]) {
        box(.12,1.55,1.35,0xe6ddc9,side*(w/2+.03),floor,col,building);
        box(.035,1.3,1.1,random()>.73?litWindows:glass,side*(w/2+.11),floor,col,building);
      }
      box(w+.12,.12,d+.12,color,0,floor-1.04,0,building);
    }
    for(const off of [-w*.25,w*.25]) {box(w*.38,1.65,.04,glass,off,1.1,d/2+.05,building);box(.06,1.8,.08,0xe5d9c0,off,1.1,d/2+.1,building);}
    box(w+.35,.15,1.2,0x2f5b60,0,2.1,d/2+.5,building);
    sign(name,w*.83,.7,0,2.42,d/2+.13,building,name==="CITY CLINIC"?"#437778":"#214b54");
    box(1.7,.7,1.25,0xd4d6cd,-w*.22,h+.8,-d*.2,building,.07);
    for(const off of [-.4,.4])cylinder(.26,.26,.04,0x53636a,-w*.22+off,h+1.17,-d*.2,building);
    cylinder(.75,.75,1.1,0x728481,w*.25,h+1,-d*.22,building);
    cylinder(.8,.8,.1,0x596b6e,w*.25,h+1.6,-d*.22,building);
  }
  const leafGeometry=shape("leaves",()=>new THREE.IcosahedronGeometry(1,2));
  const leafColors=[0x547b5a,0x61835a,0x6e905e,0x7f995e];
  const tree = (x: number,z: number,scale=1) => {
    const group=new THREE.Group();group.position.set(x,.38,z);group.scale.setScalar(scale);scene.add(group);
    cylinder(.15,.24,2.8,0x81705a,0,1.4,0,group,8);
    for(const [ox,oy,oz,s] of [[0,3.4,0,1.65],[-.8,2.9,.3,1.15],[.8,3.2,-.2,1.2],[.1,4.25,.1,1.05]]) {
      const crown=mesh(leafGeometry,plain(leafColors[Math.floor(random()*leafColors.length)]),ox,oy,oz,group);crown.scale.set(s,s*.93,s);
    }
  };
  for(const [x,z] of [[-10,-12],[-12,-31],[-37,-30],[-35,-36],[11,-13],[13,-35],[36,-31],[35,-37],[-11,13],[-12,32],[-35,33],[-33,12],[12,12],[13,34],[35,13],[35,36]])tree(x,z,.85+random()*.35);
  for(const sx of [-1,1])for(const sz of [-1,1]) {
    for(let i=0;i<5;i++) {
      const shrub=mesh(leafGeometry,plain(0x63805a),sx*(20+i*1.35),.85,sz*37);shrub.scale.set(.85,.65,.75);
    }
    // A bench, planter and litter bin stay entirely on the pavement.
    const corner=new THREE.Group();corner.position.set(sx*11,.35,sz*19);corner.rotation.y=sx*sz>0?Math.PI/2:0;scene.add(corner);
    for(const x of [-.75,.75])box(.12,.65,.6,metal,x,.32,0,corner);
    for(let i=0;i<4;i++)box(2,.09,.12,0xa17b55,0,.7,-.23+i*.15,corner);
    for(let i=0;i<3;i++)box(2,.12,.08,0xa17b55,0,.95+i*.15,-.35,corner);
    cylinder(.36,.32,.85,0x355f58,2,.45,0,corner);
    cylinder(.39,.39,.1,metal,2,.9,0,corner);
    box(1.25,.65,1.25,0xd1c8af,sx*8.5,.64,sz*10,scene,.08);
    const plant=mesh(leafGeometry,plain(0x62835c),sx*8.5,1.25,sz*10);plant.scale.set(.8,.65,.8);
  }
  // A low-detail surrounding city recedes into haze instead of a floating tile edge.
  for(let i=0;i<22;i++) {
    const angle=i/22*Math.PI*2;const radius=62+random()*22;const x=Math.cos(angle)*radius,z=Math.sin(angle)*radius;
    if(Math.abs(x)<10||Math.abs(z)<10)continue;
    const h=5+random()*13,w=6+random()*6,d=6+random()*6;
    box(w,h,d,[0x91a3a1,0xaaa995,0x97a8af][i%3],x,h/2,z);
    box(w+.2,.2,d+.2,0xb6c1b8,x,h+.1,z);
    for(let floor=2;floor<h-1;floor+=2.5) {
      for(const side of [-1,1]) {
        box(w*.8,.85,.035,glass,x,floor,z+side*(d/2+.025));
        box(.035,.85,d*.8,glass,x+side*(w/2+.025),floor,z);
      }
    }
    if(i%2===0)tree(x-6,z,.9);
  }

  const lamps=new Map<SimulationDirection,Record<LightColor,THREE.MeshStandardMaterial>>();
  const signalGlows=new Map<SimulationDirection,Record<LightColor,THREE.SpriteMaterial[]>>();
  const lensGeometry=shape("lens",()=>new THREE.SphereGeometry(.31,16,10));
  for(const a of APPROACHES) {
    const pole=new THREE.Group();pole.rotation.y=Math.atan2(a.dx,a.dz);scene.add(pole);
    cylinder(.11,.16,6.1,metal,5.7,3.3,-7.8,pole);
    cylinder(.27,.31,.3,0x777c73,5.7,.4,-7.8,pole);
    box(3.4,.14,.14,metal,4.1,6.35,-7.8,pole,.04);
    box(1,2.75,.7,0x1c2b32,2.5,5.2,-7.8,pole,.13);
    box(1.15,2.9,.08,0xe2d9ba,2.5,5.2,-7.43,pole,.08);
    const pair={} as Record<LightColor,THREE.MeshStandardMaterial>;
    const blooms={} as Record<LightColor,THREE.SpriteMaterial[]>;
    (["RED","YELLOW","GREEN"] as LightColor[]).forEach((c,i)=>{
      const m=mat(SIGNAL_COLORS[c],{emissive:SIGNAL_COLORS[c],emissiveIntensity:0,roughness:.22,metalness:.18});pair[c]=m;blooms[c]=[];
      for(const side of [-1,1]) {
        const lens=mesh(lensGeometry,m,2.5,6.03-i*.84,-7.8+side*.4,pole);lens.scale.z=.42;lens.castShadow=false;
        box(.85,.06,.25,0x22343b,2.5,6.39-i*.84,-7.8+side*.42,pole,.02);
        blooms[c].push(glow(SIGNAL_COLORS[c],1.35,2.5,6.03-i*.84,-7.8+side*.49,pole));
      }
    });lamps.set(a.direction,pair);signalGlows.set(a.direction,blooms);
  }
  batch(scene);

  const vehicleTemplates=new Map<string,THREE.Group>();
  const paintCache=new Map<number,THREE.MeshPhysicalMaterial>();
  const carPaint = (color: number) => {
    if(!paintCache.has(color)) {const m=new THREE.MeshPhysicalMaterial({color,metalness:.4,roughness:.27,clearcoat:1,clearcoatRoughness:.18,envMapIntensity:1.1});materials.add(m);paintCache.set(color,m);}
    return paintCache.get(color)!;
  };
  const tyre=mat(0x20282c,{roughness:.98});
  const chrome=mat(0x9aa8ab,{metalness:.85,roughness:.24});
  const carGlass=mat(0x243e4b,{metalness:.35,roughness:.15});
  const createVehicle = (body: number, variant: number, ambulance: boolean) => {
    const key=`${body}:${variant%2}:${ambulance}`;let template=vehicleTemplates.get(key);
    if(!template) {
      template=new THREE.Group();const paint=carPaint(body);
      box(1.43,.48,2.48,paint,0,.51,0,template,.13);
      box(1.45,.16,2.35,0x263238,0,.3,0,template,.05);
      if(ambulance) {
        box(1.4,1.06,2.17,paint,0,1.1,-.13,template,.1);
        box(1.16,.5,.04,carGlass,0,1.2,.99,template,.04);
        box(1.1,.4,.03,carGlass,0,1.23,-1.23,template,.04);
        for(const side of [-1,1]) {
          box(.025,.75,.2,0xd92d45,side*.714,1.12,-.25,template);
          box(.025,.22,.72,0xd92d45,side*.718,1.12,-.25,template);
          box(.025,.4,.53,carGlass,side*.716,1.2,.64,template,.03);
          box(.025,.1,2.05,0xe9b65f,side*.72,.75,-.1,template);
        }
        box(1.2,.06,.4,0x35444d,0,1.66,-.12,template,.03);
      } else {
        const height=variant%2?.61:.5;
        box(1.17,height,1.3,carGlass,0,.97,-.13,template,.1);
        box(1.14,.09,.92,paint,0,.99+height/2,-.2,template,.04);
        for(const side of [-1,1]) {
          box(.045,.49,.09,paint,side*.58,.98,-.1,template);
          box(.13,.1,.21,paint,side*.76,.91,.34,template,.03);
          box(.025,.035,.16,chrome,side*.722,.71,-.27,template);
        }
        box(1.18,.09,.7,paint,0,.76,.77,template,.05);
      }
      for(const x of [-.7,.7])for(const z of [-.78,.78]) {
        const wheel=cylinder(.275,.275,.19,tyre,x,.25,z,template,16);wheel.rotation.z=Math.PI/2;
        const hub=cylinder(.16,.16,.2,chrome,x,.25,z,template,10);hub.rotation.z=Math.PI/2;
        const cap=cylinder(.065,.065,.215,metal,x,.25,z,template,10);cap.rotation.z=Math.PI/2;
      }
      for(const side of [-1,1]) {
        box(.4,.11,.055,headlamp,side*.46,.62,1.24,template,.025);
        box(.34,.11,.055,tailLamp,side*.48,.6,-1.24,template,.025);
      }
      box(.63,.13,.045,metal,0,.43,1.25,template);
      box(.3,.085,.05,0xf2e9ca,0,.38,-1.25,template);
      batch(template);vehicleTemplates.set(key,template);
    }
    const group=template.clone();const beacons:THREE.MeshStandardMaterial[]=[];
    if(ambulance)for(const [i,color] of [0x489dff,0xff5362].entries()) {
      const m=mat(color,{emissive:color,emissiveIntensity:0,roughness:.17});beacons.push(m);
      box(.43,.2,.33,m,i?.3:-.3,1.8,-.12,group,.045);
    }
    return {mesh:group,beacons};
  };
  let currentLighting:SceneLighting="sunset";
  const setLighting = (lighting:SceneLighting) => {
    currentLighting=lighting;const night=lighting==="night";
    scene.background=skies[lighting];scene.fog=new THREE.Fog(night?0x283d52:lighting==="sunset"?0xc4bfa9:0xc8d8d3,95,215);
    hemisphere.intensity=night?.38:lighting==="day"?2:1.35;
    hemisphere.color.setHex(night?0x9ab6e2:0xe3eff9);hemisphere.groundColor.setHex(night?0x354246:0x777754);
    sun.color.setHex(night?0xa7c9ff:lighting==="sunset"?0xffd099:0xfff1d5);
    sun.intensity=night?.48:lighting==="sunset"?2.6:2.8;sun.position.set(-28,lighting==="sunset"?27:52,23);
    fill.intensity=night?.15:.65;scene.environmentIntensity=night?.16:.65;
    renderer.toneMappingExposure=night?.85:.95;
    litWindows.emissiveIntensity=night?2.2:0;streetBulb.emissiveIntensity=night?3:.3;
    glass.emissive.setHex(0xffc587);glass.emissiveIntensity=night?.2:0;
    streetGlows.forEach(m=>m.opacity=night?.6:0);
    streetPool.opacity=night?.22:0;
    headlamp.emissiveIntensity=night?2.4:.45;tailLamp.emissiveIntensity=night?1.7:.55;
  };
  const updateSignalGlow = (direction:SimulationDirection,color:string|undefined) => {
    const glows=signalGlows.get(direction)!;
    for(const c of ["RED","YELLOW","GREEN"] as LightColor[]) glows[c].forEach(m=>m.opacity=color===c?(currentLighting==="night"?.6:.19):0);
  };
  setLighting("sunset");
  return {lamps,materials,createVehicle,setLighting,updateSignalGlow,dispose:()=>{
    geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());textures.forEach(t=>t.dispose());environment.dispose();
  }};
}
