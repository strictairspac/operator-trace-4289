"""边界与权限验收：非法区间422、观察员403、缺失资源404、相邻区间允许。"""
from conftest import uniq,make_dataset,make_plan,submit_trace,drain,get_trace,SENSORS,READINGS

def test_invalid_intervals_422(client,auth):
 ds=make_dataset(client,auth,SENSORS,READINGS)
 bad=[[{'sensor_id':1,'zone':'甲','valid_from':'not-a-time','valid_to':'2026-11-17T10:00:00'}],
      [{'sensor_id':1,'zone':'甲','valid_from':'2026-11-17T10:00:00','valid_to':'2026-11-17T09:00:00'}],
      [{'sensor_id':1,'zone':'甲','valid_from':'2026-11-17T09:00:00','valid_to':'2026-11-17T09:00:00'}],
      [],]
 for iv in bad:
  r=client.post(f"/datasets/{ds['id']}/zones",headers=auth,json={'intervals':iv})
  assert r.status_code==422,(iv,r.status_code,r.text)
 cur=client.get(f"/datasets/{ds['id']}/zones",headers=auth).json()
 assert cur['version']==0 and cur['intervals']==[]

def test_adjacent_registration_allowed(client,auth):
 ds=make_dataset(client,auth,SENSORS,READINGS)
 r=client.post(f"/datasets/{ds['id']}/zones",headers=auth,json={'intervals':[
  {'sensor_id':1,'zone':'甲','valid_from':'2026-11-17T08:00:00','valid_to':'2026-11-17T10:00:00'},
  {'sensor_id':1,'zone':'乙','valid_from':'2026-11-17T10:00:00','valid_to':'2026-11-17T12:00:00'}]})
 assert r.status_code==200 and r.json()['version']==1  # 首尾相接不算相交

def test_viewer_forbidden(client,auth):
 r=client.post('/auth/login',json={'email':'viewer@operator.local','password':'Trace2026!'})
 v={'Authorization':'Bearer '+r.json()['token']}
 ds=make_dataset(client,auth,SENSORS,READINGS)
 assert client.post(f"/datasets/{ds['id']}/zones",headers=v,json={'intervals':[{'sensor_id':1,'zone':'甲','valid_from':'2026-11-17T08:00:00','valid_to':'2026-11-17T10:00:00'}]}).status_code==403
 t=submit_trace(client,auth,make_plan(client,auth,ds['id'],[{'op':'scan','source':'readings'}])['id'])
 assert client.post(f"/traces/{t['id']}/rerun",headers=v).status_code==403
 assert client.get(f"/datasets/{ds['id']}/zones",headers=v).status_code==200  # 只读可查

def test_missing_resources_404(client,auth):
 r=client.post('/datasets/999999/zones',headers=auth,json={'intervals':[{'sensor_id':1,'zone':'甲','valid_from':'2026-11-17T08:00:00','valid_to':'2026-11-17T10:00:00'}]})
 assert r.status_code==404
 assert client.get('/datasets/999999/zones',headers=auth).status_code==404
 assert client.post('/traces/999999/rerun',headers=auth).status_code==404

def test_canonicalization_equivalent_forms(client,auth):
 """同一时刻的不同写法规范后等价，重叠判定不受写法影响。"""
 ds=make_dataset(client,auth,SENSORS,READINGS)
 r=client.post(f"/datasets/{ds['id']}/zones",headers=auth,json={'intervals':[{'sensor_id':1,'zone':'甲','valid_from':'2026-11-17T08:00:00','valid_to':'2026-11-17T10:00:00'}]})
 assert r.status_code==200
 assert r.json()['intervals'][0]['valid_from']=='2026-11-17T08:00:00'
 r=client.post(f"/datasets/{ds['id']}/zones",headers=auth,json={'intervals':[{'sensor_id':1,'zone':'乙','valid_from':'2026-11-17 09:00:00','valid_to':'2026-11-17 11:00:00'}]})
 assert r.status_code==409  # 空格写法规范后与已生效区间相交
