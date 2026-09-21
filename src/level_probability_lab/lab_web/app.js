'use strict';

const $ = id => document.getElementById(id);

let token='', sessionId='', state=null, selected='', busy=false, playing=false, timer=null, catalog=null;

let plotted=[];

let selectedHour='';

let liveTimer=null,liveRunning=false,liveLastForecast='',recordedDates=[];

function stopLive(){liveRunning=false;clearTimeout(liveTimer);liveTimer=null;controls();}

const money = v => v == null ? '—' : '$'+Number(v).toFixed(3);

const time = t => new Date(t).toLocaleTimeString('en-US',{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',hour12:false});

const dateLabel = d => new Date(d+'T12:00:00Z').toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric',timeZone:'America/New_York'});

function message(text,error=false){$('status').textContent=text;$('status').classList.toggle('error',error)}

async function api(path,body){const r=await fetch('/api/'+path,body?{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':token},body:JSON.stringify(body)}:{});const data=await r.json();if(!r.ok)throw new Error(data.error||'Request failed');return data}

function controls(){$('autoHour').disabled=busy;$('hourForecast').disabled=busy||!state||!state.can_hour_forecast;$('hourSelect').disabled=busy||!state;['load','date','lookback','model','amountMode','samples','reset'].forEach(id=>$(id).disabled=busy||!catalog);$('forecast').disabled=busy||!state||!state.can_forecast;['step','reveal'].forEach(id=>$(id).disabled=busy||!state||state.done);$('play').disabled=!state||state.done||(busy&&!playing);$('play').textContent=playing?'Ⅱ Pause':'▶ Play';$('samples').disabled=busy||$('model').value==='saved';$('auto').disabled=busy;$('sourceMode').disabled=busy;$('liveSymbol').disabled=busy;$('stopLive').hidden=!liveRunning;$('stopLive').disabled=busy;if(state?.mode==='live'){['play','step','reveal'].forEach(id=>$(id).disabled=true);if(!liveRunning){$('forecast').disabled=true;$('hourForecast').disabled=true;}}$('date').disabled=busy||$('sourceMode').value==='live';}

function pause(){playing=false;clearTimeout(timer);timer=null;controls()}

async function action(fn){if(busy)return;busy=true;controls();try{await fn()}catch(e){pause();message(e.message,true)}finally{busy=false;controls()}}

function accept(data){state=data;if(data.session_id)sessionId=data.session_id;if(data.hour_forecast_id)selectedHour=data.hour_forecast_id;if(data.forecast_id)selected=data.forecast_id;render()}

async function load(){pause();stopLive();if($('sourceMode').value==='live'){await startLive();return;}await action(async()=>{message('Loading the selected session from local history…');if(!($('sourceMode').value==='recorded'?recordedDates:catalog.dates).includes($('date').value))throw new Error('Choose an available trading session between '+catalog.dates[0]+' and '+catalog.dates.at(-1)+'.');const data=await api('session',{symbol:$('liveSymbol').value,date:$('date').value,lookback:Number($('lookback').value),recorded:$('sourceMode').value==='recorded'});sessionId=data.session_id;selected='';selectedHour='';accept(data);message(data.missing_minutes?`${data.missing_minutes} missing session minutes. Gaps stay visible; forecasts require contiguous input.`:'Replay starts with the 9:30 Eastern opening candle, completed at 9:31 (8:31 Central). Prior-session warmup is used when available. '+(data.can_forecast?'Ready to forecast.':data.reason));})}

async function forecast(){message($('model').value==='saved'?'Retrieving the frozen Small forecast…':'Generating five candles on the local GPU. First use also loads the model…');accept(await api('forecast',{session_id:sessionId,model:$('model').value,samples:Number($('samples').value),amount_mode:$('amountMode').value}));const f=state.forecasts.find(f=>f.id===selected);message(`${f.model} [${f.amount_mode==='trades'?'Actual trade totals':'Approximate amount'}] forecast frozen · ${f.samples} paths · ${f.cached?'saved result':f.seconds.toFixed(2)+'s inference'}. Reveal the next candles to compare.`)}

async function forecastHour(samples=Number($('samples').value)){

 message('Generating a one-hour outlook with Kronos Base…');

 accept(await api('hour-forecast',{session_id:sessionId,samples}));

 message('One-hour forecast saved. Earlier forecasts and their scores stay available.');

}

async function advance(count){await action(async()=>{

 if($('auto').checked&&state.can_forecast)await forecast();

 // Smaller steps preserve the exact rollover boundary even during Reveal +5.

 const chunks=HourView.advanceChunks(state,count,$('autoHour').checked);

 let rolled=false;

 for(const chunk of chunks){

  accept(await api('step',{session_id:sessionId,count:chunk}));

  const samples=HourView.rolloverSamples(state,$('autoHour').checked);

  if(samples!==null){await forecastHour(samples);rolled=true;}

 }

 message(state.done?'Session complete. Scores include only the forecasts you issued.':rolled?'Next one-hour forecast saved. Earlier forecasts and scores remain in the hour picker.':state.can_forecast?'Replay advanced. Earlier forecasts remain frozen.':state.reason);

});if(state?.done)pause()}



async function tick(){if(!playing)return;await advance(1);if(playing)timer=setTimeout(tick,Number($('speed').value))}

$('load').onclick=load;$('reset').onclick=load;$('step').onclick=()=>{pause();advance(1)};$('reveal').onclick=()=>{pause();advance(5)};$('forecast').onclick=()=>{pause();action(forecast)};

$('play').onclick=()=>{if(playing)pause();else{playing=true;controls();tick()}};

$('model').onchange=()=>{pause();$('engineStatus').textContent=$('model').value==='saved'?'Saved Small · 120-candle lookback · 50 paths':'Local GPU · loaded on first forecast';controls()};

$('forecastSelect').onchange=()=>{selected=$('forecastSelect').value;render()};

document.addEventListener('keydown',e=>{if(/INPUT|SELECT|BUTTON/.test(e.target.tagName))return;if(e.code==='Space'){e.preventDefault();if(!$('play').disabled)$('play').click()}if(e.code==='ArrowRight'&&!$('step').disabled)$('step').click()});

function render(){if(!state)return;$('chartSymbol').textContent=state.symbol||'QQQ';$('headerSymbol').textContent=(state.symbol||'QQQ')+' · 1 MINUTE';$('coverage').textContent=state.provider==='webull_official'?'Recorded Webull candles · '+state.date:catalog.dates.length.toLocaleString()+' archive sessions · '+catalog.dates[0]+' → '+catalog.dates.at(-1);$('sourceLabel').textContent=state.provider==='webull_official'?' '+(state.symbol||'QQQ')+' · Webull official':' Invesco QQQ · Nasdaq prints';if(state.mode==='live')$('feedStatus').textContent=state.live_info?.message||'Live feed';const last=state.bars.at(-1),first=state.bars[0];$('price').textContent='$'+last.c.toFixed(2);const change=(last.c/first.o-1)*100;$('change').textContent=(change>=0?'+':'')+change.toFixed(2)+'% session';$('change').style.color=change>=0?'var(--mint)':'var(--red)';$('clock').textContent=time(state.clock);$('clockDate').textContent=dateLabel(state.date);$('sessionLabel').textContent=dateLabel(state.date);$('progressFill').style.width=((state.cursor+1)/state.total*100)+'%';$('progressText').textContent=`${state.cursor+1} / ${state.total} candles`;$('mae').textContent=money(state.metrics.mae);$('baseline').textContent=money(state.metrics.baseline_mae);$('scored').textContent=state.metrics.scored;

const picker=$('forecastSelect');picker.replaceChildren();if(!state.forecasts.length){picker.add(new Option('No forecast yet',''));}else{for(const f of [...state.forecasts].reverse())picker.add(new Option(`${time(f.origin)} · ${f.model} [${f.amount_mode==='trades'?'Actual trade totals':'Approximate amount'}] · ${f.samples} paths`,f.id));if(!state.forecasts.some(f=>f.id===selected))selected=state.forecasts.at(-1).id;picker.value=selected}

const f=state.forecasts.find(f=>f.id===selected);$('latency').textContent=f?f.seconds.toFixed(2)+'s':'—';$('latencyNote').textContent=f?(f.cached?'Saved result · original inference time':'Local inference · '+f.samples+' paths'):'Local inference time';const rows=$('forecastRows');rows.replaceChildren();if(f){f.targets.forEach((t,i)=>{const tr=document.createElement('tr');const cells=[`+${i+1} minute`,time(t),money(f.median[i]),`${money(f.low[i])} – ${money(f.high[i])}`,f.actual[i]==null?(f.outcome_status?.[i]==='missing'?'Missing candle':'Not revealed'):money(f.actual[i]),money(f.errors[i])];for(const [j,v]of cells.entries()){const td=document.createElement('td');td.textContent=v;if(j===4&&f.actual[i]==null)td.className='pending';tr.append(td)}rows.append(tr)});$('forecastNote').textContent=`${f.model} [${f.amount_mode==='trades'?'Actual trade totals':'Approximate amount'}] · ${f.repairs} display candle repairs · range is sampled close dispersion`;}else{const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=6;td.className='empty-row';td.textContent='Generate a forecast, then reveal the next candles to compare.';tr.append(td);rows.append(tr);$('forecastNote').textContent='Every prediction uses completed candles only.'}

HourView.render(state,selectedHour);renderRange(f);renderTouches(f);renderContext(f);$('chartEmpty').hidden=true;controls();draw();}

function draw(){if(state)LabChart.draw(state,state.forecasts.find(f=>f.id===selected),state.hour_forecasts?.find(f=>f.id===selectedHour));}

new ResizeObserver(draw).observe($('chart'));

for(const id of ['chartTimeframe','chartCount','indicatorFrame','fitIndicators','indicatorBands','frozenLevels'])$(id).onchange=draw;

for(const input of document.querySelectorAll('[data-ma]'))input.onchange=draw;

$('chartExpand').onclick=()=>{const expanded=document.querySelector('.workspace').classList.toggle('chart-expanded');$('chartExpand').textContent=expanded?'Compact chart':'Expand chart';draw();};

(async()=>{try{catalog=await api('catalog');token=catalog.token;$('date').min=catalog.dates[0];$('date').max=catalog.dates.at(-1);$('coverage').textContent=`${catalog.dates.length.toLocaleString()} sessions · ${catalog.dates[0]} → ${catalog.dates.at(-1)}`;controls();await load()}catch(e){message(e.message,true);$('chartEmpty').textContent='Could not load local history.'}})();



function renderRange(f){

 const rows=$('rangeRows'); rows.replaceChildren();

 $('rangeReference').textContent=f?money(f.range_forecast.reference_close):'—';

 if(!f){$('rangeStatus').textContent='Generate a forecast to compare its full five-minute range.';return;}

 const p=f.range_forecast,o=f.range_outcome;

 $('rangeStatus').textContent=(o.status==='complete'?'Final: all five minutes revealed.':o.status==='incomplete'?'Incomplete: missing target minutes; no final range score.':`Actual range so far: ${o.observed_minutes} of 5 minutes revealed.`)+` ${p.valid_paths} valid sampled paths; ${p.excluded_paths} invalid paths excluded.`;

 for(const [key,label] of [['high','Highest high'],['low','Lowest low'],['upside','Upside from reference'],['downside','Downside from reference']]){

  const tr=document.createElement('tr');

  for(const value of [label,money(p[key]?.median),p[key]?`${money(p[key].p10)} – ${money(p[key].p90)}`:'Unavailable',money(o.actual[key]),money(o.absolute_errors[key])]){const td=document.createElement('td');td.textContent=value;tr.append(td);}

  rows.append(tr);

 }

}



function renderTouches(f){

 const pct=x=>x==null?'--':x.toFixed(1)+'%';

 const label=o=>o.status==='complete'?o.outcome.replaceAll('_',' ')+(o.minutes_to_resolution!=null?' at '+o.minutes_to_resolution+' min':''):o.status;

 const extended=$('extendedSummary');extended.replaceChildren();

 const add=(body,values)=>{const tr=document.createElement('tr');for(const value of values){const td=document.createElement('td');td.textContent=value;tr.append(td);}body.append(tr);};

 const body=$('touchRows');body.replaceChildren();const summary=$('touchSummary');summary.replaceChildren();

 $('touchStatus').textContent=!f?'Generate a forecast to freeze direction and levels.':f.touch_setup.status!=='ready'?'No directional setup: '+f.touch_setup.status:`Direction: ${f.touch_setup.direction}. Reference ${money(f.touch_setup.reference)}. Frozen 1R = ${money(f.touch_setup.risk)} (Wilder ATR14 over input window). ${f.touch_setup.valid_paths} valid paths; ${f.touch_setup.excluded_paths} excluded.`;

 if(f)for(const s of f.touch_setup.setups){const o=f.touch_outcomes.find(x=>x.ratio===s.ratio);add(body,[s.ratio+':1',money(s.target)+' / '+money(s.stop),['target_first','stop_first','neither','ambiguous'].map(k=>pct(s.path_percentages[k])).join(' / '),label(o),label(f.extended_touch_outcomes.find(x=>x.ratio===s.ratio))]);}

 for(const r of state.extended_touch_summary){add(extended,[r.ratio+':1',r.completed,...['target_first','stop_first','expired','ambiguous'].map(k=>pct(r.percentages[k])+' ('+r.counts[k]+')'),[r.counts.open,r.counts.incomplete,r.counts.no_setup].join(' / ')]);}

 for(const r of state.touch_summary){add(summary,[r.ratio+':1',r.completed,...['target_first','stop_first','neither','ambiguous'].map(k=>pct(r.percentages[k])+' ('+r.counts[k]+')'),[r.counts.pending,r.counts.incomplete,r.counts.no_setup].join(' / ')]);}

}



$('locationWindow').onchange=()=>renderContext(state?.forecasts.find(f=>f.id===selected));

function renderContext(f){

 const rows=$('contextRows');rows.replaceChildren();const results=$('locationRows');results.replaceChildren();

 const add=(body,values)=>{const tr=document.createElement('tr');for(const v of values){const td=document.createElement('td');td.textContent=v;tr.append(td);}body.append(tr);};

 const ctx=f?.market_context;

 $('contextStatus').textContent=ctx?`Frozen at ${time(ctx.as_of)} NY. ${ctx.location_group.replaceAll('_',' ')}; ${ctx.confluence_pairs.length} hourly/daily average pairs. SMA20 trend agreement: ${ctx.trend_agreement}. Kronos: ${ctx.kronos_direction}. Near = within 0.5R. Completed regular-session bars only.`:'Generate a forecast to record its market context.';

 if(ctx)for(const v of ctx.levels)add(rows,[v.timeframe+' '+v.name,money(v.value),money(v.distance)+' / '+(v.distance_r==null?'unavailable':v.distance_r.toFixed(2)+'R'),v.value==null?'Insufficient or missing history':v.side+' / '+v.approach,v.slope==null?'--':money(v.slope)]);

 const window=$('locationWindow').value;

 for(const group of state?.location_summary||[])for(const r of group[window]){

 const neither=window==='extended'?'expired':'neither',pending=window==='extended'?'open':'pending';

 add(results,[group.group.replaceAll('_',' ')+' / '+r.ratio+':1',group.forecasts+' / '+r.completed,...['target_first','stop_first',neither,'ambiguous'].map(k=>(r.percentages[k]==null?'--':r.percentages[k].toFixed(1)+'%')+' ('+r.counts[k]+')'),[r.counts[pending],r.counts.incomplete,r.counts.no_setup].join(' / ')]);

 }

}



$('hourForecast').onclick=()=>{pause();action(()=>forecastHour())};

$('hourSelect').onchange=()=>{selectedHour=$('hourSelect').value;render()};

$('showHour').onchange=draw;

$('hourDetails').ontoggle=()=>HourView.detail(state,state?.hour_forecasts?.find(f=>f.id===selectedHour));



async function liveForecasts(){
 if(!liveRunning||!state?.live_info?.ready)return;
 const warnings=[];
 if($('auto').checked&&state.can_forecast&&state.clock!==liveLastForecast){
  liveLastForecast=state.clock;
  try{await forecast();}catch(e){warnings.push('Five-minute forecast: '+e.message);}
 }
 const due=HourView.rolloverSamples(state,$('autoHour').checked);
 if(state.can_hour_forecast&&$('autoHour').checked&&(!state.hour_forecasts.length||due!==null)){
  try{await forecastHour(due??Number($('samples').value));}catch(e){warnings.push('Hour forecast: '+e.message);}
 }
 return warnings.join(' | ');
}
async function startLive(){

 await action(async()=>{

  try{message('Connecting to the official Webull data feed…');$('amountMode').value='approximate';if($('model').value==='saved')$('model').value='base';

  selected='';selectedHour='';liveLastForecast='';

  accept(await api('live',{symbol:$('liveSymbol').value,lookback:Number($('lookback').value)}));liveRunning=true;$('auto').checked=true;

  const warning=await liveForecasts();message(warning||state.live_info.message,!!warning);

  }catch(e){stopLive();throw e;}

 });

 if(liveRunning)liveTimer=setTimeout(liveTick,livePollDelay());

}

async function liveTick(){

 if(!liveRunning)return;

 if(busy){liveTimer=setTimeout(liveTick,1000);return;}

 await action(async()=>{try{accept(await api('live',{symbol:$('liveSymbol').value,lookback:Number($('lookback').value)}));const warning=await liveForecasts();message(warning||state.live_info.message,!!warning);}catch(e){if(state){state.can_forecast=false;state.can_hour_forecast=false;}$('feedStatus').textContent='Candle update failed; retrying shortly: '+e.message;message($('feedStatus').textContent,true);}});

 if(liveRunning)liveTimer=setTimeout(liveTick,livePollDelay());

}

$('stopLive').onclick=()=>{stopLive();$('feedStatus').textContent='Live polling stopped. Candles and forecasts already recorded remain saved.';};

$('sourceMode').onchange=async()=>{

 pause();stopLive();const mode=$('sourceMode').value;

 $('load').textContent=mode==='live'?'Connect Webull':mode==='recorded'?'Load Webull recording':'Load session';

 $('feedStatus').textContent=mode==='live'?'Official QQQ completed candles, checked after each minute closes while connected. New candles trigger forecasts; regular session only.':mode==='recorded'?'Replay locally recorded Webull candles.':'Historical Nasdaq replay.';

 if(mode==='recorded')await action(async()=>{recordedDates=(await api('recordings',{symbol:$('liveSymbol').value})).dates;if(recordedDates.length){$('date').min=recordedDates[0];$('date').max=recordedDates.at(-1);$('date').value=recordedDates.at(-1);}else message('No Webull recordings yet. Connect Webull first.');});

 else if(mode==='historical'){$('date').min=catalog.dates[0];$('date').max=catalog.dates.at(-1);$('date').value=catalog.default_date;}

 controls();

};



let quoteActive=false,quoteTimer=null;

$('streamToggle').onclick=()=>{quoteActive=!quoteActive;$('streamToggle').textContent=quoteActive?'Disconnect quotes & time-and-sales':'Connect quotes & time-and-sales';if(quoteActive)quotePoll();else{clearTimeout(quoteTimer);LabChart.stream(null);$('streamStatus').textContent='Disconnected. Recording stops within 30 seconds unless another tab is connected.';}};

async function quotePoll(){

 try{const symbol=$('liveSymbol').value;const q=await api('stream',{symbol});if(!quoteActive||symbol!==$('liveSymbol').value)return;

 $('streamStatus').textContent=q.error||(q.stale?'Waiting / stale  -  no fresh stream messages.':'Receiving Webull stream  -  recorded locally');

 $('streamPrice').textContent=money(q.price);$('streamQuote').textContent=`  -  Bid ${money(q.bid)} / Ask ${money(q.ask)}`;

 $('formingInfo').textContent=q.forming?'Partial forming candle  -  '+new Date(q.forming.time*1000).toLocaleTimeString('en-US',{timeZone:'America/New_York'})+' Eastern  -  shown on live 1-minute chart only':'';

 const tape=$('streamTape');tape.replaceChildren();for(const t of (q.ticks||[]).slice().reverse()){const tr=document.createElement('tr');let stamp=Number(t.time);const d=Number.isFinite(stamp)?new Date(stamp>1e12?stamp:stamp*1000):new Date(t.time);for(const v of [(/^\d{2}:\d{2}:\d{2}$/.test(t.time)?t.time:d.toLocaleTimeString('en-US',{timeZone:'America/New_York'})),money(t.price),t.size,t.side]){const td=document.createElement('td');td.textContent=v;tr.append(td)}tape.append(tr)}

 LabChart.stream(!q.stale&&q.forming?.time===Math.floor(Date.now()/60000)*60&&state?.mode==='live'&&$('chartTimeframe').value==='1'?q.forming:null);

 }catch(e){$('streamStatus').textContent='Stream unavailable: '+e.message;}

 if(quoteActive)quoteTimer=setTimeout(quotePoll,1000);

}


$('liveSymbol').onchange=async()=>{
 stopLive();pause();quoteActive=false;clearTimeout(quoteTimer);LabChart.stream(null);
 $('streamTape').replaceChildren();$('streamPrice').textContent='—';$('streamQuote').textContent='';$('formingInfo').textContent='';
 $('liveSymbolTitle').textContent=$('liveSymbol').value;
 $('sourceMode').value='live';$('load').textContent='Connect Webull';
 await load();quoteActive=true;$('streamToggle').textContent='Disconnect quotes & time-and-sales';quotePoll();
};

function livePollDelay(){
 const now=Date.now(),boundary=Math.floor(now/60000)*60000,readyAt=boundary+6000;
 if(now<readyAt)return readyAt-now;
 return state?.clock&&Date.parse(state.clock)>=boundary?readyAt+60000-now:5000;
}
