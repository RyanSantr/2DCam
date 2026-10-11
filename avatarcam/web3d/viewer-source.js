import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

const $ = id => document.getElementById(id);
let capture = new URLSearchParams(location.search).has('capture');
const embedded = new URLSearchParams(location.search).has('embedded');
if (embedded) document.body.classList.add('embedded');
const bridge = embedded ? await new Promise(resolve => new QWebChannel(qt.webChannelTransport, channel => resolve(channel.objects.studio))) : null;
if (capture) document.body.classList.add('capture');
const canvas = $('canvas'), stage = $('stage');
const renderer = new THREE.WebGLRenderer({canvas, alpha:true, antialias:true, powerPreference:'default'});
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;
renderer.setClearColor(0x000000, 0);
const scene = new THREE.Scene();
scene.add(new THREE.HemisphereLight(0xbbeeff, 0x354459, 2.2));
const key = new THREE.DirectionalLight(0xffffff, 3.3); key.position.set(-2, 3, 4); scene.add(key);
const rim = new THREE.DirectionalLight(0x6af2df, 2); rim.position.set(2, 2, -3); scene.add(rim);
const camera = new THREE.PerspectiveCamera(32, 1, .01, 100);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true; controls.dampingFactor = .12; controls.enabled = !capture;
controls.minDistance = .2; controls.maxDistance = 20;
const loader = new GLTFLoader();
loader.register(parser => new VRMLoaderPlugin(parser));
// Os modelos aceitos sao autocontidos. Nunca busca texturas externas.
loader.manager.setURLModifier(url => {
  if (url.startsWith('blob:') || url.startsWith('data:')) return url;
  const parsed = new URL(url, location.href);
  if (parsed.origin !== location.origin || !parsed.pathname.startsWith(new URL('model/', location.href).pathname)) throw new Error('Recurso externo bloqueado. Exporte um GLB autocontido.');
  return parsed.href;
});
let snapshot = {}, model = null, vrm = null, mixer = null, morphs = [], mouth = 0;
let modelURL = null, generation = 0, loadedURL = null, lastRevision = -1;
let lastState = 0, connected = false, busy = false, modelHeight = 1.8, frameCounter = 0, statsStart = performance.now();
const expressionNames = ['happy','angry','sad','relaxed','surprised'];
let appliedTargets = new Set(), postMorphTargets = new Map(), modelBaseY = 0, loadError = '';
const exportCanvas = document.createElement('canvas');
const defaultPosition = new THREE.Vector3(0, 1.15, 3.5);
const defaultTarget = new THREE.Vector3(0, .95, 0);
camera.position.copy(defaultPosition); controls.target.copy(defaultTarget); controls.update();
const clock = new THREE.Clock();
let nextBlink = 3, blinkStart = -100, baseRotation = 0;

function toast(message) { $('toast').textContent = message; $('toast').classList.add('show'); clearTimeout(toast.timer); toast.timer = setTimeout(() => $('toast').classList.remove('show'), 3200); }
async function command(action, value=null) {
  if (bridge) return await new Promise(resolve => bridge.command(action, JSON.stringify(value), resolve));
  try {
    const response = await fetch('api/command', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action,value}), signal:AbortSignal.timeout(2500)});
    if (!response.ok) throw new Error();
    return true;
  } catch { toast('Abra o app para usar este controle.'); return false; }
}
function dispose() {
  if (mixer) { mixer.stopAllAction(); if (model) mixer.uncacheRoot(model); }
  if (model) { scene.remove(model); VRMUtils.deepDispose(model); }
  renderer.renderLists.dispose();
  model = vrm = mixer = null; morphs = []; mouth = 0; appliedTargets.clear(); postMorphTargets.clear();
}
function fitCamera() {
  defaultTarget.set(0, modelHeight * .54, 0);
  const distance = modelHeight * Math.max(2.15, 1.2/Math.max(.35,camera.aspect));
  defaultPosition.set(0, modelHeight * .59, distance);
  camera.position.copy(defaultPosition); controls.target.copy(defaultTarget); controls.update();
}
function applyCamera(saved) {
  if (saved?.position?.length === 3 && saved?.target?.length === 3) {
    camera.position.fromArray(saved.position); controls.target.fromArray(saved.target); controls.update();
  } else fitCamera();
}
function normalize(name) { return name.toLowerCase().replace(/[^a-z0-9]/g,''); }
function capabilities() {
  const available = vrm?.expressionManager?.expressionMap || {};
  const hasMouth = Boolean(available.aa) || morphs.some(m => m.mouth.length);
  $('capabilities').textContent = model ? `${vrm ? 'VRM · humanoide' : 'GLB · modelo 3D'} · ${hasMouth ? 'boca por voz disponível' : 'sem expressão de boca; visualize e enquadre'}` : 'Importe um VRM ou GLB na aba Avatar 3D do app.';
  document.querySelectorAll('[data-expression]').forEach(button => {
    button.disabled = button.dataset.expression !== 'neutral' && !available[button.dataset.expression];
    button.title = button.disabled ? 'Esta expressão não está incluída no modelo.' : '';
  });
}
async function loadModel(url) {
  const serial = ++generation;
  modelURL = url;
  if (!url) { dispose(); loadedURL = null; $('model-name').textContent='Nenhum modelo'; $('notice').textContent='Importe seu avatar no painel ou experimente o exemplo.'; capabilities(); return; }
  dispose(); loadedURL=null; loadError='';
  $('notice').textContent='Carregando avatar…';
  try {
    const gltf = await loader.loadAsync(url);
    if (serial !== generation) { VRMUtils.deepDispose(gltf.scene); return; }
    dispose();
    vrm = gltf.userData.vrm || null;
    model = vrm ? vrm.scene : gltf.scene;
    if (vrm) {
      VRMUtils.rotateVRM0(vrm);
      const left = vrm.humanoid.getNormalizedBoneNode('leftUpperArm');
      const right = vrm.humanoid.getNormalizedBoneNode('rightUpperArm');
      if (left) left.rotation.z = -1.15;
      if (right) right.rotation.z = 1.15;
      vrm.update(0);
    }
    model.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(model), size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3());
    if (!Number.isFinite(size.y) || size.length() < .0001) throw new Error('Modelo sem geometria visível.');
    const scale = 1.8 / Math.max(size.y, size.x, .01);
    model.scale.multiplyScalar(scale);
    model.position.sub(new THREE.Vector3(center.x*scale, box.min.y*scale, center.z*scale));
    modelHeight = size.y*scale;
    model.updateMatrixWorld(true);
    vrm?.springBoneManager?.setInitState();
    model.traverse(object => {
      if (object.isMesh) object.frustumCulled = false;
      if (object.morphTargetDictionary) {
        const mouthIndices = [], blinkIndices = [];
        Object.entries(object.morphTargetDictionary).forEach(([name,index]) => {
          const normalized = normalize(name);
          if (/^(aa|a|mouthopen|jawopen|visemeaa|visemea)$/.test(normalized)) mouthIndices.push(index);
          if (/^(blink|eyeblinkleft|eyeblinkright|blinkleft|blinkright)$/.test(normalized)) blinkIndices.push(index);
        });
        morphs.push({object, mouth:mouthIndices, blink:blinkIndices});
      }
    });
    if (gltf.animations.length) { mixer = new THREE.AnimationMixer(model); mixer.clipAction(gltf.animations[0]).play(); }
    baseRotation = model.rotation.y; modelBaseY = model.position.y;
    scene.add(model); fitCamera(); applyCamera(snapshot.camera); lastRevision = snapshot.cameraRevision;
    loadedURL = url;
    $('model-name').textContent = decodeURIComponent(url.split('/').pop());
    $('scene-title').textContent = vrm ? 'Seu avatar, com vida.' : 'Seu avatar em 3D.';
    $('notice').textContent=''; capabilities();
  } catch (error) {
    if (serial !== generation) return;
    dispose(); loadedURL = null; loadError = error.message;
    $('notice').textContent='Não foi possível abrir o modelo. Use VRM/GLB com recursos incorporados e sem Draco/KTX2. ' + error.message;
    capabilities();
  }
}
async function poll() {
  try {
    if (bridge) snapshot = JSON.parse(await new Promise(resolve => bridge.state(resolve)));
    else {
      const response = await fetch('api/state', {cache:'no-store', signal:AbortSignal.timeout(2000)});
      if (!response.ok) throw new Error();
      snapshot = await response.json();
    } lastState = performance.now(); connected = true;
    if (embedded) {
      capture=Boolean(snapshot.capture); document.body.classList.toggle('capture',capture);
      stage.style.background=capture ? (snapshot.background || '#00ff00') : '#1a1c20';
      controls.enabled=!capture;
      const ratio=Math.min(devicePixelRatio,snapshot.pixelRatio || 1);
      if (renderer.getPixelRatio()!==ratio) { renderer.setPixelRatio(ratio); renderer.setSize(stage.clientWidth,stage.clientHeight,false); }
    }
    $('connection').textContent='● App conectado'; $('connection').classList.add('connected');
    $('microphone').textContent=snapshot.microphone ? 'Desativar microfone' : 'Ativar microfone';
    $('mic-indicator').classList.toggle('active', Boolean(snapshot.microphone));
    if (snapshot.model !== modelURL) loadModel(snapshot.model);
    if (model && snapshot.cameraRevision !== lastRevision) { applyCamera(snapshot.camera); lastRevision=snapshot.cameraRevision; }
    // Uma captura acompanha o enquadramento salvo no editor.
    if (capture && model && snapshot.camera) applyCamera(snapshot.camera);
    document.querySelectorAll('[data-expression]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.expression === snapshot.expression)));
  } catch {
    connected=false; snapshot.level=0; snapshot.speaking=false;
    $('connection').textContent='App desconectado'; $('connection').classList.remove('connected');
    $('mic-indicator').classList.remove('active');
    $('voice-status').textContent='Abra o app para reconectar';
  } finally { setTimeout(poll, connected ? snapshot.active===false ? 250 : 1000/Math.min(30,snapshot.fps || 30) : 1000); }
}
let lastRender=0, deltaAccumulator=0;
function animate(now) {
  const schedule=()=>setTimeout(()=>requestAnimationFrame(animate),snapshot.active===false || document.hidden ? 250 : Math.max(0,1000/(snapshot.paused ? 5 : snapshot.fps || 30)-(performance.now()-lastRender)-14));
  if (snapshot.active===false || document.hidden) { clock.getDelta(); schedule(); return; }
  deltaAccumulator += Math.min(clock.getDelta(), .1);
  if (now-lastRender < 1000/(snapshot.paused ? 5 : snapshot.fps || 30)-2) { schedule(); return; }
  const delta=Math.min(deltaAccumulator, .2); deltaAccumulator=0; lastRender=now;
  const seconds=now/1000;
  const fresh=connected && now-lastState<1500;
  const level=fresh ? (snapshot.level || 0) : 0;
  const face = fresh && snapshot.face?.detected ? snapshot.face : null;
  const targetMouth = Math.max(face?.jaw || 0, fresh && snapshot.speaking ? Math.min(1, level*2.8) : 0);
  mouth = THREE.MathUtils.damp(mouth, targetMouth, 18, delta);
  if (seconds>nextBlink) { blinkStart=seconds; nextBlink=seconds+3+Math.random()*3; }
  const blinkPhase=seconds-blinkStart, blink=blinkPhase<.18 ? Math.sin(blinkPhase/.18*Math.PI) : 0;
  if (!snapshot.paused) {
  if (mixer) mixer.update(delta);
  if (vrm) {
    vrm.expressionManager?.setValue('aa', snapshot.expressionMapping?.mouth ? 0 : mouth);
    vrm.expressionManager?.setValue('blink', face ? 0 : blink);
    vrm.expressionManager?.setValue('blinkLeft', snapshot.expressionMapping?.blink ? 0 : face?.blinkLeft || 0);
    vrm.expressionManager?.setValue('blinkRight', snapshot.expressionMapping?.blink ? 0 : face?.blinkRight || 0);
    expressionNames.forEach(name => vrm.expressionManager?.setValue(name, 0));
    const head = vrm.humanoid.getNormalizedBoneNode('head');
    if (head) head.rotation.set(face ? -face.pitch : 0, face ? -face.yaw : 0, face ? -face.roll : 0, 'YXZ');
    if (vrm.lookAt) {
      vrm.lookAt.autoUpdate = false;
      vrm.lookAt.applier.applyYawPitch((face?.gazeX || 0)*25, (face?.gazeY || 0)*20);
    }
    const gesture=snapshot.gesture, phase=gesture?.progress || 0, envelope=Math.sin(phase*Math.PI);
    const nod=gesture?.name==='yes' ? Math.sin(phase*Math.PI*6)*.3*envelope : 0;
    const shake=gesture?.name==='no' ? Math.sin(phase*Math.PI*6)*.35*envelope : 0;
    if (head) { head.rotation.x+=nod; head.rotation.y+=shake; }
    const left=vrm.humanoid.getNormalizedBoneNode('leftUpperArm'), right=vrm.humanoid.getNormalizedBoneNode('rightUpperArm');
    if (left) left.rotation.z=-1.15;
    if (right) right.rotation.z=1.15;
    if (gesture?.name==='wave' && right) right.rotation.z=1.15-envelope*1.65+Math.sin(phase*Math.PI*8)*.2*envelope;
    if (gesture?.name==='celebrate') {
      if (left) left.rotation.z=-1.15+envelope*1.65;
      if (right) right.rotation.z=1.15-envelope*1.65;
    }
    applyExpressions(face, blink);
    vrm.update(delta);
    postMorphTargets.forEach((value,target)=>{morphs.forEach(m=>{const i=m.object.morphTargetDictionary[target.slice(6)];if(i!==undefined)m.object.morphTargetInfluences[i]=value;});});
  } else morphs.forEach(({object,mouth:indices,blink:eyes}) => { indices.forEach(i => object.morphTargetInfluences[i]=mouth); eyes.forEach(i => object.morphTargetInfluences[i]=face ? (face.blinkLeft+face.blinkRight)/2 : blink); });
  }
  if (!vrm && !snapshot.paused) applyExpressions(face, blink);
  controls.autoRotate=false;
  if (model && !vrm && !snapshot.paused) {
    const gesture=snapshot.gesture, phase=gesture?.progress || 0, e=Math.sin(phase*Math.PI);
    model.rotation.x=(face ? -face.pitch*.4 : 0)+(gesture?.name==='yes' ? Math.sin(phase*Math.PI*6)*.15*e : 0);
    model.rotation.z=(face ? -face.roll*.4 : 0)+(gesture?.name==='no' ? Math.sin(phase*Math.PI*6)*.15*e : 0);
    model.position.y=modelBaseY+(gesture?.name==='celebrate' ? Math.abs(Math.sin(phase*Math.PI*5))*.08*e : 0);
  }
  if (model && !snapshot.paused) model.rotation.y = baseRotation + (snapshot.rotate ? (Date.now()/1000 - (snapshot.animationEpoch || Date.now()/1000))*.15 : 0);
  controls.autoRotateSpeed=.7;
  controls.update(delta); renderer.render(scene,camera);
  $('meter').style.width=(level*100)+'%'; $('level').textContent=Math.round(level*100)+'%';
  if (fresh) $('voice-status').textContent=snapshot.speaking ? 'Voz detectada' : snapshot.microphone ? 'Ouvindo microfone' : 'Microfone desligado';
  schedule();
  frameCounter++;
  if (now-statsStart>1000) { const fps=Math.round(frameCounter*1000/(now-statsStart)); $('render-stats').textContent=`WebGL · ${fps} FPS`; frameCounter=0; statsStart=now;
    window.studioDiagnostics = {fps, textures:renderer.info.memory.textures, geometries:renderer.info.memory.geometries, calls:renderer.info.render.calls, pixelRatio:renderer.getPixelRatio(), capture, loaded:Boolean(model), vrm:Boolean(vrm), mouth, face:Boolean(face), head:vrm?.humanoid?.getNormalizedBoneNode('head')?.rotation.toArray().slice(0,3), width:canvas.width, height:canvas.height, editedValues:Object.fromEntries([...new Set([snapshot.expressionPreview?.target,...Object.values(snapshot.expressionMapping || {}).map(x=>x.target)].filter(Boolean))].map(t=>[t,t.startsWith('morph:') ? Math.max(0,...morphs.map(m=>m.object.morphTargetInfluences[m.object.morphTargetDictionary[t.slice(6)]] || 0)) : vrm?.expressionManager?.getValue(t) || 0])), expressions:expressionNames.filter(name => expressionCatalog().includes(snapshot.expressionMapping?.[name]?.target ?? name)), expressionCatalog:expressionCatalog(), gestures:gestureCatalog(), expressionValues:Object.fromEntries([...expressionNames,'aa'].map(n=>[n,vrm?.expressionManager?.getValue(n) || 0])), hasMouth:Boolean(vrm?.expressionManager?.expressionMap?.aa) || morphs.some(m=>m.mouth.length) || expressionCatalog().includes(snapshot.expressionMapping?.mouth?.target), triangles:renderer.info.render.triangles, error:loadError};
    if (bridge) bridge.report(JSON.stringify(window.studioDiagnostics));
  }
}

function expressionCatalog() {
  return [...new Set([...Object.keys(vrm?.expressionManager?.expressionMap || {}), ...morphs.flatMap(m=>Object.keys(m.object.morphTargetDictionary || {}).map(n=>'morph:'+n))])].slice(0,256);
}
function setTarget(target,value) {
  if (!target) return;
  if (target.startsWith('morph:')) { postMorphTargets.set(target,value); morphs.forEach(m=>{ const i=m.object.morphTargetDictionary[target.slice(6)]; if (i!==undefined) m.object.morphTargetInfluences[i]=value; }); }
  else vrm?.expressionManager?.setValue(target,value);
  appliedTargets.add(target);
}
function applyExpressions(face,blink) {
  const targets=[...appliedTargets]; postMorphTargets.clear(); targets.forEach(t=>setTarget(t,0)); appliedTargets.clear();
  // Limpa só o que o editor controla, preservando os demais parâmetros do modelo.
  const map=snapshot.expressionMapping || {};
  const mapped=(action,value,def)=>{ const item=map[action]; setTarget(item?.target ?? def,value*(item?.intensity ?? 1)); };
  mapped('mouth',mouth,'aa');
  mapped('blink',face ? (vrm && !map.blink ? 0 : Math.max(face.blinkLeft,face.blinkRight)) : blink,'blink');
  if (!vrm) {
    if (map.mouth) morphs.forEach(m=>m.mouth.forEach(i=>m.object.morphTargetInfluences[i]=0));
    if (map.blink) morphs.forEach(m=>m.blink.forEach(i=>m.object.morphTargetInfluences[i]=0));
    mapped('mouth',mouth,'aa'); mapped('blink',face ? (vrm && !map.blink ? 0 : Math.max(face.blinkLeft,face.blinkRight)) : blink,'blink');
  }
  if (snapshot.expression && (snapshot.expression!=='neutral' || map.neutral)) mapped(snapshot.expression,snapshot.expression==='neutral' ? 1 : .8,snapshot.expression);
  if (snapshot.expressionPreview) setTarget(snapshot.expressionPreview.target,snapshot.expressionPreview.intensity);
}
function gestureCatalog() {
  if (!model) return [];
  if (!vrm) return ['yes','no','celebrate'];
  const bone=name=>vrm.humanoid.getNormalizedBoneNode(name);
  return [...(bone('head') ? ['yes','no'] : []), ...(bone('rightUpperArm') ? ['wave'] : []), ...(bone('leftUpperArm') && bone('rightUpperArm') ? ['celebrate'] : [])];
}
window.studioExportFrame = (maxSide=640) => {
  if (!model) return null;
  renderer.render(scene,camera);
  const scale=Math.min(1,maxSide/Math.max(canvas.width,canvas.height));
  exportCanvas.width=Math.max(1,Math.round(canvas.width*scale)); exportCanvas.height=Math.max(1,Math.round(canvas.height*scale));
  exportCanvas.getContext('2d').drawImage(canvas,0,0,exportCanvas.width,exportCanvas.height);
  return exportCanvas.toDataURL('image/png');
};

controls.addEventListener('end',()=>{ if (!capture && model) command('camera',{position:camera.position.toArray(),target:controls.target.toArray()}); });
new ResizeObserver(() => {
  const w=stage.clientWidth,h=stage.clientHeight,previousAspect=camera.aspect;
  if (!w || !h) return;
  renderer.setSize(w,h,false); camera.aspect=w/Math.max(h,1); camera.updateProjectionMatrix();
  if (model && !snapshot.camera && Math.abs(previousAspect-camera.aspect)>.01) fitCamera();
}).observe(stage);
$('test').onclick=()=>command('test'); $('microphone').onclick=()=>command('microphone');
$('reset').onclick=async()=>{ if(await command('reset_camera')) { fitCamera(); toast('Enquadramento restaurado.'); } };
$('save-camera').onclick=async()=>{ if(await command('camera',{position:camera.position.toArray(),target:controls.target.toArray()})) toast('Enquadramento salvo e aplicado à captura OBS.'); };
document.querySelectorAll('[data-expression]').forEach(button => button.onclick=()=>command('expression',button.dataset.expression));
$('copy-obs').onclick=async()=>{ const url=new URL(location.href); url.search='?capture=1'; try{await navigator.clipboard.writeText(url.href);toast('URL copiada. Cole em uma Fonte de navegador no OBS.');}catch{toast('Use o botão Copiar URL para o OBS no painel do app.');} };
$('fullscreen').onclick=()=>{ if(document.fullscreenElement) document.exitFullscreen(); else stage.requestFullscreen(); };
canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();$('notice').textContent='Renderização interrompida. Use Recarregar prévia nas Configurações.';});
capabilities(); poll(); requestAnimationFrame(animate);
