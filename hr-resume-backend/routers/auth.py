# -*- coding: utf-8 -*-
"""
认证路由：注册、登录、获取当前用户
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import UserRegister, UserLogin, UserResponse, TokenResponse
from auth_utils import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", summary="用户注册")
def register(data: UserRegister, db: Session = Depends(get_db)):
    # 手机号唯一校验
    existing = db.query(User).filter(User.phone == data.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="该手机号已被注册")

    # 维护人员注册：需审核，状态 pending，不返回 token
    if data.role == "maintainer":
        user = User(
            phone=data.phone,
            password_hash=hash_password(data.password),
            name=data.name,
            role="maintainer",
            status="pending",
        )
        db.add(user)
        db.commit()
        return {
            "access_token": "",
            "token_type": "bearer",
            "user": UserResponse.model_validate(user).model_dump(),
            "requires_approval": True,
            "message": "维护人员注册申请已提交，等待超级管理员审核开通"
        }

    # 招聘人员注册：直接激活，返回 token 自动登录
    user = User(
        phone=data.phone,
        password_hash=hash_password(data.password),
        name=data.name,
        role="recruiter",
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    ).model_dump()


@router.post("/login", response_model=TokenResponse, summary="用户登录")
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == data.phone).first()
    if not user:
        raise HTTPException(status_code=401, detail="手机号或密码错误")
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="手机号或密码错误")
    if user.status == "pending":
        raise HTTPException(status_code=403, detail="账号待审核，请联系管理员开通")
    if user.status == "disabled":
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse, summary="获取当前登录用户信息")
def me(current_user: User = Depends(get_current_user)):
    return current_user
