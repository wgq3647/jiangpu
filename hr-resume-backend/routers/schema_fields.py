from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import SchemaField, User, Position
import matching_runner
from schemas import SchemaFieldCreate, SchemaFieldUpdate, SchemaFieldResponse, SchemaBatchSave
from auth_utils import get_current_user, require_roles

router = APIRouter(prefix="/api/schema-fields", tags=["Schema字段管理"])

@router.get("/", response_model=List[SchemaFieldResponse], summary="获取Schema字段列表")
def list_schema_fields(position_id: int, db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    fields = db.query(SchemaField).filter(SchemaField.position_id == position_id).order_by(SchemaField.sort_order).all()
    for f in fields:
        f.creator_name = f.creator.name if f.creator else None
    return fields

@router.post("/", response_model=SchemaFieldResponse, summary="新增Schema字段")
def create_schema_field(field: SchemaFieldCreate, db: Session = Depends(get_db),
                        current_user: User = Depends(require_roles("super_admin", "maintainer", "recruiter"))):
    db_field = SchemaField(**field.model_dump(), creator_id=current_user.id)
    db.add(db_field)
    db.commit()
    db.refresh(db_field)
    db_field.creator_name = db_field.creator.name if db_field.creator else None
    return db_field

@router.put("/{field_id}", response_model=SchemaFieldResponse, summary="编辑Schema字段")
def update_schema_field(field_id: int, field_update: SchemaFieldUpdate, db: Session = Depends(get_db),
                        current_user: User = Depends(require_roles("super_admin", "maintainer", "recruiter"))):
    field = db.query(SchemaField).filter(SchemaField.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="字段不存在")
    if current_user.role == "recruiter" and field.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作：只能编辑自己创建的Schema字段")
    for key, value in field_update.model_dump(exclude_unset=True).items():
        setattr(field, key, value)
    db.commit()
    db.refresh(field)
    return field

@router.delete("/{field_id}", summary="删除Schema字段")
def delete_schema_field(field_id: int, db: Session = Depends(get_db),
                       current_user: User = Depends(require_roles("super_admin", "maintainer", "recruiter"))):
    field = db.query(SchemaField).filter(SchemaField.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="字段不存在")
    if current_user.role == "recruiter" and field.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作：只能删除自己创建的Schema字段")
    db.delete(field)
    db.commit()
    return {"message": "删除成功"}

@router.post("/batch/{position_id}", response_model=List[SchemaFieldResponse], summary="批量初始化岗位Schema字段")
def init_schema_fields(position_id: int, db: Session = Depends(get_db),
                      current_user: User = Depends(require_roles("super_admin", "maintainer", "recruiter"))):
    """为岗位批量初始化默认Schema字段（学历、年限、技能、行业、项目、证书）"""
    position = db.query(Position).filter(Position.id == position_id).first()
    if not position:
        raise HTTPException(status_code=404, detail="岗位不存在")
    if current_user.role == "recruiter" and position.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作：只能初始化自己创建的岗位的Schema")
    default_fields = [
        {"field_name": "学历", "field_type": "枚举", "requirement": "本科及以上", "is_hard": True, "weight": 10, "sort_order": 1},
        {"field_name": "工作年限", "field_type": "数字", "requirement": "3年以上", "is_hard": False, "weight": 10, "sort_order": 2},
        {"field_name": "核心技能", "field_type": "多选", "requirement": "Python, SQL", "is_hard": False, "weight": 12, "sort_order": 3},
        {"field_name": "行业经验", "field_type": "单选", "requirement": "互联网 / 金融", "is_hard": False, "weight": 8, "sort_order": 4},
        {"field_name": "项目经历", "field_type": "多选", "requirement": "数据平台, 用户增长", "is_hard": False, "weight": 9, "sort_order": 5},
        {"field_name": "证书", "field_type": "多选", "requirement": "NPDP, PMP", "is_hard": False, "weight": 7, "sort_order": 6},
    ]
    result = []
    for f in default_fields:
        db_field = SchemaField(position_id=position_id, creator_id=current_user.id, **f)
        db.add(db_field)
        result.append(db_field)
    db.commit()
    for r in result:
        db.refresh(r)
        r.creator_name = r.creator.name if r.creator else None
    return result


@router.put("/batch-save/{position_id}", response_model=List[SchemaFieldResponse], summary="批量保存Schema配置（全量更新，保存后自动匹配所有简历）")
def batch_save_schema_fields(
    position_id: int,
    payload: SchemaBatchSave,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "maintainer", "recruiter"))
):
    """
    全量保存岗位的Schema配置：
    - 有id的字段：更新
    - 无id的字段：新增
    - 不在列表中的旧字段：删除
    保存成功后，后台自动对所有已解析简历执行匹配
    """
    position = db.query(Position).filter(Position.id == position_id).first()
    if not position:
        raise HTTPException(status_code=404, detail="岗位不存在")

    # 维护人员/招聘人员只能保存自己创建的岗位的Schema
    if current_user.role == "recruiter" and position.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作：只能编辑自己创建的岗位的Schema")

    incoming_ids = set()
    result_fields = []

    for idx, item in enumerate(payload.fields):
        if item.id:
            # 更新已有字段
            field = db.query(SchemaField).filter(
                SchemaField.id == item.id,
                SchemaField.position_id == position_id
            ).first()
            if field:
                field.field_name = item.field_name
                field.field_type = item.field_type
                field.requirement = item.requirement
                field.is_hard = item.is_hard
                field.weight = item.weight
                field.sort_order = item.sort_order
                incoming_ids.add(field.id)
                result_fields.append(field)
            else:
                # id不存在，按新增处理
                new_field = SchemaField(
                    position_id=position_id,
                    creator_id=current_user.id,
                    field_name=item.field_name,
                    field_type=item.field_type,
                    requirement=item.requirement,
                    is_hard=item.is_hard,
                    weight=item.weight,
                    sort_order=item.sort_order
                )
                db.add(new_field)
                result_fields.append(new_field)
        else:
            # 新增字段
            new_field = SchemaField(
                position_id=position_id,
                creator_id=current_user.id,
                field_name=item.field_name,
                field_type=item.field_type,
                requirement=item.requirement,
                is_hard=item.is_hard,
                weight=item.weight,
                sort_order=item.sort_order
            )
            db.add(new_field)
            result_fields.append(new_field)

    # 删除不在列表中的旧字段
    existing_fields = db.query(SchemaField).filter(SchemaField.position_id == position_id).all()
    for ef in existing_fields:
        if ef.id not in incoming_ids:
            db.delete(ef)

    db.commit()

    # 刷新并设置creator_name
    for f in result_fields:
        db.refresh(f)
        f.creator_name = f.creator.name if f.creator else None

    # 保存成功后，后台自动匹配所有已解析简历
    background_tasks.add_task(matching_runner.run_match_for_position, position_id)

    return result_fields
