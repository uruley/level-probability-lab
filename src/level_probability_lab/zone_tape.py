"""Receive-time first-print touch ordering, separate from candle labels."""
import pandas as pd

def resolve(tape, event, touch_minute):
    start=pd.Timestamp(event['cutoff']); touch_minute=pd.Timestamp(touch_minute)
    end=touch_minute+pd.Timedelta(minutes=15)
    level,risk=event['level'],event['risk'];direction=1 if event['price']>level else -1
    lower,upper=level-.1*risk,level+.1*risk
    data=tape[(tape.ts_recv>=start)&(tape.ts_recv<end)].sort_values('ts_recv',kind='stable')
    touch=None;touch_price=None
    for stamp,g in data.groupby('ts_recv',sort=True):
        prices=g.price
        if touch is None:
            hits=g[(prices>=lower)&(prices<=upper)]
            if not len(hits):
                if ((prices<lower) if direction==1 else (prices>upper)).any():
                    return dict(status='gap_over_zone',time=stamp.isoformat())
                continue
            if stamp.floor('min')!=touch_minute:
                return dict(status='incomplete',reason='tape/candle first-touch mismatch')
            touch=stamp;touch_price=float(hits.iloc[0].price)
            if (prices>=level+.5*risk).any() or (prices<=level-.5*risk).any():
                return dict(status='ambiguous',reason='same receive timestamp touch and barrier')
            continue
        up=(prices>=level+.5*risk).any();down=(prices<=level-.5*risk).any()
        if up and down:return dict(status='ambiguous',reason='same receive timestamp both barriers')
        if up or down:
            subset=data[(data.ts_recv>=touch)&(data.ts_recv<=stamp)]
            zone=subset[(subset.price>=lower)&(subset.price<=upper)]
            return dict(status='rejection' if (up if direction==1 else down) else 'continuation',
                touch=touch.isoformat(),touch_price=touch_price,resolved_at=stamp.isoformat(),
                seconds_after_touch=(stamp-touch).total_seconds(),
                zone_shares_until_resolution=float(zone['size'].sum()),zone_prints_until_resolution=len(zone))
    return dict(status='unresolved' if touch is not None else 'no_trade_in_zone',touch=touch.isoformat() if touch is not None else None)
