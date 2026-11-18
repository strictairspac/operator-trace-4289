from fastapi import APIRouter,Depends
from src.middlewares.auth import current,writer
from src.schemas.business import DatasetInput,ZoneBatchInput
from src.services import datasets,zones
from src.controllers.business import save_dataset,save_zones
router=APIRouter()
@router.get('/datasets')
def listing(u=Depends(current)):return datasets.list_items()
@router.post('/datasets')
def create(data:DatasetInput,u=Depends(writer)):return save_dataset(data,u)
@router.put('/datasets/{item_id}')
def update(item_id:int,data:DatasetInput,u=Depends(writer)):return save_dataset(data,u,item_id)
@router.get('/datasets/{item_id}/zones')
def zones_current(item_id:int,u=Depends(current)):return zones.current(item_id)
@router.post('/datasets/{item_id}/zones')
def zones_register(item_id:int,data:ZoneBatchInput,u=Depends(writer)):return save_zones(item_id,data,u)
