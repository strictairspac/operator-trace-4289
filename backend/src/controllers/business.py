from src.services import datasets,plans,traces,zones
from src.services.audit import log
def save_dataset(data,user,item_id=None):
 row=datasets.save(data,item_id);log(user.email,'dataset.save',row['name']);return row
def save_plan(data,user,item_id=None):
 row=plans.save(data,item_id);log(user.email,'plan.save',row['name']);return row
def start_trace(data,user):
 row=traces.create(data);log(user.email,'trace.queue',row['name']);return row
def rerun_trace(item_id,user):
 row=traces.rerun(item_id);log(user.email,'trace.rerun',row['name']);return row
def save_zones(dataset_id,data,user):
 row=zones.register(dataset_id,data,user.email);log(user.email,'zone.backfill',f"dataset#{dataset_id} v{row['version']} {len(data.intervals)}条区间");return row
