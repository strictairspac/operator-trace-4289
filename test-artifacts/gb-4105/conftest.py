"""验收环境：真实 PostgreSQL(15432) + 内存队列替代 Redis + TestClient/真实 uvicorn。
用法：先启动测试库（见 report.md），再 pytest -v。每个用例使用唯一自然名，可重复运行。"""
import os,sys,time,threading,uuid
BACKEND=os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..','backend'))
sys.path.insert(0,BACKEND)
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://trace:tracepass@127.0.0.1:15432/operatortrace')
os.environ['JWT_SECRET']='gb4105-acceptance-secret'
os.environ.setdefault('REDIS_URL','redis://127.0.0.1:6390/9')
os.environ['SEED_DEMO']='true'
import pytest
import src.services.traces as traces_svc
class FakeQueue:
 """进程内队列，替代Redis；drain()模拟worker单消费者。"""
 def __init__(self):self.items=[]
 def rpush(self,key,*vals):self.items.extend(int(v) for v in vals);return len(self.items)
 def ping(self):return True
traces_svc.queue=FakeQueue()
import src.main as main
main.queue=traces_svc.queue
from fastapi.testclient import TestClient
from src.config.database import Session
from src.models.trace import Trace
from src.services.operators import execute

def drain():
 """与 src.worker 主循环相同的取任务-执行-落库逻辑。"""
 while traces_svc.queue.items:
  run_id=traces_svc.queue.items.pop(0)
  with Session() as s:
   row=s.get(Trace,run_id)
   if not row or row.status!='queued':continue
   row.status='running';snapshot=row.snapshot;s.commit()
  try:
   result=execute(snapshot['dataset'],snapshot['plan']['steps'],snapshot.get('zone_intervals'),snapshot.get('zone_version',0))
   with Session() as s:r=s.get(Trace,run_id);r.result=result;r.status='completed';s.commit()
  except Exception as exc:
   with Session() as s:r=s.get(Trace,run_id);r.status='failed';r.error=str(exc)[:1000];s.commit()

@pytest.fixture(scope='session')
def client():
 with TestClient(main.app) as c:yield c
@pytest.fixture(scope='session')
def auth(client):
 r=client.post('/auth/login',json={'email':'operator@operator.local','password':'Trace2026!'})
 assert r.status_code==200,r.text
 return {'Authorization':'Bearer '+r.json()['token']}
@pytest.fixture(scope='session')
def server(client):
 import uvicorn
 srv=uvicorn.Server(uvicorn.Config(main.app,host='127.0.0.1',port=18099,log_level='error'))
 threading.Thread(target=srv.run,daemon=True).start()
 for _ in range(200):
  try:
   import socket
   with socket.create_connection(('127.0.0.1',18099),timeout=0.2):break
  except OSError:time.sleep(0.1)
 else:raise RuntimeError('uvicorn未启动')
 yield 'http://127.0.0.1:18099'
 srv.should_exit=True

def uniq(tag):return f'gb4105-{tag}-{uuid.uuid4().hex[:10]}'
def make_dataset(client,auth,sensors,readings):
 r=client.post('/datasets',json={'name':uniq('ds'),'description':'调区验收','sensors':sensors,'readings':readings},headers=auth)
 assert r.status_code==200,r.text
 return r.json()
def make_plan(client,auth,dataset_id,steps):
 r=client.post('/plans',json={'name':uniq('plan'),'dataset_id':dataset_id,'steps':steps,'note':'调区验收'},headers=auth)
 assert r.status_code==200,r.text
 return r.json()
def submit_trace(client,auth,plan_id):
 r=client.post('/traces',json={'name':uniq('trace'),'plan_id':plan_id},headers=auth)
 assert r.status_code==200,r.text
 return r.json()
def get_trace(client,auth,trace_id):
 r=client.get(f'/traces/{trace_id}',headers=auth)
 assert r.status_code==200,r.text
 return r.json()
def join_step(trace):return next(o for o in trace['result']['operators'] if o['op']=='hash_join')
SAMPLE_TIME=[{'op':'scan','source':'readings'},{'op':'hash_join','right':'sensors','left_key':'sensor_id','right_key':'sensor_id','zone_mode':'sample_time'},{'op':'group','keys':['zone'],'measure':'value','aggregate':'avg'}]
SENSORS=[{'sensor_id':1,'zone':'北场','device_type':'pump'},{'sensor_id':2,'zone':'南场','device_type':'motor'}]
READINGS=[{'sensor_id':1,'value':80,'recorded_at':'2026-11-17T09:00:00'},
          {'sensor_id':1,'value':60,'recorded_at':'2026-11-17T10:00:00'},
          {'sensor_id':2,'value':50,'recorded_at':'2026-11-17T09:30:00'}]
