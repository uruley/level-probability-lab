import contextlib,io,json,logging,threading,time,uuid
from pathlib import Path
from dotenv import dotenv_values
from webull.data.data_streaming_client import DataStreamingClient
logging.disable(logging.CRITICAL)
import sys
sys.path.insert(0,'C:/Users/ruley/WebullTradingScanner')
from scanner.webull_client import _ensure_official_sdk_version
_ensure_official_sdk_version()
env=dotenv_values(Path('C:/Users/ruley/WebullTradingScanner/.env'))

symbol=sys.argv[1] if len(sys.argv)>1 else 'QQQ'
if symbol not in ('QQQ','TSLA','NVDA'):raise ValueError('Unsupported symbol')
OUT=Path(__file__).resolve().parents[1]/'data/kronos_lab/stream'
if symbol!='QQQ':OUT=OUT/symbol
OUT.mkdir(parents=True,exist_ok=True)
state={'symbol':symbol,'connected':False,'subscribed':False,'ticks':[],'forming':None}
lock=threading.RLock()
def connected(client,*args):
 state['connected']=True
 client.subscribe([symbol],'US_STOCK',['QUOTE','SNAPSHOT','TICK'])
def subscribed(*args):state['subscribed']=True
def message(client,topic,q):
 from datetime import datetime,timezone
 now=time.time(); kind=type(q).__name__
 with lock:
  event={'received_at':now,'type':kind}
  if kind=='TickResult':
   event.update(time=str(q.time),price=float(q.price),size=q.volume,side=str(q.side or 'unknown'))
   state['ticks']=(state['ticks']+[event])[-60:]
   state['price']=event['price'];state['last_trade_received']=now
   try:
    raw=float(q.time);seconds=raw/1000 if raw>1e12 else raw
   except (ValueError,TypeError):
    from zoneinfo import ZoneInfo
    text=str(q.time)
    seconds=datetime.combine(datetime.now(ZoneInfo('America/New_York')).date(),datetime.strptime(text,'%H:%M:%S').time(),tzinfo=ZoneInfo('America/New_York')).timestamp() if len(text)==8 else datetime.fromisoformat(text.replace('Z','+00:00')).timestamp()
   minute=int(seconds//60)*60
   b=state['forming']
   if abs(seconds-now)<90:
    if b is None or minute>b['time']: b={'time':minute,'open':event['price'],'high':event['price'],'low':event['price'],'close':event['price']}
    if minute==b['time']:
     b['high']=max(b['high'],event['price']);b['low']=min(b['low'],event['price']);b['close']=event['price']
    state['forming']=b
  elif kind=='QuoteResult':
   event.update(bid=float(q.bids[0].price) if q.bids else None,ask=float(q.asks[0].price) if q.asks else None)
   state.update(bid=event['bid'],ask=event['ask'])
  elif kind=='SnapshotResult':
   event.update(price=float(q.price) if q.price else None,time=str(q.last_trade_time))
  else:return
  state['received_at']=now
  with (OUT/(datetime.now(timezone.utc).strftime('%Y-%m-%d')+'.jsonl')).open('a') as f:f.write(json.dumps(event)+'\n')
def run():
 try:client.connect_and_loop_forever(logger_enable=False)
 except Exception:state['error']='Stream connection failed. Reconnect to retry.'
with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
 client=DataStreamingClient(env['WEBULL_APP_KEY'],env['WEBULL_APP_SECRET'],'us','kronos-'+uuid.uuid4().hex[:12],http_host='api.webull.com',mqtt_host='data-api.webull.com')
 client.api_client.set_token_dir('C:/Users/ruley/WebullTradingScanner/.webull_token')
 client.api_client._stream_logger_set=True;client.api_client._file_logger_set=True
 client.on_connect_success=connected;client.on_subscribe_success=subscribed;client.on_quotes_message=message
 threading.Thread(target=run,daemon=True).start()
 while time.time()-(OUT/'lease').stat().st_mtime<30:
  with lock:
   tmp=OUT/'latest.tmp';tmp.write_text(json.dumps(state));tmp.replace(OUT/'latest.json')
  time.sleep(.5)
 client.disconnect()
