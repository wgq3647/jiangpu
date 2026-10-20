from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from database import get_db
from models import Company, User, Position
from schemas import CompanyCreate, CompanyUpdate, CompanyResponse, CompanyWithPositions
from auth_utils import get_current_user, require_roles

router = APIRouter(prefix="/api/companies", tags=["公司管理"])

@router.get("/", response_model=List[CompanyResponse], summary="获取公司列表（未删除）")
def list_companies(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    companies = db.query(Company).filter(Company.is_deleted == False).all()
    for c in companies:
        c.creator_name = c.creator.name if c.creator else None
    return companies

@router.get("/deleted", response_model=List[CompanyResponse], summary="获取已删除公司列表")
def list_deleted_companies(db: Session = Depends(get_db), current_user: User = Depends(require_roles("super_admin", "maintainer"))):
    companies = db.query(Company).filter(Company.is_deleted == True).all()
    for c in companies:
        c.creator_name = c.creator.name if c.creator else None
    return companies

@router.post("/", response_model=CompanyResponse, summary="新增公司")
def create_company(company: CompanyCreate, db: Session = Depends(get_db),
                  current_user: User = Depends(require_roles("super_admin", "maintainer", "recruiter"))):
    db_company = Company(**company.model_dump(), creator_id=current_user.id)
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    return db_company

@router.get("/{company_id}", response_model=CompanyWithPositions, summary="获取公司详情（含岗位）")
def get_company(company_id: int, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="公司不存在")
    company.creator_name = company.creator.name if company.creator else None
    return company

@router.put("/{company_id}", response_model=CompanyResponse, summary="编辑公司")
def update_company(company_id: int, company_update: CompanyUpdate, db: Session = Depends(get_db),
                   current_user: User = Depends(require_roles("super_admin", "maintainer", "recruiter"))):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="公司不存在")
    if current_user.role == "recruiter" and company.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作：只能编辑自己创建的公司")
    for key, value in company_update.model_dump(exclude_unset=True).items():
        setattr(company, key, value)
    db.commit()
    db.refresh(company)
    return company

@router.delete("/{company_id}", summary="删除公司（软删除，前置检查招聘中岗位）")
def delete_company(company_id: int, db: Session = Depends(get_db),
                   current_user: User = Depends(require_roles("super_admin", "maintainer", "recruiter"))):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="公司不存在")
    if company.is_deleted:
        raise HTTPException(status_code=400, detail="公司已被删除")
    if current_user.role == "recruiter" and company.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作：只能删除自己创建的公司")
    
    # 前置检查：是否有招聘中的岗位
    recruiting_positions = db.query(Position).filter(
        Position.company_id == company_id,
        Position.status == "招聘中"
    ).all()
    if recruiting_positions:
        position_names = [p.name for p in recruiting_positions]
        raise HTTPException(
            status_code=400,
            detail=f"该公司下有 {len(recruiting_positions)} 个招聘中岗位（{', '.join(position_names)}），请先将这些岗位改为非招聘中状态后再删除公司"
        )
    
    # 软删除
    company.is_deleted = True
    company.deleted_at = datetime.now()
    db.commit()
    return {"message": "删除成功（已移入回收站，可恢复）"}

@router.post("/{company_id}/restore", summary="恢复已删除公司")
def restore_company(company_id: int, db: Session = Depends(get_db),
                    current_user: User = Depends(require_roles("super_admin", "maintainer"))):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="公司不存在")
    if not company.is_deleted:
        raise HTTPException(status_code=400, detail="公司未被删除，无需恢复")
    
    # 恢复
    company.is_deleted = False
    company.deleted_at = None
    db.commit()
    return {"message": "公司恢复成功"}
