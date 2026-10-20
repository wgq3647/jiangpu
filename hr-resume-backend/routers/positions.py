from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import json
from database import get_db
from models import Position, PositionStatus, Resume, MatchResult, SchemaField, User
from schemas import PositionCreate, PositionUpdate, PositionResponse, PositionWithFields
from auth_utils import get_current_user, require_roles
from ai_service import unified_ai_service

router = APIRouter(prefix="/api/positions", tags=["岗位管理"])

@router.get("/", response_model=List[PositionResponse], summary="获取岗位列表")
def list_positions(
    company_id: Optional[int] = None,
    status: Optional[PositionStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Position)
    if company_id:
        query = query.filter(Position.company_id == company_id)
    if status:
        query = query.filter(Position.status == status)
    positions = query.all()
    for p in positions:
        p.creator_name = p.creator.name if p.creator else None
    return positions

@router.post("/", response_model=PositionResponse, summary="新增岗位")
def create_position(position: PositionCreate, db: Session = Depends(get_db),
                    current_user: User = Depends(require_roles("super_admin", "maintainer", "recruiter"))):
    db_position = Position(**position.model_dump(), creator_id=current_user.id)
    db.add(db_position)
    db.commit()
    db.refresh(db_position)

    # 创建岗位后自动套用系统默认模板
    from models import PositionTemplate, TemplateFactor, SchemaField
    default_template = db.query(PositionTemplate).filter(PositionTemplate.is_default == True).first()
    if default_template:
        template_factors = db.query(TemplateFactor).filter(
            TemplateFactor.template_id == default_template.id
        ).order_by(TemplateFactor.sort_order).all()
        for idx, tf in enumerate(template_factors):
            factor = tf.factor
            if factor:
                schema_field = SchemaField(
                    position_id=db_position.id,
                    field_name=factor.name,
                    field_type=factor.field_type,
                    requirement="",
                    is_hard=False,
                    weight=1,
                    creator_id=current_user.id,
                    sort_order=idx + 1
                )
                db.add(schema_field)
        db.commit()
        db.refresh(db_position)

    return db_position

@router.get("/{position_id}", response_model=PositionWithFields, summary="获取岗位详情（含Schema字段）")
def get_position(position_id: int, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    position = db.query(Position).filter(Position.id == position_id).first()
    if not position:
        raise HTTPException(status_code=404, detail="岗位不存在")
    position.creator_name = position.creator.name if position.creator else None
    for sf in position.schema_fields:
        sf.creator_name = sf.creator.name if sf.creator else None
    return position

@router.put("/{position_id}", response_model=PositionResponse, summary="编辑岗位")
def update_position(position_id: int, position_update: PositionUpdate, db: Session = Depends(get_db),
                    current_user: User = Depends(require_roles("super_admin", "maintainer", "recruiter"))):
    position = db.query(Position).filter(Position.id == position_id).first()
    if not position:
        raise HTTPException(status_code=404, detail="岗位不存在")
    if current_user.role == "recruiter" and position.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作：只能编辑自己创建的岗位")
    for key, value in position_update.model_dump(exclude_unset=True).items():
        setattr(position, key, value)
    db.commit()
    db.refresh(position)
    return position

@router.patch("/{position_id}/status", response_model=PositionResponse, summary="更新岗位状态（招聘中/暂停/已满岗）")
def update_position_status(position_id: int, status: PositionStatus, db: Session = Depends(get_db),
                           current_user: User = Depends(require_roles("super_admin", "maintainer", "recruiter"))):
    position = db.query(Position).filter(Position.id == position_id).first()
    if not position:
        raise HTTPException(status_code=404, detail="岗位不存在")
    if current_user.role == "recruiter" and position.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作：只能修改自己创建的岗位状态")
    position.status = status
    db.commit()
    db.refresh(position)
    return position

@router.delete("/{position_id}", summary="删除岗位")
def delete_position(position_id: int, db: Session = Depends(get_db),
                    current_user: User = Depends(require_roles("super_admin", "maintainer", "recruiter"))):
    position = db.query(Position).filter(Position.id == position_id).first()
    if not position:
        raise HTTPException(status_code=404, detail="岗位不存在")
    if current_user.role == "recruiter" and position.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作：只能删除自己创建的岗位")
    # 级联删除：先删匹配结果 → Schema字段 → 岗位
    from models import MatchResult, SchemaField
    db.query(MatchResult).filter(MatchResult.position_id == position_id).delete(synchronize_session=False)
    db.query(SchemaField).filter(SchemaField.position_id == position_id).delete(synchronize_session=False)
    db.delete(position)
    db.commit()
    return {"message": "删除成功"}


@router.post("/{position_id}/match-all-resumes", summary="对指定岗位匹配所有简历")
def match_all_resumes_to_position(position_id: int, db: Session = Depends(get_db),
                                  current_user: User = Depends(require_roles("super_admin", "maintainer", "recruiter"))):
    """
    将所有已解析简历匹配到指定岗位
    用于新增岗位后批量匹配已有简历
    """
    position = db.query(Position).filter(Position.id == position_id).first()
    if not position:
        raise HTTPException(status_code=404, detail="岗位不存在")
    if current_user.role == "recruiter" and position.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作：只能匹配自己创建的岗位")

    # 获取该岗位的Schema字段
    schema_fields = db.query(SchemaField).filter(
        SchemaField.position_id == position_id
    ).order_by(SchemaField.sort_order).all()

    if not schema_fields:
        raise HTTPException(status_code=400, detail="该岗位尚未配置Schema字段，请先配置")

    # 获取所有已解析且有效的简历（过滤掉无效简历）
    resumes = db.query(Resume).filter(
        Resume.status == "已解析",
        Resume.business_status != "无效"
    ).all()

    if not resumes:
        raise HTTPException(status_code=400, detail="暂无已解析的简历，请先上传简历")

    company_name = position.company.name if position.company else ''

    total = len(resumes)
    matched = 0
    passed = 0
    results = []

    for resume in resumes:
        try:
            # 准备简历数据
            resume_data = {
                'candidate_name': resume.candidate_name,
                'parsed_education': resume.parsed_education,
                'parsed_experience': resume.parsed_experience,
                'parsed_skills': resume.parsed_skills,
                'parsed_industry': resume.parsed_industry,
                'parsed_projects': resume.parsed_projects,
                'parsed_certificates': resume.parsed_certificates,
            }
            if resume.parsed_fields_json:
                try:
                    resume_data['parsed_fields'] = json.loads(resume.parsed_fields_json)
                except:
                    resume_data['parsed_fields'] = {}
            else:
                resume_data['parsed_fields'] = {}

            # AI语义匹配
            match_result = unified_ai_service.match_resume_to_position(
                resume_data=resume_data,
                schema_fields=schema_fields,
                position_name=position.name,
                company_name=company_name
            )

            # 保存匹配结果（存在则更新，不存在则创建）
            existing = db.query(MatchResult).filter(
                MatchResult.resume_id == resume.id,
                MatchResult.position_id == position_id
            ).first()

            dimension_scores = match_result.get('dimension_scores', {})

            if existing:
                existing.total_score = match_result['total_score']
                existing.passed_hard = match_result['passed_hard']
                existing.reject_reason = match_result['reject_reason']
                existing.education_score = dimension_scores.get('学历', 0)
                existing.experience_score = dimension_scores.get('工作年限', 0)
                existing.skill_score = dimension_scores.get('核心技能', 0)
                existing.industry_score = dimension_scores.get('行业经验', 0)
                existing.project_score = dimension_scores.get('项目经验', 0)
                existing.certificate_score = dimension_scores.get('证书', 0)
                existing.match_details_json = json.dumps(match_result.get('match_details', []), ensure_ascii=False)
                existing.match_method = match_result.get('match_method', 'rule')
                existing.match_highlights = match_result.get('match_highlights', '')
                existing.match_gaps = match_result.get('match_gaps', '')
            else:
                new_result = MatchResult(
                    resume_id=resume.id,
                    position_id=position_id,
                    total_score=match_result['total_score'],
                    passed_hard=match_result['passed_hard'],
                    reject_reason=match_result['reject_reason'],
                    education_score=dimension_scores.get('学历', 0),
                    experience_score=dimension_scores.get('工作年限', 0),
                    skill_score=dimension_scores.get('核心技能', 0),
                    industry_score=dimension_scores.get('行业经验', 0),
                    project_score=dimension_scores.get('项目经验', 0),
                    certificate_score=dimension_scores.get('证书', 0),
                    match_details_json=json.dumps(match_result.get('match_details', []), ensure_ascii=False),
                    match_method=match_result.get('match_method', 'rule'),
                    match_highlights=match_result.get('match_highlights', ''),
                    match_gaps=match_result.get('match_gaps', '')
                )
                db.add(new_result)

            matched += 1
            if match_result['passed_hard']:
                passed += 1

            results.append({
                'resume_id': resume.id,
                'candidate_name': resume.candidate_name or resume.file_name,
                'total_score': match_result['total_score'],
                'passed_hard': match_result['passed_hard'],
                'match_method': match_result.get('match_method', 'rule')
            })

        except Exception as e:
            results.append({
                'resume_id': resume.id,
                'candidate_name': resume.candidate_name or resume.file_name,
                'error': str(e)
            })

    db.commit()

    # 按分数降序
    results.sort(key=lambda x: x.get('total_score', 0), reverse=True)

    return {
        'position_id': position_id,
        'position_name': position.name,
        'company_name': company_name,
        'total_resumes': total,
        'matched_count': matched,
        'passed_count': passed,
        'results': results
    }
