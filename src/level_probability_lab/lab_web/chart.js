/* Read-only chart transformations; no changes to forecasts or replay time. */
'use strict';
const LabChart = (()=>{
 const periods=[5,10,20,50,100,200];
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 const stamp=t=>Date.parse(t);
 const fmt=(t,daily=false)=>new Date(t).toLocaleString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',...(daily?{}:{hour:'2-digit',minute:'2-digit',hour12:false})});
 function indicators(bars){
  return bars.map((b,i)=>{
   const result={...b};
   for(const n of periods){const values=bars.slice(Math.max(0,i-n+1),i+1).map(x=>x.c);result['sma'+n]=values.length===n&&values.every(finite)?values.reduce((a,v)=>a+v,0)/n:null;}
   const values=bars.slice(Math.max(0,i-19),i+1).map(x=>x.c),mean=result.sma20;
   const sd=finite(mean)?Math.sqrt(values.reduce((a,v)=>a+(v-mean)**2,0)/20):null;
   result.bbUpper=finite(sd)?mean+2*sd:null;result.bbLower=finite(sd)?mean-2*sd:null;
   return result;
  });
 }
 function intraday(state,minutes){
  const start=stamp(state.session_open||state.bars[0].t),clock=stamp(state.clock),step=minutes*60000;
  const byTime=new Map(state.bars.map(b=>[stamp(b.t),b]));const bars=[];
  for(let t=start;t+step<=clock;t+=step){
   const parts=[];for(let j=0;j<minutes;j++)parts.push(byTime.get(t+j*60000));
   const complete=parts.every(b=>b&&[b.o,b.h,b.l,b.c].every(finite));
   bars.push({t:new Date(t).toISOString(),end:new Date(t+step).toISOString(),
    o:complete?parts[0].o:null,h:complete?Math.max(...parts.map(b=>b.h)):null,
    l:complete?Math.min(...parts.map(b=>b.l)):null,c:complete?parts.at(-1).c:null,
    v:complete?parts.reduce((a,b)=>a+b.v,0):null});
  }
  return indicators(bars);
 }
 function series(state,timeframe){
  return timeframe==='1'||timeframe==='5'?intraday(state,Number(timeframe)):(state.chart_history?.[timeframe]||[]);
 }
 function asOf(source, bars, key){
  let j=-1;return bars.map(b=>{while(j+1<source.length&&stamp(source[j+1].end)<=stamp(b.end))j++;
   return j>=0&&finite(source[j][key])?source[j][key]:null;});
 }

 let chart=null,actual=null,ghost=null,volume=null,lastKey='',lastCount=0,lastState=null,lastForecast=null,lastHour=null,hourBand=null,hourEnd=null;
 const overlays=new Map();
 const unix=t=>Math.floor(stamp(t)/1000);
 function candleData(bars){return bars.map(b=>[b.o,b.h,b.l,b.c].every(finite)?
  {time:unix(b.t),open:b.o,high:b.h,low:b.l,close:b.c}:{time:unix(b.t)});}
 function create(){
  const $=id=>document.getElementById(id),L=window.LightweightCharts;
  chart=L.createChart($('chart'),{autoSize:true,
   layout:{background:{type:'solid',color:'#111923'},textColor:'#a9bac8',attributionLogo:true},
   grid:{vertLines:{color:'#1c2936'},horzLines:{color:'#1c2936'}},
   crosshair:{mode:L.CrosshairMode.Normal},
   rightPriceScale:{borderColor:'#324252',scaleMargins:{top:.08,bottom:.2}},
   timeScale:{timeVisible:true,secondsVisible:false,rightOffset:7,borderColor:'#324252',
    tickMarkFormatter:t=>new Date(t*1000).toLocaleString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false})},
   localization:{timeFormatter:t=>fmt(t*1000)},
   handleScroll:{mouseWheel:true,pressedMouseMove:true,horzTouchDrag:true,vertTouchDrag:true},
   handleScale:{mouseWheel:true,pinch:true,axisPressedMouseMove:{time:true,price:true},axisDoubleClickReset:{time:true,price:true}}});
  actual=chart.addSeries(L.CandlestickSeries,{upColor:'#84e3bc',downColor:'#e99599',wickUpColor:'#84e3bc',wickDownColor:'#e99599',borderVisible:false});
  ghost=chart.addSeries(L.CandlestickSeries,{upColor:'#96b4ff55',downColor:'#96b4ff55',wickUpColor:'#96b4ff',wickDownColor:'#96b4ff',borderUpColor:'#96b4ff',borderDownColor:'#96b4ff',priceLineVisible:false,lastValueVisible:false});
  volume=chart.addSeries(L.HistogramSeries,{priceScaleId:'volume',priceFormat:{type:'volume'},priceLineVisible:false,lastValueVisible:false});
  volume.priceScale().applyOptions({scaleMargins:{top:.85,bottom:0}});
  chart.subscribeCrosshairMove(p=>{
   const tip=$('tooltip'),b=p.seriesData.get(actual);
   if(!p.point||!p.time||!b||!finite(b.close)){tip.hidden=true;return;}
   tip.hidden=false;tip.textContent=fmt(Number(p.time)*1000)+' NY'+`\nO ${b.open.toFixed(2)}  H ${b.high.toFixed(2)}\nL ${b.low.toFixed(2)}  C ${b.close.toFixed(2)}`;
   tip.style.left=Math.max(0,Math.min(p.point.x+12,$('chart').clientWidth-230))+'px';tip.style.top='40px';
  });
  chart.timeScale().subscribeVisibleLogicalRangeChange(r=>{if(r)$('chartViewport').textContent=Math.round(r.to-r.from)+' visible slots';});
  $('chart').addEventListener('wheel',()=>{$('chartFollow').checked=false;},{passive:true});
  let down=null;
  $('chart').addEventListener('pointerdown',e=>{down=[e.clientX,e.clientY];});
  $('chart').addEventListener('pointermove',e=>{if(down&&Math.abs(e.clientX-down[0])+Math.abs(e.clientY-down[1])>4)$('chartFollow').checked=false;});
  window.addEventListener('pointerup',()=>{down=null;});
  $('chart').addEventListener('keydown',e=>{if(e.key==='+'||e.key==='='){e.preventDefault();zoom(.75);}if(e.key==='-'){e.preventDefault();zoom(1.33);}});
  $('chartZoomIn').onclick=()=>zoom(.75);$('chartZoomOut').onclick=()=>zoom(1.33);
  $('chartReset').onclick=()=>{lastKey='';$('chartFollow').checked=true;chart.priceScale('right').applyOptions({autoScale:true});draw(lastState,lastForecast,lastHour);};
  $('chartFollow').onchange=()=>{if($('chartFollow').checked){chart.timeScale().scrollToRealTime();}};
 }
 function zoom(factor){if(!chart)return;const r=chart.timeScale().getVisibleLogicalRange();if(!r)return;document.getElementById('chartFollow').checked=false;const mid=(r.from+r.to)/2,half=Math.max(2,(r.to-r.from)*factor/2);chart.timeScale().setVisibleLogicalRange({from:mid-half,to:mid+half});}
 function draw(state,forecast,hour){
  if(!state)return;
  const $=id=>document.getElementById(id),L=window.LightweightCharts;
  if(!L){$('chartNotice').textContent='Chart library could not load. Refresh the page; saved forecasts are unaffected.';return;}
  lastState=state;lastForecast=forecast;lastHour=hour;if(!chart)create();
  if(formingSeries)formingSeries.setData([]);
  const timeframe=$('chartTimeframe').value,count=Number($('chartCount').value),bars=series(state,timeframe);
  const key=(state.symbol||'QQQ')+'|'+state.provider+'|'+state.date+'|'+timeframe,reset=key!==lastKey||count!==lastCount;
  const range=chart.timeScale().getVisibleLogicalRange();
  chart.applyOptions({timeScale:{timeVisible:timeframe!=='daily',tickMarkFormatter:t=>timeframe==='daily'?fmt(t*1000,true):new Date(t*1000).toLocaleString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false})}});
  actual.setData(candleData(bars));volume.setData(bars.map(b=>finite(b.v)&&finite(b.c)?{time:unix(b.t),value:b.v,color:b.c>=b.o?'#84e3bc60':'#e9959960'}:{time:unix(b.t)}));
  const fc=timeframe==='1'&&forecast?forecast.targets.map((t,i)=>({t,o:forecast.candles[i][0],h:forecast.candles[i][1],l:forecast.candles[i][2],c:forecast.candles[i][3],lo:forecast.low[i],hi:forecast.high[i]})):[];
  const showHour=timeframe==='1'&&document.getElementById('showHour')?.checked&&hour;
  const hourGrid=showHour?Array.from({length:61},(_,i)=>({time:unix(hour.as_of)+i*60})):[];
  const ghostMap=new Map(hourGrid.map(b=>[b.time,b]));for(const b of candleData(fc))ghostMap.set(b.time,b);
  ghost.setData([...ghostMap.values()].sort((a,b)=>a.time-b.time));
  if(!hourBand){hourBand=chart.addSeries(L.BaselineSeries,{baseValue:{type:'price',price:0},topLineColor:'#edbd6e',topFillColor1:'#edbd6e22',topFillColor2:'#edbd6e22',bottomLineColor:'transparent',bottomFillColor1:'transparent',bottomFillColor2:'transparent',priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false});
   hourEnd=chart.addSeries(L.LineSeries,{color:'#ffd391',lineVisible:false,pointMarkersVisible:true,pointMarkersRadius:5,priceLineVisible:false,lastValueVisible:true,title:'1h close'});}
  const hr=hour?.range;
  if(showHour&&hr?.high&&hr?.low){hourBand.applyOptions({baseValue:{type:'price',price:hr.low.median}});hourBand.setData([{time:unix(hour.as_of),value:hr.high.median},{time:unix(hour.end),value:hr.high.median}]);}else hourBand.setData([]);
  hourEnd.setData(showHour?[{time:unix(hour.end),value:hour.median_close}]:[]);
  const legend=$('indicatorLegend');legend.replaceChildren();const used=new Set();
  const fit=$('fitIndicators').checked;
  function line(id,data,color,dashed=false,includeScale=fit){
   used.add(id);let item=overlays.get(id);
   const options={color,lineWidth:1,lineType:L.LineType.WithSteps,lineStyle:dashed?L.LineStyle.Dashed:L.LineStyle.Solid,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false,autoscaleInfoProvider:base=>includeScale?base():null};
   if(!item){item=chart.addSeries(L.LineSeries,options);overlays.set(id,item);}else item.applyOptions(options);
   item.setData(data);return item;
  }
  const chosen=[...document.querySelectorAll('[data-ma]:checked')].map(el=>Number(el.dataset.ma));
  if(showHour&&hr?.low)line('hour-low',[{time:unix(hour.as_of),value:hr.low.median},{time:unix(hour.end),value:hr.low.median}],'#edbd6e',false,true);
  const selection=$('indicatorFrame').value,frames=selection==='both'?['hourly','daily']:[selection==='chart'?timeframe:selection];
  const colors=['#f5c06c','#76cde5','#b9a1ff','#e7a4c3','#a6d779','#f19877'];
  for(const frame of frames){
   const source=frame===timeframe?bars:series(state,frame),label=frame==='1'?'1m':frame==='5'?'5m':frame==='hourly'?'1h':'1d';
   const keys=chosen.map(n=>['sma'+n,'SMA '+n,colors[periods.indexOf(n)]]);
   if($('indicatorBands').checked){keys.push(['bbUpper','BB upper','#83b6f5'],['bbLower','BB lower','#83b6f5']);if(!chosen.includes(20))keys.push(['sma20','BB middle','#8398b0']);}
   for(const [field,name,color] of keys){
    const values=asOf(source,bars,field);line(frame+field,bars.map((b,i)=>finite(values[i])?{time:unix(b.t),value:values[i]}:{time:unix(b.t)}),color,frame==='daily');
    const chip=document.createElement('span');chip.className='indicator-chip';chip.style.borderColor=color;chip.style.color=color;
    chip.textContent=label+' '+name+(finite(values.at(-1))?' $'+values.at(-1).toFixed(2):' unavailable');legend.append(chip);
   }
  }
  for(const [field,color] of [['lo','#7895d5'],['hi','#7895d5']])if(fc.length)line('forecast-'+field,fc.map(b=>({time:unix(b.t),value:b[field]})),color,true,true);
  if($('frozenLevels').checked&&forecast?.market_context&&bars.length){
   for(const v of forecast.market_context.levels){
    if(!finite(v.value)||!frames.includes(v.timeframe)||!(v.name.startsWith('SMA ')&&chosen.includes(Number(v.name.slice(4)))||$('indicatorBands').checked&&v.name.startsWith('BB ')))continue;
    const times=[bars[0].t,bars.at(-1).t];line('frozen-'+v.timeframe+v.name,[...new Set(times)].map(t=>({time:unix(t),value:v.value})),'#d4a5ff',true);
   }
  }
  for(const [id,item] of overlays)if(!used.has(id)){chart.removeSeries(item);overlays.delete(id);}
  const times=new Set([...bars.map(b=>unix(b.t)),...fc.map(b=>unix(b.t)),...hourGrid.map(b=>b.time)]);
  if(times.size){
   if(reset){chart.priceScale('right').applyOptions({autoScale:true});chart.timeScale().setVisibleLogicalRange({from:Math.max(-.5,times.size-count),to:times.size+6});}
   else if(range){const width=range.to-range.from;chart.timeScale().setVisibleLogicalRange($('chartFollow').checked?{from:times.size+6-width,to:times.size+6}:range);}
  }
  lastKey=key;lastCount=count;
  const missing=bars.filter(b=>!finite(b.c)).length;
  $('chartNotice').textContent=`${bars.length} available completed ${timeframe==='hourly'?'hourly':timeframe==='daily'?'daily':timeframe+'-minute'} slots; ${missing} missing. `+(timeframe==='1'?'Blue forecast candles and dashed close bounds are predictions. ':'Forecast candles appear on the 1-minute view. ')+(timeframe==='daily'?'Today appears after session close. ':timeframe==='hourly'?'Full hours start at 9:30 NY; short closing block excluded. ':'')+'Pan through loaded history. Indicator values in the legend are the latest available; use Fit indicators if levels are outside the price view.';
 }
 let formingSeries=null;
 function stream(bar){
  if(!chart)return;
  if(!formingSeries)formingSeries=chart.addSeries(window.LightweightCharts.CandlestickSeries,{upColor:'#edbd6e',downColor:'#edbd6e',wickUpColor:'#edbd6e',wickDownColor:'#edbd6e',borderVisible:false,title:'Partial live',priceLineVisible:false});
  formingSeries.setData(bar?[bar]:[]);
 }
 return {draw,stream,indicators,intraday,asOf,series,candleData};
})();
if(typeof module!=='undefined')module.exports=LabChart;
