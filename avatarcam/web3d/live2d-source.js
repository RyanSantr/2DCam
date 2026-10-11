import * as PIXI from 'pixi.js';
import { Live2DModel, MotionPreloadStrategy } from 'pixi-live2d-display/cubism4';
window.PIXI = PIXI;
const bridge = await new Promise(resolve=>new QWebChannel(qt.webChannelTransport,c=>resolve(c.objects.studio)));
const canvas=document.getElementById('canvas'), notice=document.getElementById('notice');
const app=new PIXI.Application({view:canvas,transparent:true,antialias:true,autoStart:false,resolution:1});
Live2DModel.registerTicker(PIXI.Ticker);
let state={},model=null,url=null,busy=false,serial=0,last=0,frames=0,stats=performance.now(),error='';
const exportCanvas=document.createElement('canvas');
function fit() {
  const w=innerWidth,h=innerHeight; app.renderer.resize(w,h);
  if (!model) return;
  const base=model.internalModel.width, height=model.internalModel.height;
  model.scale.set(Math.min(w*.75/base,h*.9/height)*(state.camera?.position?.[2] || 1));
  model.anchor.set(.5,.5); model.position.set(w*(state.camera?.target?.[0] ?? .5),h*(state.camera?.target?.[1] ?? .52));
}
async function load(next) {
  const id=++serial;url=next;error='';
  if (model) { app.stage.removeChild(model); model.destroy({children:true,texture:true,baseTexture:true}); model=null; }
  if (!next) return;
  try {
    const loaded=await Live2DModel.from(next,{autoUpdate:false,autoInteract:false,motionPreload:MotionPreloadStrategy.NONE});
    if (id!==serial) { loaded.destroy({children:true,texture:true,baseTexture:true}); return; }
    model=loaded; app.stage.addChild(model);fit();notice.textContent='';
    model.internalModel.on('beforeModelUpdate',()=>{
      const core=model.internalModel.coreModel,face=state.face?.detected ? state.face : {};
      core.setParameterValueById('ParamAngleX',-(face.yaw || 0)*57.3);
      core.setParameterValueById('ParamAngleY',-(face.pitch || 0)*57.3);
      core.setParameterValueById('ParamAngleZ',-(face.roll || 0)*57.3);
      core.setParameterValueById('ParamEyeBallX',face.gazeX || 0); core.setParameterValueById('ParamEyeBallY',face.gazeY || 0);
      core.setParameterValueById('ParamMouthOpenY',Math.max(face.jaw || 0,state.speaking ? Math.min(1,state.level*2.8) : 0));
      if (face.detected) { core.setParameterValueById('ParamEyeLOpen',1-face.blinkLeft);core.setParameterValueById('ParamEyeROpen',1-face.blinkRight); }
      const gesture=state.gesture,p=gesture?.progress || 0,e=Math.sin(p*Math.PI);
      if (gesture?.name==='yes') core.addParameterValueById('ParamAngleY',Math.sin(p*Math.PI*6)*15*e);
      if (gesture?.name==='no') core.addParameterValueById('ParamAngleX',Math.sin(p*Math.PI*6)*15*e);
      for (const [action,item] of Object.entries(state.expressionMapping || {})) {
        const value=action==='mouth' ? Math.max(face.jaw || 0,state.speaking ? state.level*2.8 : 0) : action==='blink' ? Math.max(face.blinkLeft || 0,face.blinkRight || 0) : action===state.expression ? 1 : 0;
        core.setParameterValueById(item.target,Math.min(1,value)*item.intensity);
      }
      if (state.expressionPreview) core.setParameterValueById(state.expressionPreview.target,state.expressionPreview.intensity);
    });
  } catch(exc) { error=exc.message;notice.textContent='Não foi possível abrir o Live2D: '+error; }
}
async function poll() {
  if (!busy) {
    busy=true;
    try {const next=JSON.parse(await new Promise(r=>bridge.state(r)));const oldCamera=JSON.stringify(state.camera);state=next;
      document.body.style.background=state.capture ? state.background : '#1a1c20';
      if (state.model!==url) load(state.model);
      if (JSON.stringify(state.camera)!==oldCamera) fit();
    } finally {busy=false;}
  }
  setTimeout(poll,state.active===false ? 250 : 50);
}
function animate(now) {
  setTimeout(()=>requestAnimationFrame(animate),state.active===false || document.hidden ? 250 : Math.max(0,1000/(state.paused ? 5 : state.fps || 30)-12));
  if (state.active===false || document.hidden) {last=now;return;}
  const delta=Math.min(100,now-last);last=now;
  if (model && !state.paused) model.update(delta);
  app.renderer.render(app.stage);frames++;
  if (now-stats>1000) {
    const core=model?.internalModel.coreModel,ids=core?._parameterIds || [];
    const report={fps:Math.round(frames*1000/(now-stats)),loaded:Boolean(model),error,expressions:Object.keys(state.expressionMapping || {}),expressionCatalog:ids.slice(0,256),gestures:model?['yes','no']:[],hasMouth:ids.includes('ParamMouthOpenY'),capture:state.capture,width:canvas.width,height:canvas.height};
    window.studioDiagnostics=report;bridge.report(JSON.stringify(report));frames=0;stats=now;
  }
}
let drag=null;
canvas.onpointerdown=e=>{if(!state.capture) {drag=[e.clientX,e.clientY,model?.x || 0,model?.y || 0];canvas.setPointerCapture(e.pointerId);}};
canvas.onpointermove=e=>{if(drag&&model)model.position.set(drag[2]+e.clientX-drag[0],drag[3]+e.clientY-drag[1]);};
function saveCamera(){if(model)bridge.command('camera',JSON.stringify({position:[0,0,model.scale.x/Math.min(innerWidth*.75/model.internalModel.width,innerHeight*.9/model.internalModel.height)],target:[model.x/innerWidth,model.y/innerHeight,0]}),()=>{});}
canvas.onpointerup=()=>{if(drag)saveCamera();drag=null;};
canvas.onwheel=e=>{if(model&&!state.capture){e.preventDefault();model.scale.set(Math.max(.01,model.scale.x*(e.deltaY<0?1.06:.94)));saveCamera();}};
window.studioSaveCamera=saveCamera;
window.studioExportFrame=(maxSide=640)=>{if(!model)return null;app.renderer.render(app.stage);const scale=Math.min(1,maxSide/Math.max(canvas.width,canvas.height));exportCanvas.width=Math.round(canvas.width*scale);exportCanvas.height=Math.round(canvas.height*scale);exportCanvas.getContext('2d').drawImage(canvas,0,0,exportCanvas.width,exportCanvas.height);return exportCanvas.toDataURL('image/png');};
addEventListener('resize',fit);fit();poll();requestAnimationFrame(animate);
