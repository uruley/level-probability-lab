const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const series=[];const chart={addSeries(type){const s={type,data:[],setData(d){this.data=d}};series.push(s);return s},removeSeries(s){series.splice(series.indexOf(s),1)},priceScale(){return {applyOptions(){}}},timeScale(){return {setVisibleRange(r){assert.ok(Number.isFinite(r.from)&&Number.isFinite(r.to));chart.range=r;}}}};
const ctx=vm.createContext({module:{exports:{}},document:{getElementById(){return {open:true}}},window:{LightweightCharts:{createChart(){return chart},CandlestickSeries:'candle',LineSeries:'line'}},LabChart:{intraday(s){return s.bars},candleData(b){return b}}});
vm.runInContext(fs.readFileSync('src/level_probability_lab/lab_web/hour.js','utf8'),ctx);
const view=ctx.module.exports;const start=Date.parse('2026-08-14T14:00Z');
const f={id:'frozen',end:new Date(start+50*60000).toISOString(),targets:Array.from({length:50},(_,i)=>new Date(start+i*60000).toISOString()),candles:Array.from({length:50},()=>[100,102,99,101])};
const state={symbol:'QQQ',date:'2026-08-14',clock:new Date(start).toISOString(),bars:[],hour_forecasts:[f]};
view.detail(state,f);assert.equal(series[1].data.length,50);const trace=series[3];const original=JSON.stringify(trace.data);
state.clock=new Date(start+50*60000).toISOString();state.bars=[{time:start/1000,open:100,high:101,low:99,close:100.5}];view.detail(state,f);
assert.equal(series[1].data.length,0);assert.equal(JSON.stringify(trace.data),original);assert.equal(series[2].data[0].value,100.5);
console.log('Expired ghosts disappear; frozen prediction trace and actual-close line remain.');

const frozen=JSON.stringify(trace.data);
view.stream({time:start/1000+900,open:100,high:102,low:99,close:101});
assert.equal(series.at(-1).data[0].close,101);
view.stream(null);assert.equal(series.at(-1).data.length,0);
assert.equal(JSON.stringify(trace.data),frozen);
console.log('Live partial candle clears independently without changing saved predictions.');
