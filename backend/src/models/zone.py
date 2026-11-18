from sqlalchemy import Column,Integer,String,DateTime,func,ForeignKey
from src.config.database import Base
class ZoneBatch(Base):
 __tablename__='zone_batches'
 id=Column(Integer,primary_key=True)
 dataset_id=Column(Integer,ForeignKey('datasets.id'),nullable=False)
 version=Column(Integer,nullable=False)
 actor=Column(String(120),nullable=False,default='')
 note=Column(String(200),nullable=False,default='')
 created_at=Column(DateTime,server_default=func.now())
class ZoneInterval(Base):
 __tablename__='zone_intervals'
 id=Column(Integer,primary_key=True)
 batch_id=Column(Integer,ForeignKey('zone_batches.id'),nullable=False)
 dataset_id=Column(Integer,ForeignKey('datasets.id'),nullable=False)
 sensor_id=Column(Integer,nullable=False)
 zone=Column(String(40),nullable=False)
 valid_from=Column(String(40),nullable=False)
 valid_to=Column(String(40),nullable=False)
