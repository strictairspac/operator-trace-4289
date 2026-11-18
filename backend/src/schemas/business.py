from pydantic import BaseModel,Field,model_validator,ConfigDict
from typing import Literal
from src.services.operators import validate_steps
from src.utils.times import canonical
class Login(BaseModel):
 email:str;password:str
class Sensor(BaseModel):
 model_config=ConfigDict(extra='forbid')
 sensor_id:int=Field(ge=1,le=100000)
 zone:str=Field(min_length=1,max_length=40)
 device_type:Literal['pump','motor','valve']
class Reading(BaseModel):
 model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
 sensor_id:int=Field(ge=1,le=100000)
 value:float=Field(ge=-1000000,le=1000000)
 recorded_at:str=Field(min_length=1,max_length=40)
class DatasetInput(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 description:str=Field(default='',max_length=500)
 sensors:list[Sensor]=Field(max_length=100)
 readings:list[Reading]=Field(max_length=2000)
class PlanInput(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 dataset_id:int
 steps:list[dict]
 note:str=Field(default='',max_length=500)
 @model_validator(mode='after')
 def validate(self):validate_steps(self.steps);return self
class TraceInput(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 plan_id:int
class ZoneIntervalInput(BaseModel):
 model_config=ConfigDict(extra='forbid')
 sensor_id:int=Field(ge=1,le=100000)
 zone:str=Field(min_length=1,max_length=40)
 valid_from:str=Field(min_length=1,max_length=40)
 valid_to:str=Field(min_length=1,max_length=40)
 @model_validator(mode='after')
 def validate(self):
  f,t=canonical(self.valid_from),canonical(self.valid_to)
  if f is None or t is None:raise ValueError('valid_from/valid_to须为ISO 8601时间，如2026-11-17T09:00:00')
  if not f<t:raise ValueError('valid_from必须早于valid_to；区间含起点、不含终点')
  self.valid_from,self.valid_to=f,t
  return self
class ZoneBatchInput(BaseModel):
 intervals:list[ZoneIntervalInput]=Field(min_length=1,max_length=200)
 note:str=Field(default='',max_length=200)
