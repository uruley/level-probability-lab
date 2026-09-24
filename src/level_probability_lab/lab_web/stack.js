'use strict';
const StackView=(()=>{
 let chart,actual,ghost,data,selection='',scene='',pending=false,lastRequest='',attempt='';
 const $=id=>document.getElementById(id);
 const label=t=>new Date(t).toLocaleString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
 function paint(){
  if(!data)return;
  if(!chart){const L=window.LightweightCharts;chart=L.createChart($('stackHourChart'),{autoSize:true,layout:{background:{type:'solid',color:'#111923'},textColor:'#a9bac8'},grid:{vertLines:{color:'#1c2936'},horzLines:{color:'#1c2936'}},timeScale:{timeVisible:true},localization:{timeFormatter:t=>label(t*1000)}});actual=chart.addSeries(L.CandlestickSeries,{upColor:'#84e3bc',downColor:'#e99599',borderVisible:false});ghost=chart.addSeries(L.CandlestickSeries,{upColor:'#edbd6e66',downColor:'#edbd6e66',wickUpColor:'#edbd6e',wickDownColor:'#edbd6e',borderVisible:false});}
  actual.setData(data.bars);
  $('stackHourPredict').disabled=!!data.reason;
  const f=data.forecasts.find(f=>f.id===selection)||data.forecasts.at(-1);
  selection=f?.id||'';const picker=$('stackHourSelect');picker.replaceChildren();
  for(const row of [...data.forecasts].reverse())picker.add(new Option(label(row.as_of),row.id));picker.value=selection;
  ghost.setData(f?f.targets.map((t,i)=>({time:Date.parse(t)/1000,open:f.candles[i][0],high:f.candles[i][1],low:f.candles[i][2],close:f.candles[i][3]})):[]);
  $('stackHourStatus').textContent=data.symbol+' · '+(data.reason||'Using last completed hour: '+label(data.forecast_origin)+' Eastern.')+(f?' Selected forecast: '+label(f.as_of)+' Eastern · '+f.repairs+' display repairs.':'');
  $('stackHourScores').textContent=f?f.outcomes.map((o,i)=>label(f.targets[i])+' — '+o.status+(o.error!=null?' · close error $'+o.error.toFixed(3):'')).join(' | '):'No hourly forecast yet.';
  const viewKey=data.symbol+'|'+(f?.id||'');
  if(scene!==viewKey){chart.priceScale('right').applyOptions({autoScale:true});chart.timeScale().fitContent();scene=viewKey;}
 }
 async function refresh(sid,state,api,predict=false){
  const key=sid+'|'+state.clock;
  if(pending||(!predict&&key===lastRequest))return;
  pending=true;lastRequest=key;
  try{
   let result=await api('hourly-bars',{session_id:sid,predict,samples:25});
   if(!predict&&!result.reason&&$('stackAuto').checked&&attempt!==sid+'|'+result.forecast_origin&&!(state.mode==='live'&&!state.live_info?.ready)){
    const originKey=sid+'|'+result.forecast_origin;selection='';result=await api('hourly-bars',{session_id:sid,predict:true,samples:25});attempt=originKey;
   }
   if(sid!==sessionId)return;
   data=result;if(predict)selection='';paint();
  }catch(e){$('stackHourStatus').textContent=e.message;}finally{pending=false;}
 }
 function select(){selection=$('stackHourSelect').value;paint();}
 return {refresh,select};
})();
