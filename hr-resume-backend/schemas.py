from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from models import PositionStatus, FieldType
import re

# ========== User ==========
class UserRegister(BaseModel):
    phone: str = Field(..., description="手机号")
    password: str = Field(..., description="密码")
    confirm_password: str = Field(..., description="确认密码")
    name: Optional[str] = Field(None, description="姓名")
    role: str = Field("recruiter", description="申请角色：recruiter/maintainer")

    @validator("phone")
    def validate_phone(cls, v):
        if not re.match(r"^1\d{10}$", v):
            raise ValueError("手机号格式不正确，应为11位数字且以1开头")
        return v

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError("密码至少6位")
        return v

    @validator("confirm_password")
    def validate_confirm(cls, v, values):
        if "password" in values and v != values["password"]:
            raise ValueError("两次输入的密码不一致")
        return v

    @validator("role")
    def validate_role(cls, v):
        if v not in ("recruiter", "maintainer"):
            raise ValueError("角色只能是 recruiter 或 maintainer")
        return v

class UserLogin(BaseModel):
    phone: str = Field(..., description="手机号")
    password: str = Field(..., description="密码")

class UserResponse(BaseModel):
    id: int
    phone: str
    name: Optional[str]
    role: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class UserUpdateRole(BaseModel):
    role: str = Field(..., description="目标角色：maintainer/recruiter")

class UserUpdateStatus(BaseModel):
    status: str = Field(..., description="目标状态：active/disabled")

# ========== Company ==========
class CompanyBase(BaseModel):
    name: str = Field(..., description="公司名称")
    description: Optional[str] = Field(None, description="公司描述")
    status: str = Field("合作中", description="合作状态")
    email: Optional[str] = Field(None, description="公司接收简历邮箱")
    city: Optional[str] = Field(None, description="所在城市")
    address: Optional[str] = Field(None, description="详细地址")

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None

class CompanyResponse(CompanyBase):
    id: int
    creator_id: Optional[int] = None
    creator_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# ========== Position ==========
class PositionBase(BaseModel):
    name: str = Field(..., description="岗位名称")
    description: Optional[str] = Field(None, description="岗位描述")
    status: PositionStatus = Field(PositionStatus.RECRUITING, description="岗位状态")
    headcount: int = Field(1, description="招聘人数")
    work_locations: Optional[str] = Field(None, description="工作地区（多选，逗号分隔）")

class PositionCreate(PositionBase):
    company_id: int = Field(..., description="所属公司ID")

class PositionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[PositionStatus] = None
    headcount: Optional[int] = None
    work_locations: Optional[str] = None

class PositionResponse(PositionBase):
    id: int
    company_id: int
    creator_id: Optional[int] = None
    creator_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# ========== SchemaField ==========
class SchemaFieldBase(BaseModel):
    field_name: str = Field(..., description="字段名称")
    field_type: FieldType = Field(..., description="字段类型")
    requirement: str = Field(..., description="匹配要求")
    is_hard: bool = Field(False, description="是否硬性淘汰")
    weight: int = Field(10, ge=0, le=100, description="匹配权重")
    sort_order: int = Field(0, description="排序")

class SchemaFieldCreate(SchemaFieldBase):
    position_id: int = Field(..., description="所属岗位ID")

class SchemaFieldUpdate(BaseModel):
    field_name: Optional[str] = None
    field_type: Optional[FieldType] = None
    requirement: Optional[str] = None
    is_hard: Optional[bool] = None
    weight: Optional[int] = Field(None, ge=0, le=100)
    sort_order: Optional[int] = None

class SchemaFieldBatchItem(BaseModel):
    id: Optional[int] = None
    field_name: str
    field_type: FieldType
    requirement: str
    is_hard: bool = False
    weight: int = Field(10, ge=0, le=100)
    sort_order: int = 0

class SchemaBatchSave(BaseModel):
    fields: List[SchemaFieldBatchItem]

class SchemaFieldResponse(SchemaFieldBase):
    id: int
    position_id: int
    creator_id: Optional[int] = None
    creator_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# ========== 联合响应 ==========
class PositionWithFields(PositionResponse):
    schema_fields: List[SchemaFieldResponse] = []

class CompanyWithPositions(CompanyResponse):
    positions: List[PositionResponse] = []
