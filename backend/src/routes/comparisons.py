from fastapi import APIRouter,Depends
from src.config.database import get_db
from src.utils.auth import current_user,editor
from src.schemas.comparison import ComparisonInput
from src.controllers.comparison_controller import list_comparisons,create_comparison,get_comparison
router=APIRouter(prefix='/comparisons')
@router.get('')
def index(db=Depends(get_db),user=Depends(current_user)):return list_comparisons(db)
@router.post('',status_code=201)
def create(data:ComparisonInput,db=Depends(get_db),user=Depends(editor)):return create_comparison(db,data)
@router.get('/{id}')
def detail(id:int,db=Depends(get_db),user=Depends(current_user)):return get_comparison(db,id)
