# -*- coding: utf-8 -*-
"""
系统热配置路由（仅 super_admin 可访问）
支持AI API Key、提供商、开关等配置的运行时修改
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Optional
from pydantic import BaseModel

from database import get_db
from models import SystemConfig, User
from auth_utils import require_roles

router = APIRouter(prefix="/api/system-config", tags=["系统配置"])


class ConfigUpdateRequest(BaseModel):
    configs: Dict[str, str]


@router.get("", summary="获取所有系统配置")
def get_all_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin"))
):
    """获取所有系统配置项（API Key等敏感值不脱敏，仅超管可访问）"""
    configs = db.query(SystemConfig).order_by(SystemConfig.id).all()
    return {
        c.config_key: {
            "value": c.config_value,
            "description": c.description,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None
        }
        for c in configs
    }


@router.put("", summary="批量更新系统配置")
def update_configs(
    body: ConfigUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin"))
):
    """批量更新配置项，不存在的键会被忽略"""
    updated = []
    for key, value in body.configs.items():
        config = db.query(SystemConfig).filter(SystemConfig.config_key == key).first()
        if config:
            config.config_value = str(value) if value is not None else None
            updated.append(key)
    db.commit()
    return {"message": f"成功更新 {len(updated)} 项配置", "updated_keys": updated}


@router.get("/ai-status", summary="获取AI服务状态（公开）")
def get_ai_status(db: Session = Depends(get_db)):
    """获取AI服务当前状态（不需要登录，用于前端显示）"""
    from ai.config import AIConfig
    AIConfig.load_from_db(db)
    config = AIConfig.get_provider_config()
    return {
        "enabled": AIConfig.ENABLED,
        "provider": AIConfig.PROVIDER,
        "provider_name": config.get("name", ""),
        "configured": AIConfig.is_configured(),
        "model": config.get("model", ""),
        "has_api_key": bool(config.get("api_key"))
    }
