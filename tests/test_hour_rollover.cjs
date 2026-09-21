const assert=require('node:assert/strict');
const hour=require('../src/level_probability_lab/lab_web/hour.js');
const first={as_of:'2026-08-14T15:30Z',end:'2026-08-14T16:30Z',samples:25};
const state={clock:'2026-08-14T16:29Z',can_hour_forecast:true,done:false,hour_forecasts:[first]};
assert.equal(hour.rolloverSamples(state,true),null);
state.clock=first.end;
assert.equal(hour.rolloverSamples(state,true),25);
assert.equal(hour.rolloverSamples(state,false),null);
assert.equal(hour.rolloverSamples({...state,hour_forecasts:[]},true),null);
assert.equal(hour.rolloverSamples({...state,can_hour_forecast:false},true),null);
assert.equal(hour.rolloverSamples({...state,done:true},true),null);
const next={as_of:first.end,end:'2026-08-14T17:30Z',samples:25};
assert.equal(hour.rolloverSamples({...state,hour_forecasts:[next,first]},true),null);
assert.deepEqual(hour.advanceChunks(state,5,true),[1,1,1,1,1]);
assert.deepEqual(hour.advanceChunks(state,5,false),[5]);
assert.deepEqual(hour.advanceChunks({...state,hour_forecasts:[]},5,true),[5]);
assert.deepEqual(hour.advanceChunks(state,1,true),[1]);
console.log('Hourly rollover: deadline, duplicate prevention, opt-out, session close, and five-step boundary checks pass.');

// Exercise the real playback orchestration with an isolated fake API and clock.
const vm=require('node:vm'),fs=require('node:fs');
const elements=new Map();
const context=vm.createContext({HourView:hour,console,setTimeout,clearTimeout,
 document:{getElementById:id=>{if(!elements.has(id))elements.set(id,{checked:id==='autoHour',value:'25',classList:{toggle(){}},disabled:false});return elements.get(id)},querySelectorAll:()=>[],addEventListener(){}},
 ResizeObserver:class{observe(){}},fetch:()=>new Promise(()=>{})});
vm.runInContext(fs.readFileSync(require.resolve('../src/level_probability_lab/lab_web/app.js'),'utf8'),context);
(async()=>{
 const result=await vm.runInContext(`(async()=>{
  render=()=>{};controls=()=>{};message=()=>{};
  state={clock:'2026-08-14T16:29:00Z',done:false,can_forecast:true,can_hour_forecast:false,hour_forecasts:[{id:'old',as_of:'2026-08-14T15:30:00Z',end:'2026-08-14T16:30:00Z',samples:25}]};
  sessionId='test';const calls=[];
  api=async(path,body)=>{
   calls.push({path,clock:state.clock});
   if(path==='step'){const clock=new Date(Date.parse(state.clock)+body.count*60000).toISOString();return {...state,clock,can_hour_forecast:new Date(clock).getUTCMinutes()%5===0};}
   const next={id:'next',as_of:state.clock,end:new Date(Date.parse(state.clock)+3600000).toISOString(),samples:body.samples};
   return {...state,hour_forecast_id:'next',hour_forecasts:[...state.hour_forecasts,next]};
  };
  await advance(5);return {calls,state,selectedHour};
 })()`,context);
 const forecasts=result.calls.filter(x=>x.path==='hour-forecast');
 assert.equal(forecasts.length,1);assert.equal(forecasts[0].clock,'2026-08-14T16:30:00.000Z');
 assert.equal(result.state.clock,'2026-08-14T16:34:00.000Z');
 assert.equal(result.state.hour_forecasts.length,2);assert.equal(result.state.hour_forecasts[0].id,'old');
 assert.equal(result.selectedHour,'next');
 console.log('Playback integration: Reveal +5 rolls over exactly at expiry once, retains the old forecast, and selects the next.');
})().catch(e=>{console.error(e);process.exitCode=1});
