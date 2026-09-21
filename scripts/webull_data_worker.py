"""Local data-only worker, using the scanner's installed official SDK.

JSON lines on stdin/stdout. Never imports trading, account, or order clients.
Credentials and SDK output never cross the worker boundary.
"""
import contextlib
import io
import json
import logging
from pathlib import Path
import sys

SCANNER=Path(r'C:\Users\ruley\WebullTradingScanner')


def run():
    sys.path.insert(0,str(SCANNER))
    import yaml
    from dotenv import dotenv_values
    from scanner.config import WebullConfig
    from scanner.webull_client import OfficialWebullBackend
    raw=yaml.safe_load((SCANNER/'config.yaml').read_text()) or {}
    env=dotenv_values(SCANNER/'.env'); wb=raw.get('webull',{})
    cfg=WebullConfig(backend='official',use_production=True,region='us',
        app_key=env.get('WEBULL_APP_KEY') or wb.get('app_key',''),
        app_secret=env.get('WEBULL_APP_SECRET') or wb.get('app_secret',''),
        token_dir=str(SCANNER/wb.get('token_dir','.webull_token')),max_retries=1)
    if not cfg.configured_official: raise ValueError('missing_credentials')
    logging.disable(logging.CRITICAL)
    client=OfficialWebullBackend(cfg,SCANNER)
    for line in sys.stdin:
        try:
            request=json.loads(line)
            symbol=request.get('symbol','QQQ')
            if symbol not in ('QQQ','TSLA','NVDA'):raise ValueError('Unsupported symbol')
            if request.get('action') not in ('fetch','probe'): raise ValueError('unsupported_request')
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                if not client._connected: client.connect(token_wait_seconds=60)
                frames={}
                for interval in (['M1','M5'] if request.get('warmup',False) else ['M1']):
                    frame=client.get_bars(symbol,interval,1200 if request.get('warmup',False) else 120)
                    frames[interval]=json.loads(frame.to_json(orient='records',date_format='iso'))
            result=dict(ok=True,provider='webull_official',symbol=symbol,frames=frames)
        except Exception as exc:
            # Never emit raw provider errors: signed headers/credentials can occur.
            message=str(exc).upper()
            reason='Webull data request failed. Check the scanner connection and API access.'
            if any(v in message for v in ['403','NOT_SUBSCRIBED','INSUFFICIENT']): reason='Webull denied market-data access. Check the existing OpenAPI data entitlement.'
            elif any(v in message for v in ['TOKEN','401','PENDING','AUTHORIZ','VERIFIED']): reason='Webull authorization is needed. Open the scanner and authorize its official connection, then retry.'
            result=dict(ok=False,error=reason)
        print(json.dumps(result,allow_nan=False),flush=True)


if __name__=='__main__':
    try: run()
    except Exception:
        print(json.dumps(dict(ok=False,error='Webull worker setup failed. Check scanner installation and local credentials.')),flush=True)
