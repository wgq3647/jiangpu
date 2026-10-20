# -*- coding: utf-8 -*-
"""
用户管理路由（仅 super_admin 可访问）
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models import User
from schemas import UserResponse, UserUpdateRole, UserUpdateStatus
from auth_utils import get_current_user, require_roles

router = APIRouter(prefix="/api/users", tags=["用户管理"])


@router.get("/", response_model=List[UserResponse], summary="获取所有用户列表")
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin")),
):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.get("/recruiters", summary="获取招聘人员列表（用于简历分配）")
def list_recruiters(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "maintainer")),
):
    """获取所有活跃的招聘人员基本信息（超管和维护人员可访问）"""
    recruiters = db.query(User).filter(
        User.role == "recruiter",
        User.status == "active"
    ).order_by(User.created_at.asc()).all()
    return [{"id": u.id, "name": u.name, "phone": u.phone} for u in recruiters]


@router.patch("/{user_id}/role", response_model=UserResponse, summary="修改用户角色")
def update_user_role(
    user_id: int,
    data: UserUpdateRole,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin")),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能修改自己的角色")
    if data.role not in ("maintainer", "recruiter"):
        raise HTTPException(status_code=400, detail="角色必须为 maintainer 或 recruiter")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.role = data.role
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/status", response_model=UserResponse, summary="启用/禁用用户")
def update_user_status(
    user_id: int,
    data: UserUpdateStatus,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin")),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能修改自己的状态")
    if data.status not in ("active", "disabled"):
        raise HTTPException(status_code=400, detail="状态必须为 active 或 disabled")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.status = data.status
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/approve", response_model=UserResponse, summary="审核通过用户注册")
def approve_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.status != "pending":
        raise HTTPException(status_code=400, detail="该用户不是待审核状态")
    user.status = "active"
    db.commit()
    db.refresh(user)
    return user
