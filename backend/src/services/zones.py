from collections import defaultdict
from fastapi import HTTPException
from sqlalchemy import func
from src.config.database import Session
from src.models.dataset import Dataset
from src.models.zone import ZoneBatch,ZoneInterval
from src.utils.serialization import record

def _version(s,dataset_id):return s.query(func.max(ZoneBatch.version)).filter(ZoneBatch.dataset_id==dataset_id).scalar() or 0
def _intervals(s,dataset_id):
 return s.query(ZoneInterval).filter_by(dataset_id=dataset_id).order_by(ZoneInterval.sensor_id,ZoneInterval.valid_from,ZoneInterval.id).all()
def pinned(s,dataset_id):
 """归属快照：受理执行时锁定，供worker按采样时刻连接。单条查询保证版本与区间一致。"""
 rows=(s.query(ZoneInterval.sensor_id,ZoneInterval.zone,ZoneInterval.valid_from,ZoneInterval.valid_to,ZoneBatch.version)
  .join(ZoneBatch,ZoneInterval.batch_id==ZoneBatch.id).filter(ZoneInterval.dataset_id==dataset_id)
  .order_by(ZoneInterval.sensor_id,ZoneInterval.valid_from,ZoneInterval.id).all())
 version=max((r[4] for r in rows),default=0)
 return version,[{'sensor_id':r[0],'zone':r[1],'valid_from':r[2],'valid_to':r[3]} for r in rows]
def current(dataset_id):
 with Session() as s:
  if not s.get(Dataset,dataset_id):raise HTTPException(404,'未找到数据集')
  batches=s.query(ZoneBatch).filter_by(dataset_id=dataset_id).order_by(ZoneBatch.version.desc()).all()
  return {'dataset_id':dataset_id,'version':_version(s,dataset_id),'intervals':[record(i) for i in _intervals(s,dataset_id)],'batches':[record(b) for b in batches]}
def register(dataset_id,data,actor):
 with Session() as s:
  d=s.query(Dataset).filter_by(id=dataset_id).with_for_update().first()
  if not d:raise HTTPException(404,'未找到数据集')
  by_sensor=defaultdict(list);fresh=defaultdict(list)
  for e in _intervals(s,dataset_id):by_sensor[e.sensor_id].append((e.valid_from,e.valid_to))
  for iv in data.intervals:
   for f,t in by_sensor[iv.sensor_id]:
    if iv.valid_from<t and f<iv.valid_to:raise HTTPException(409,f'传感器{iv.sensor_id}区间[{iv.valid_from},{iv.valid_to})与已生效归属[{f},{t})重叠，整批登记已拒绝')
   for f,t in fresh[iv.sensor_id]:
    if iv.valid_from<t and f<iv.valid_to:raise HTTPException(409,f'传感器{iv.sensor_id}区间[{iv.valid_from},{iv.valid_to})与本批次另一区间[{f},{t})重叠，整批登记已拒绝')
   fresh[iv.sensor_id].append((iv.valid_from,iv.valid_to))
  version=_version(s,dataset_id)+1
  batch=ZoneBatch(dataset_id=dataset_id,version=version,actor=actor,note=data.note)
  s.add(batch);s.flush()
  for iv in data.intervals:s.add(ZoneInterval(batch_id=batch.id,dataset_id=dataset_id,sensor_id=iv.sensor_id,zone=iv.zone,valid_from=iv.valid_from,valid_to=iv.valid_to))
  s.commit()
 return current(dataset_id)
