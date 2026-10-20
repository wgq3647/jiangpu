from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from models import Factor, User
from routers.auth import get_current_user

router = APIRouter(prefix="/api/factors", tags=["因子库"])

class FactorCreate(BaseModel):
    name: str
    field_type: str
    description: str = ""

class FactorUpdate(BaseModel):
    name: str = None
    field_type: str = None
    description: str = None

# 字段类型选项
FIELD_TYPE_OPTIONS = [
    {"value": "枚举", "label": "枚举"},
    {"value": "单选", "label": "单选"},
    {"value": "多选", "label": "多选"},
    {"value": "数字", "label": "数字"},
    {"value": "文本", "label": "文本"},
]

@router.get("/field-types")
def get_field_types():
    """获取字段类型选项"""
    return FIELD_TYPE_OPTIONS

@router.get("")
def list_factors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取所有因子（按创建时间排序）"""
    factors = db.query(Factor).order_by(Factor.created_at.desc()).all()
    return [
        {
            "id": f.id,
            "name": f.name,
            "field_type": f.field_type,
            "description": f.description or "",
            "creator_id": f.creator_id,
            "creator_name": f.creator.name if f.creator else "",
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in factors
    ]

@router.post("")
def create_factor(
    data: FactorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建因子（仅超管和维护人员）"""
    if current_user.role not in ["super_admin", "maintainer"]:
        raise HTTPException(status_code=403, detail="无权限操作")
    
    # 检查重名
    existing = db.query(Factor).filter(Factor.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="因子名称已存在")
    
    factor = Factor(
        name=data.name,
        field_type=data.field_type,
        description=data.description,
        creator_id=current_user.id,
    )
    db.add(factor)
    db.commit()
    db.refresh(factor)
    return {"id": factor.id, "name": factor.name, "field_type": factor.field_type}

@router.put("/{factor_id}")
def update_factor(
    factor_id: int,
    data: FactorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新因子"""
    if current_user.role not in ["super_admin", "maintainer"]:
        raise HTTPException(status_code=403, detail="无权限操作")
    
    factor = db.query(Factor).filter(Factor.id == factor_id).first()
    if not factor:
        raise HTTPException(status_code=404, detail="因子不存在")
    
    if data.name is not None:
        # 检查重名（排除自己）
        existing = db.query(Factor).filter(Factor.name == data.name, Factor.id != factor_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="因子名称已存在")
        factor.name = data.name
    if data.field_type is not None:
        factor.field_type = data.field_type
    if data.description is not None:
        factor.description = data.description
    
    db.commit()
    return {"message": "更新成功"}

@router.delete("/{factor_id}")
def delete_factor(
    factor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除因子"""
    if current_user.role not in ["super_admin", "maintainer"]:
        raise HTTPException(status_code=403, detail="无权限操作")
    
    factor = db.query(Factor).filter(Factor.id == factor_id).first()
    if not factor:
        raise HTTPException(status_code=404, detail="因子不存在")
    
    db.delete(factor)
    db.commit()
    return {"message": "删除成功"}
