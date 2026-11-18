"""API验收：迟到记录、区间交界、并发重叠、归属版本全程可查、原连接方式。"""
import threading
import httpx
from conftest import (drain,uniq,make_dataset,make_plan,submit_trace,get_trace,join_step,SAMPLE_TIME,SENSORS,READINGS)

def test_late_backfill_and_archive(client,auth):
 """迟到记录：补登前v0无归属全部掉线；补登后新剖面用修正归属；旧剖面存档不变、重跑保持原分组。"""
 ds=make_dataset(client,auth,SENSORS,READINGS)
 plan=make_plan(client,auth,ds['id'],SAMPLE_TIME)
 t1=submit_trace(client,auth,plan['id'])
 assert t1['status']=='queued' and t1['zone_version']==0  # 受理即可查归属版本
 drain()
 t1=get_trace(client,auth,t1['id'])
 assert t1['status']=='completed' and t1['zone_version']==0
 assert t1['result']['output']==[] and join_step(t1)['detail']['unmatched_rows']==3
 c1=t1['result']['checksum']
 r=client.post(f"/datasets/{ds['id']}/zones",headers=auth,json={'note':'迟到补登','intervals':[
  {'sensor_id':1,'zone':'试验间','valid_from':'2026-11-17T08:00:00','valid_to':'2026-11-17T10:30:00'},
  {'sensor_id':2,'zone':'南场','valid_from':'2026-11-17T09:00:00','valid_to':'2026-11-17T10:00:00'}]})
 assert r.status_code==200 and r.json()['version']==1
 t2=submit_trace(client,auth,plan['id']);assert t2['zone_version']==1  # 新剖面采用修正后归属
 drain();t2=get_trace(client,auth,t2['id'])
 assert t2['zone_version']==1  # 完成后版本不变
 assert sorted(t2['result']['output'],key=lambda x:x['zone'])==[{'zone':'南场','avg':50.0},{'zone':'试验间','avg':70.0}]
 t1_after=get_trace(client,auth,t1['id'])
 assert t1_after['result']['output']==[] and t1_after['result']['checksum']==c1  # 存档未被覆盖
 r=client.post(f"/traces/{t1['id']}/rerun",headers=auth)
 assert r.status_code==200 and r.json()['zone_version']==0
 t1r=get_trace(client,auth,r.json()['id']);drain();t1r=get_trace(client,auth,t1r['id'])
 assert t1r['result']['checksum']==c1 and t1r['result']['output']==[]  # 重跑保持原分组
 assert get_trace(client,auth,t1['id'])['result']['checksum']==c1
 listed=client.get('/traces',headers=auth).json()
 assert {x['id']:x['zone_version'] for x in listed if x['id'] in (t1['id'],t2['id'],t1r['id'])}=={t1['id']:0,t2['id']:1,t1r['id']:0}

def test_boundary_via_api(client,auth):
 """区间交界：含起点、不含终点，整点归属准确。"""
 readings=[{'sensor_id':1,'value':v,'recorded_at':ts} for v,ts in
  [(10,'2026-11-17T08:59:59'),(20,'2026-11-17T09:00:00'),(30,'2026-11-17T09:59:59'),(40,'2026-11-17T10:00:00')]]
 ds=make_dataset(client,auth,SENSORS[:1],readings)
 plan=make_plan(client,auth,ds['id'],SAMPLE_TIME)
 r=client.post(f"/datasets/{ds['id']}/zones",headers=auth,json={'intervals':[
  {'sensor_id':1,'zone':'南场','valid_from':'2026-11-17T09:00:00','valid_to':'2026-11-17T10:00:00'}]})
 assert r.status_code==200
 t=submit_trace(client,auth,plan['id']);drain();t=get_trace(client,auth,t['id'])
 assert t['result']['output']==[{'zone':'南场','avg':25.0}]  # 09:00含、10:00不含
 assert join_step(t)['detail']['unmatched_rows']==2

def test_batch_atomic_reject(client,auth):
 """整批拒绝：批内一条撞已生效区间，整批不入库，版本不变。"""
 ds=make_dataset(client,auth,SENSORS,READINGS)
 r=client.post(f"/datasets/{ds['id']}/zones",headers=auth,json={'intervals':[
  {'sensor_id':1,'zone':'试验间','valid_from':'2026-11-17T08:00:00','valid_to':'2026-11-17T12:00:00'}]})
 assert r.status_code==200 and r.json()['version']==1
 r=client.post(f"/datasets/{ds['id']}/zones",headers=auth,json={'intervals':[
  {'sensor_id':2,'zone':'南场','valid_from':'2026-11-17T09:00:00','valid_to':'2026-11-17T10:00:00'},
  {'sensor_id':1,'zone':'北场','valid_from':'2026-11-17T11:00:00','valid_to':'2026-11-17T13:00:00'}]})
 assert r.status_code==409 and '整批登记已拒绝' in r.json()['detail']
 cur=client.get(f"/datasets/{ds['id']}/zones",headers=auth).json()
 assert cur['version']==1 and len(cur['intervals'])==1  # 无任何部分生效
 r=client.post(f"/datasets/{ds['id']}/zones",headers=auth,json={'intervals':[
  {'sensor_id':1,'zone':'甲','valid_from':'2026-11-17T13:00:00','valid_to':'2026-11-17T15:00:00'},
  {'sensor_id':1,'zone':'乙','valid_from':'2026-11-17T14:00:00','valid_to':'2026-11-17T16:00:00'}]})
 assert r.status_code==409  # 批内自相交同样整批拒绝
 assert client.get(f"/datasets/{ds['id']}/zones",headers=auth).json()['version']==1

def test_concurrent_overlap(server,client,auth):
 """并发重叠：互撞的并发登记只有一批生效；互不相交的并发登记全部生效且版本连续。"""
 ds=make_dataset(client,auth,SENSORS,READINGS)
 def fire(batch,results,i):
  r=httpx.post(f"{server}/datasets/{ds['id']}/zones",json={'intervals':batch},headers=auth,timeout=30)
  results[i]=r.status_code
 def race(batches):
  results=[None]*len(batches);barrier=threading.Barrier(len(batches))
  def wrapped(b,i):barrier.wait();fire(b,results,i)
  ts=[threading.Thread(target=wrapped,args=(b,i)) for i,b in enumerate(batches)]
  [t.start() for t in ts];[t.join() for t in ts]
  return results
 overlapping=[[{'sensor_id':1,'zone':z,'valid_from':'2026-11-17T08:00:00','valid_to':'2026-11-17T10:00:00'}] for z in '甲乙丙丁']
 assert sorted(race(overlapping))==[200,409,409,409]  # 同一区间并发：恰好一批生效
 cur=client.get(f"/datasets/{ds['id']}/zones",headers=auth).json()
 assert cur['version']==1 and len(cur['intervals'])==1
 disjoint=[[{'sensor_id':s,'zone':'调','valid_from':f'2026-11-17T{h:02d}:00:00','valid_to':f'2026-11-17T{h+1:02d}:00:00'}] for s,h in [(2,8),(3,9),(4,10)]]
 assert sorted(race(disjoint))==[200,200,200]  # 互不相交：全部生效
 cur=client.get(f"/datasets/{ds['id']}/zones",headers=auth).json()
 assert cur['version']==4 and len(cur['intervals'])==4
 assert sorted(b['version'] for b in cur['batches'])==[1,2,3,4]
 mixed=race([[{'sensor_id':1,'zone':'戊','valid_from':'2026-11-17T09:00:00','valid_to':'2026-11-17T11:00:00'}],
             [{'sensor_id':5,'zone':'己','valid_from':'2026-11-17T12:00:00','valid_to':'2026-11-17T13:00:00'}]])
 assert sorted(mixed)==[200,409]  # 撞已有区间的整批拒绝，不相交的成功
 cur=client.get(f"/datasets/{ds['id']}/zones",headers=auth).json()
 assert cur['version']==5 and len(cur['intervals'])==5

def test_original_mode_still_available(client,auth):
 """原连接方式：不带zone_mode按计划传感器表连接，行为不变。"""
 ds=make_dataset(client,auth,SENSORS,READINGS)
 steps=[{'op':'scan','source':'readings'},{'op':'hash_join','right':'sensors','left_key':'sensor_id','right_key':'sensor_id'},{'op':'group','keys':['zone'],'measure':'value','aggregate':'count'}]
 plan=make_plan(client,auth,ds['id'],steps)
 t=submit_trace(client,auth,plan['id']);drain();t=get_trace(client,auth,t['id'])
 assert sorted(t['result']['output'],key=lambda x:x['zone'])==[{'zone':'北场','count':2},{'zone':'南场','count':1}]
 assert join_step(t)['detail']['zone_mode']=='current'
