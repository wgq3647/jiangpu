from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from database import get_db
from models import PositionTemplate, TemplateFactor, Factor, User
from routers.auth import get_current_user

router = APIRouter(prefix="/api/position-templates", tags=["岗位模板"])

class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    factor_ids: List[int] = []

class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    factor_ids: Optional[List[int]] = None

class FactorIdsRequest(BaseModel):
    factor_ids: List[int]

@router.get("")
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取所有模板（含因子列表）"""
    templates = db.query(PositionTemplate).order_by(PositionTemplate.created_at.desc()).all()
    result = []
    for t in templates:
        factors = []
        for tf in sorted(t.template_factors, key=lambda x: x.sort_order):
            factors.append({
                "id": tf.factor.id,
                "name": tf.factor.name,
                "field_type": tf.factor.field_type,
                "description": tf.factor.description or "",
            })
        result.append({
            "id": t.id,
            "name": t.name,
            "description": t.description or "",
            "creator_id": t.creator_id,
            "creator_name": t.creator.name if t.creator else "",
            "factor_count": len(t.template_factors),
            "factors": factors,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })
    return result

@router.get("/{template_id}")
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取单个模板详情"""
    t = db.query(PositionTemplate).filter(PositionTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    factors = []
    for tf in sorted(t.template_factors, key=lambda x: x.sort_order):
        factors.append({
            "id": tf.factor.id,
            "name": tf.factor.name,
            "field_type": tf.factor.field_type,
            "description": tf.factor.description or "",
        })
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description or "",
        "factor_count": len(t.template_factors),
        "factors": factors,
    }

@router.post("")
def create_template(
    data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建模板（仅超管和维护人员）"""
    if current_user.role not in ["super_admin", "maintainer"]:
        raise HTTPException(status_code=403, detail="无权限操作")
    
    # 检查重名
    existing = db.query(PositionTemplate).filter(PositionTemplate.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="模板名称已存在")
    
    template = PositionTemplate(
        name=data.name,
        description=data.description,
        creator_id=current_user.id,
    )
    db.add(template)
    db.flush()
    
    # 添加因子关联
    for idx, factor_id in enumerate(data.factor_ids):
        factor = db.query(Factor).filter(Factor.id == factor_id).first()
        if factor:
            tf = TemplateFactor(template_id=template.id, factor_id=factor_id, sort_order=idx)
            db.add(tf)
    
    db.commit()
    db.refresh(template)
    return {"id": template.id, "name": template.name, "message": "创建成功"}

@router.put("/{template_id}")
def update_template(
    template_id: int,
    data: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新模板（含因子列表替换）"""
    if current_user.role not in ["super_admin", "maintainer"]:
        raise HTTPException(status_code=403, detail="无权限操作")
    
    template = db.query(PositionTemplate).filter(PositionTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    if data.name is not None:
        existing = db.query(PositionTemplate).filter(
            PositionTemplate.name == data.name,
            PositionTemplate.id != template_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="模板名称已存在")
        template.name = data.name
    
    if data.description is not None:
        template.description = data.description
    
    # 如果提供了factor_ids，替换所有因子关联
    if data.factor_ids is not None:
        # 删除旧关联
        db.query(TemplateFactor).filter(TemplateFactor.template_id == template_id).delete()
        # 添加新关联
        for idx, factor_id in enumerate(data.factor_ids):
            factor = db.query(Factor).filter(Factor.id == factor_id).first()
            if factor:
                tf = TemplateFactor(template_id=template.id, factor_id=factor_id, sort_order=idx)
                db.add(tf)
    
    db.commit()
    return {"message": "更新成功"}

@router.delete("/{template_id}")
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除模板"""
    if current_user.role not in ["super_admin", "maintainer"]:
        raise HTTPException(status_code=403, detail="无权限操作")
    
    template = db.query(PositionTemplate).filter(PositionTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    if template.is_default:
        raise HTTPException(status_code=400, detail="系统默认模板不可删除")
    
    db.delete(template)
    db.commit()
    return {"message": "删除成功"}

@router.post("/{template_id}/factors")
def add_factors_to_template(
    template_id: int,
    data: FactorIdsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """向模板添加因子（追加，不替换）"""
    if current_user.role not in ["super_admin", "maintainer"]:
        raise HTTPException(status_code=403, detail="无权限操作")
    
    template = db.query(PositionTemplate).filter(PositionTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    # 获取当前最大排序
    max_order = db.query(TemplateFactor).filter(
        TemplateFactor.template_id == template_id
    ).count()
    
    added = 0
    for factor_id in data.factor_ids:
        # 检查是否已存在
        existing = db.query(TemplateFactor).filter(
            TemplateFactor.template_id == template_id,
            TemplateFactor.factor_id == factor_id
        ).first()
        if existing:
            continue
        factor = db.query(Factor).filter(Factor.id == factor_id).first()
        if factor:
            tf = TemplateFactor(template_id=template_id, factor_id=factor_id, sort_order=max_order + added)
            db.add(tf)
            added += 1
    
    db.commit()
    return {"message": f"成功添加{added}个因子"}

@router.delete("/{template_id}/factors/{factor_id}")
def remove_factor_from_template(
    template_id: int,
    factor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """从模板移除单个因子"""
    if current_user.role not in ["super_admin", "maintainer"]:
        raise HTTPException(status_code=403, detail="无权限操作")
    
    tf = db.query(TemplateFactor).filter(
        TemplateFactor.template_id == template_id,
        TemplateFactor.factor_id == factor_id
    ).first()
    if not tf:
        raise HTTPException(status_code=404, detail="关联不存在")
    
    db.delete(tf)
    db.commit()
    return {"message": "移除成功"}
