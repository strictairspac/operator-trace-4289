import redis
from fastapi import HTTPException
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.models.dataset import Dataset
from src.models.plan import Plan
from src.models.trace import Trace
from src.services.zones import pinned
from src.utils.serialization import record
queue=redis.Redis.from_url(REDIS_URL)
def list_items():
 with Session() as s:return [record(r) for r in s.query(Trace).order_by(Trace.id.desc()).limit(100).all()]
def detail(item_id):
 with Session() as s:
  row=s.get(Trace,item_id)
  if not row:raise HTTPException(404,'未找到执行轨迹')
  return record(row)
def _enqueue(row_id):
 try:queue.rpush('operator-traces',row_id)
 except redis.RedisError:
  with Session() as s:r=s.get(Trace,row_id);r.status='failed';r.error='队列不可用，请创建新任务';s.commit()
  raise HTTPException(503,'队列不可用，请稍后重试')
def create(data):
 with Session() as s:
  p=s.get(Plan,data.plan_id)
  if not p:raise HTTPException(404,'未找到算子计划')
  d=s.get(Dataset,p.dataset_id)
  version,intervals=pinned(s,d.id)
  row=Trace(name=data.name,plan_id=p.id,dataset_id=d.id,status='queued',zone_version=version,snapshot={'dataset':record(d),'plan':record(p),'zone_version':version,'zone_intervals':intervals})
  s.add(row);s.commit();s.refresh(row);result=record(row)
 _enqueue(result['id'])
 return result
def rerun(item_id):
 with Session() as s:
  old=s.get(Trace,item_id)
  if not old:raise HTTPException(404,'未找到执行轨迹')
  base=f'{old.name[:90]}-rerun-{old.id}';name=base;n=2
  while s.query(Trace).filter_by(name=name).first():name=f'{base}-{n}';n+=1
  row=Trace(name=name,plan_id=old.plan_id,dataset_id=old.dataset_id,status='queued',zone_version=old.zone_version,snapshot=old.snapshot)
  s.add(row);s.commit();s.refresh(row);result=record(row)
 _enqueue(result['id'])
 return result
