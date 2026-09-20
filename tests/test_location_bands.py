from level_probability_lab.location_bands import band,classify


def test_band_boundaries_and_missing():
    assert [band(v) for v in [0,.5,.50001,1,1.00001,2,2.00001,None,float('nan'),-1]]==['0_to_0.5R','0_to_0.5R','0.5_to_1R','0.5_to_1R','1_to_2R','1_to_2R','over_2R','unknown','unknown','unknown']


def test_confluence_requires_pair_closeness_not_just_near_price():
    levels=[]
    for tf,d in [('hourly',.4),('daily',-.4)]:
        levels += [dict(timeframe=tf,name='SMA '+str(p),distance_r=d) for p in [5,10,20,50,100,200]]
        levels += [dict(timeframe=tf,name='BB '+b,distance_r=d) for b in ['upper','lower']]
    r=classify(dict(levels=levels))
    assert r['hourly_sma_band']=='0_to_0.5R'
    assert r['sma_confluence_distance_r']==.8 and r['sma_confluence_band']=='0.5_to_1R'
    levels[0]['distance_r']=None
    assert classify(dict(levels=levels))['sma_confluence_band']=='unknown'
