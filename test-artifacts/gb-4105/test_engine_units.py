"""引擎单元验收：区间交界、无归属采样、原连接方式、确定性。"""
import sys,os
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..','backend')))
import pytest
from src.services.operators import execute,validate_steps

DS={'sensors':[{'sensor_id':1,'zone':'北场','device_type':'pump'},{'sensor_id':1,'zone':'复核点','device_type':'pump'}],
    'readings':[{'sensor_id':1,'value':10,'recorded_at':'2026-11-17T08:59:59'},
                {'sensor_id':1,'value':20,'recorded_at':'2026-11-17T09:00:00'},
                {'sensor_id':1,'value':30,'recorded_at':'2026-11-17T09:30:00'},
                {'sensor_id':1,'value':40,'recorded_at':'2026-11-17T10:00:00'},
                {'sensor_id':1,'value':50,'recorded_at':'2026-11-17T10:00:01'}]}
JOIN={'op':'hash_join','right':'sensors','left_key':'sensor_id','right_key':'sensor_id'}
SCAN={'op':'scan','source':'readings'}
GROUP={'op':'group','keys':['zone'],'measure':'value','aggregate':'avg'}

def test_boundary_start_inclusive_end_exclusive():
 steps=[SCAN,{**JOIN,'zone_mode':'sample_time'},GROUP]
 iv=[{'sensor_id':1,'zone':'南场','valid_from':'2026-11-17T09:00:00','valid_to':'2026-11-17T10:00:00'}]
 r=execute(DS,steps,iv,1)
 assert r['output']==[{'zone':'南场','avg':25.0}]  # 09:00与09:30入区；10:00整点被排除
 d=r['operators'][1]['detail']
 assert d['probe_rows']==5 and d['unmatched_rows']==3 and d['zone_version']==1

def test_adjacent_intervals_no_gap_no_overlap():
 steps=[SCAN,{**JOIN,'zone_mode':'sample_time'},GROUP]
 iv=[{'sensor_id':1,'zone':'北场','valid_from':'2026-11-17T09:00:00','valid_to':'2026-11-17T09:30:00'},
     {'sensor_id':1,'zone':'南场','valid_from':'2026-11-17T09:30:00','valid_to':'2026-11-17T10:00:00'}]
 r=execute(DS,steps,iv,2)
 assert r['output']==[{'zone':'北场','avg':20.0},{'zone':'南场','avg':30.0}]  # 09:30整点归属后一区间

def test_no_intervals_all_dropped():
 r=execute(DS,[SCAN,{**JOIN,'zone_mode':'sample_time'},GROUP],[],0)
 assert r['output']==[] and r['operators'][1]['detail']['unmatched_rows']==5

def test_original_join_unchanged_duplicate_keys_retained():
 r=execute(DS,[SCAN,JOIN,GROUP])
 assert r['output']==[{'zone':'北场','avg':30.0},{'zone':'复核点','avg':30.0}]  # 右表重复键保留倍数，全部5行参与
 assert r['operators'][1]['detail']['zone_mode']=='current'

def test_deterministic_checksum():
 steps=[SCAN,{**JOIN,'zone_mode':'sample_time'},GROUP]
 iv=[{'sensor_id':1,'zone':'南场','valid_from':'2026-11-17T09:00:00','valid_to':'2026-11-17T10:00:00'}]
 assert execute(DS,steps,iv,1)['checksum']==execute(DS,steps,iv,1)['checksum']

def test_validate_zone_mode():
 validate_steps([SCAN,{**JOIN,'zone_mode':'current'},GROUP])
 validate_steps([SCAN,{**JOIN,'zone_mode':'sample_time'},GROUP])
 with pytest.raises(ValueError):validate_steps([SCAN,{**JOIN,'zone_mode':'bogus'},GROUP])
 with pytest.raises(ValueError):validate_steps([SCAN,{**JOIN,'zone_mode':'sample_time','extra':1},GROUP])
 with pytest.raises(ValueError):validate_steps([SCAN,{**JOIN,'zone_mode':'sample_time'},{'op':'group','keys':['device_type'],'measure':'value','aggregate':'avg'}])
