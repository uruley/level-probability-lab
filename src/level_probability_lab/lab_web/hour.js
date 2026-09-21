'use strict';
const HourView=(()=>{
 function latest(state){return (state?.hour_forecasts||[]).reduce((a,b)=>!a||Date.parse(b.as_of)>=Date.parse(a.as_of)?b:a,null);}
 function rolloverSamples(state,enabled){
  const last=latest(state);
  return enabled&&last&&state.can_hour_forecast&&!state.done&&Date.parse(state.clock)>=Date.parse(last.end)?last.samples:null;
 }
 function advanceChunks(state,count,enabled){
  // Stepping minute-by-minute while a forecast is active avoids skipping its end.
  return enabled&&latest(state)&&count===5?[1,1,1,1,1]:[count];
 }
 let chart,actual,ghost;
 const price=v=>v==null?'—':'$'+v.toFixed(2);
 const label=t=>new Date(t).toLocaleTimeString('en-US',{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',hour12:false});
 function detail(state,f){
  if(!state||!document.getElementById('hourDetails').open)return;
  const L=window.LightweightCharts;
  if(!chart){chart=L.createChart(document.getElementById('hourChart'),{autoSize:true,layout:{background:{type:'solid',color:'#111923'},textColor:'#a9bac8'},grid:{vertLines:{color:'#1c2936'},horzLines:{color:'#1c2936'}},timeScale:{timeVisible:true,tickMarkFormatter:t=>label(t*1000)},localization:{timeFormatter:t=>label(t*1000)}});
   actual=chart.addSeries(L.CandlestickSeries,{upColor:'#84e3bc',downColor:'#e99599',borderVisible:false});
   ghost=chart.addSeries(L.CandlestickSeries,{upColor:'#edbd6e55',downColor:'#edbd6e55',wickUpColor:'#edbd6e',wickDownColor:'#edbd6e',borderUpColor:'#edbd6e',borderDownColor:'#edbd6e',priceLineVisible:false});}
  actual.setData(LabChart.candleData(LabChart.intraday(state,5)));
  ghost.setData(f?f.targets.map((t,i)=>({time:Date.parse(t)/1000,open:f.candles[i][0],high:f.candles[i][1],low:f.candles[i][2],close:f.candles[i][3]})):[]);
  chart.timeScale().fitContent();
 }
 function render(state,id){
  const $=id=>document.getElementById(id),picker=$('hourSelect'),forecasts=state.hour_forecasts||[];
  picker.replaceChildren();picker.add(new Option('Choose a forecast',''));
  for(const f of [...forecasts].reverse())picker.add(new Option(label(f.as_of)+' → '+label(f.end),f.id));
  picker.value=id;
  const f=forecasts.find(f=>f.id===id),values=$('hourValues');values.replaceChildren();
  if(!f){$('hourStatus').textContent=state.hour_reason||'Ready: 120 completed five-minute candles → next 12 candles. Uses Base and approximate dollar amount.';detail(state,null);return;}
  const o=f.outcome;
  $('hourStatus').textContent=label(f.as_of)+' → '+label(f.end)+' NY · '+(o.status==='complete'?'Complete':o.status==='incomplete'?'Missing minutes — final scores unavailable':o.observed_minutes+'/60 minutes revealed')+' · '+f.samples+' paths · '+f.range.valid_paths+' valid range paths · '+f.repairs+' display repairs';
  for(const [key,title,predicted] of [['high','Hour high',f.range.high?.median],['low','Hour low',f.range.low?.median],['close','Ending close',f.median_close]]){
   const box=document.createElement('span');box.append(title);const number=document.createElement('b');number.textContent=price(predicted);box.append(number);
   const text=document.createElement('small');text.textContent='Actual'+(o.status==='pending'&&key!=='close'?' so far':'')+': '+price(o.actual[key])+' · Error: '+price(o.errors[key]);box.append(text);values.append(box);
  }
  const baseline=document.createElement('span');baseline.textContent='Flat-price close error: '+price(o.flat_close_error)+' · Ending close sample spread: '+price(f.close_p10)+'–'+price(f.close_p90);values.append(baseline);
  detail(state,f);
 }
 return {render,detail,rolloverSamples,advanceChunks};
})();
if(typeof module!=='undefined')module.exports=HourView;
