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
 let chart,actual,ghost,actualLine,formingSeries,liveBar=null;const traces=new Map();let traceScene='';
 const price=v=>v==null?'—':'$'+v.toFixed(2);
 const label=t=>new Date(t).toLocaleTimeString('en-US',{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',hour12:false});
 function detail(state,f,reset=false){
  if(!state||!document.getElementById('hourDetails').open)return;
  const L=window.LightweightCharts;
  if(!chart){chart=L.createChart(document.getElementById('hourChart'),{autoSize:true,layout:{background:{type:'solid',color:'#111923'},textColor:'#a9bac8'},grid:{vertLines:{color:'#1c2936'},horzLines:{color:'#1c2936'}},timeScale:{timeVisible:true,tickMarkFormatter:t=>label(t*1000)},localization:{timeFormatter:t=>label(t*1000)}});
   actual=chart.addSeries(L.CandlestickSeries,{upColor:'#84e3bc',downColor:'#e99599',borderVisible:false});
   ghost=chart.addSeries(L.CandlestickSeries,{upColor:'#a8caff66',downColor:'#a8caff66',wickUpColor:'#a8caff',wickDownColor:'#a8caff',borderUpColor:'#a8caff',borderDownColor:'#a8caff',priceLineVisible:false});}
  if(state.mode!=='live'||traceScene!==state.symbol+'|'+state.date)stream(null);
  else if(liveBar&&liveBar.time!==Math.floor(Date.now()/60000)*60)stream(null);
  const sceneKey=state.symbol+'|'+state.date;
  if(traceScene!==sceneKey){for(const line of traces.values())chart.removeSeries(line);traces.clear();traceScene=sceneKey;}
  if(!actualLine)actualLine=chart.addSeries(L.LineSeries,{color:'#84e3bc',lineWidth:2,priceLineVisible:false,lastValueVisible:false});
  actualLine.setData(LabChart.candleData(LabChart.intraday(state,1)).map(b=>b.close==null?{time:b.time}:{time:b.time,value:b.close}));
  const ids=new Set((state.hour_forecasts||[]).map(f=>f.id));
  for(const [id,line] of traces){if(!ids.has(id)){chart.removeSeries(line);traces.delete(id);}}
  for(const forecast of state.hour_forecasts||[]){
   if(!traces.has(forecast.id))traces.set(forecast.id,chart.addSeries(L.LineSeries,{color:'#a8caff77',lineWidth:1,priceLineVisible:false,lastValueVisible:false}));
   traces.get(forecast.id).setData(forecast.targets.map((t,i)=>({time:Date.parse(t)/1000,value:forecast.candles[i][3]})));
  }
  actual.setData(LabChart.candleData(LabChart.intraday(state,1)));
  ghost.setData(f?f.targets.map((t,i)=>({time:Date.parse(t)/1000,open:f.candles[i][0],high:f.candles[i][1],low:f.candles[i][2],close:f.candles[i][3]})).filter(b=>b.time>=Date.parse(state.clock)/1000):[]);
  const key=(state.symbol||'QQQ')+'|'+state.date+'|'+(f?.id||'')+'|'+(LabChart.intraday(state,1).length>0);
  if(reset||chart._scene!==key){chart.priceScale('right').applyOptions({autoScale:true});
   const clock=Date.parse(state.clock)/1000;
   chart.timeScale().setVisibleRange({from:clock-60*60,to:Math.max(clock,f?Date.parse(f.end)/1000:clock)});chart._scene=key;}
 }
 function render(state,id){
  const $=id=>document.getElementById(id),picker=$('hourSelect'),forecasts=state.hour_forecasts||[];
  picker.replaceChildren();picker.add(new Option('Choose a forecast',''));
  for(const f of [...forecasts].reverse())picker.add(new Option(label(f.as_of)+' → '+label(f.end),f.id));
  picker.value=id;
  const f=forecasts.find(f=>f.id===id),values=$('hourValues');values.replaceChildren();
  if(!f){$('hourStatus').textContent=state.hour_reason||'Ready: completed one-minute inputs produce 50 forecast candles. Uses Base and approximate dollar amount.';detail(state,null);return;}
  const o=f.outcome;
  $('hourStatus').textContent=label(f.as_of)+' → '+label(f.end)+' NY · '+(o.status==='complete'?'Complete':o.status==='incomplete'?'Missing minutes — final scores unavailable':o.observed_minutes+'/50 minutes revealed')+' · '+f.samples+' paths · '+f.range.valid_paths+' valid range paths · '+f.repairs+' display repairs';
  for(const [key,title,predicted] of [['high','50-minute high',f.range.high?.median],['low','50-minute low',f.range.low?.median],['close','Ending close',f.median_close]]){
   const box=document.createElement('span');box.append(title);const number=document.createElement('b');number.textContent=price(predicted);box.append(number);
   const text=document.createElement('small');text.textContent='Actual'+(o.status==='pending'&&key!=='close'?' so far':'')+': '+price(o.actual[key])+' · Error: '+price(o.errors[key]);box.append(text);values.append(box);
  }
  const baseline=document.createElement('span');baseline.textContent='Flat-price close error: '+price(o.flat_close_error)+' · Ending close sample spread: '+price(f.close_p10)+'–'+price(f.close_p90);values.append(baseline);
  detail(state,f);
 }
 function stream(bar){
  liveBar=bar;if(!chart||(!bar&&!formingSeries))return;
  if(!formingSeries)formingSeries=chart.addSeries(window.LightweightCharts.CandlestickSeries,{upColor:'#52d9ee',downColor:'#52d9ee',wickUpColor:'#52d9ee',wickDownColor:'#52d9ee',borderVisible:false,title:'LIVE PRICE',priceLineVisible:true,priceLineColor:'#52eaff',priceLineWidth:2,priceLineStyle:0});
  formingSeries.setData(bar?[bar]:[]);
 }
 return {render,detail,rolloverSamples,advanceChunks,stream,latest};
})();
if(typeof module!=='undefined')module.exports=HourView;
