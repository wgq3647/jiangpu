from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import json
import logging

from database import get_db, SessionLocal
from models import Resume, MatchResult, Position, SchemaField, PositionStatus, User, Company
from auth_utils import get_current_user, require_roles
from ai_service import unified_ai_service
from ai import AIConfig
from file_parser import FileParser, FileParseError, is_pdf_image_recognition_enabled
from batch_manager import batch_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resumes", tags=["简历管理"])

# ========== Pydantic Schemas ==========
class ResumeResponse(BaseModel):
    id: int
    file_name: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    candidate_name: Optional[str]
    parsed_education: Optional[str]
    parsed_experience: Optional[int]
    parsed_skills: Optional[str]
    parsed_industry: Optional[str]
    parsed_certificates: Optional[str]
    parsed_fields_json: Optional[str]
    parse_method: Optional[str]
    status: str
    business_status: Optional[str] = '有效'
    routing_paused: Optional[bool] = False
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    duplicate_of_id: Optional[int] = None
    duplicate_of_name: Optional[str] = None
    duplicate_of_owner: Optional[str] = None
    matched_count: Optional[int] = 0
    matched_positions: Optional[list] = []
    created_at: datetime

    class Config:
        from_attributes = True

class ReassignOwnerRequest(BaseModel):
    owner_id: int

class BatchReassignRequest(BaseModel):
    resume_ids: List[int]
    owner_id: int

class MatchResultResponse(BaseModel):
    id: int
    resume_id: int
    position_id: int
    total_score: int
    passed_hard: bool
    reject_reason: Optional[str]
    education_score: int
    experience_score: int
    skill_score: int
    industry_score: int
    project_score: int
    certificate_score: int
    match_details_json: Optional[str]
    match_method: Optional[str]
    match_highlights: Optional[str]
    match_gaps: Optional[str]
    sent_to_company: Optional[bool] = False
    sent_at: Optional[datetime] = None
    sent_by: Optional[int] = None
    interview_scheduled: Optional[bool] = False
    interview_scheduled_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True

class MatchResultWithDetail(MatchResultResponse):
    resume_name: Optional[str] = None
    position_name: Optional[str] = None
    company_name: Optional[str] = None

class BatchUploadResponse(BaseModel):
    uploaded: int
    parsed: int
    failed: int
    resume_ids: List[int]
    parse_method: str

class TextResumeUpload(BaseModel):
    file_name: str
    content: str

class AIStatusResponse(BaseModel):
    ai_enabled: bool
    ai_configured: bool
    provider: str
    model: str

class BatchTaskResponse(BaseModel):
    task_id: str
    file_name: str
    file_size: int
    status: str
    progress: int
    error: str
    resume_id: Optional[int]
    parse_method: str
    retry_count: int

class BatchJobResponse(BaseModel):
    batch_id: str
    total_files: int
    success_count: int
    failed_count: int
    pending_count: int
    status: str
    overall_progress: int
    tasks: List[BatchTaskResponse]

# ========== 后台批量处理函数 ==========
def _process_single_file(batch_id: str, task_id: str, file_bytes: bytes, file_name: str, owner_id: int = None):
    """后台处理单个文件：解析文本 -> AI语义解析 -> 保存数据库"""
    db = SessionLocal()
    try:
        # 更新状态为解析中
        batch_manager.update_task(batch_id, task_id, status="parsing", progress=10)

        # 0. 检查PDF和图片识别功能开关
        file_type_check = FileParser.get_file_type(file_name)
        if file_type_check in ('pdf', 'image') and not is_pdf_image_recognition_enabled(db):
            error_msg = f"该文件格式（{file_type_check}）识别功能已关闭，暂不支持解析，请上传Word或文本格式简历"
            logger.warning(f"{file_name}: {error_msg}")
            batch_manager.update_task(batch_id, task_id, status="failed", progress=0, error=error_msg)
            return

        # 1. 文件解析（PDF/Word/图片/文本）
        try:
            text, file_type = FileParser.parse(file_bytes, file_name)
            batch_manager.update_task(batch_id, task_id, progress=40)
        except FileParseError as e:
            error_msg = f"文件解析失败: {str(e)}"
            logger.warning(f"{file_name}: {error_msg}")
            batch_manager.update_task(batch_id, task_id, status="failed", progress=0, error=error_msg)
            return
        except Exception as e:
            error_msg = f"文件解析异常: {str(e)}"
            logger.error(f"{file_name}: {error_msg}")
            batch_manager.update_task(batch_id, task_id, status="failed", progress=0, error=error_msg)
            return

        # 2. 简历去重（基于内容哈希，全局去重：内容相同即禁止上传）
        import hashlib
        content_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        existing = db.query(Resume).filter(Resume.content_hash == content_hash).first()
        if existing:
            owner_name = existing.owner.name if existing.owner else '未知'
            batch_manager.update_task(
                batch_id, task_id, status="failed", progress=0,
                error=f"重复简历：该简历内容已由「{owner_name}」上传（resume_id={existing.id}），无需重复上传",
                parse_method="duplicate"
            )
            logger.info(f"{file_name} 与 resume_id={existing.id} 内容重复，已拒绝上传")
            return

        # 3. AI语义解析（AI优先，降级规则引擎）
        batch_manager.update_task(batch_id, task_id, progress=60)
        all_schema_fields = db.query(SchemaField).all()
        parsed_data = unified_ai_service.parse_resume(text, all_schema_fields)
        parse_method = parsed_data.get('parse_method', 'rule')
        batch_manager.update_task(batch_id, task_id, progress=85)

        # 4. 简历有效性校验
        candidate_name = parsed_data.get('candidate_name')
        logger.info(f"[简历校验] 文件={file_name}, 候选人姓名={candidate_name}, 文本长度={len(text)}, 文本前100字={text[:100]}")
        is_valid_resume, invalid_reason = _validate_resume_content(text, candidate_name)
        logger.info(f"[简历校验] 文件={file_name}, 校验结果: valid={is_valid_resume}, reason={invalid_reason}")

        # 无效简历不落库，直接返回失败
        if not is_valid_resume:
            batch_manager.update_task(
                batch_id, task_id, status="failed", progress=0,
                error=f"非简历文件：{invalid_reason}",
                parse_method=parse_method
            )
            logger.info(f"{file_name} 被识别为非简历文件，不落库。原因={invalid_reason}")
            return

        # 5. 保存到数据库（仅有效简历）
        task_info = batch_manager.get_task(batch_id, task_id)
        file_size = task_info.file_size if task_info else len(file_bytes)
        file_type = FileParser.get_file_type(file_name) or 'unknown'
        resume = Resume(
            file_name=file_name,
            file_size=file_size,
            file_type=file_type,
            raw_text=text[:5000],
            status="已解析",
            business_status="有效",
            owner_id=owner_id,
            content_hash=content_hash
        )
        _save_resume_parsed(resume, parsed_data)
        db.add(resume)
        db.commit()
        db.refresh(resume)

        # 完成
        batch_manager.update_task(
            batch_id, task_id, status="success", progress=100,
            resume_id=resume.id, parse_method=parse_method
        )
        logger.info(f"{file_name} 解析完成，resume_id={resume.id}, 方式={parse_method}")

    except Exception as e:
        error_msg = f"处理异常: {str(e)}"
        logger.error(f"{file_name}: {error_msg}", exc_info=True)
        batch_manager.update_task(batch_id, task_id, status="failed", progress=0, error=error_msg)
    finally:
        db.close()


def _process_batch_files(batch_id: str, file_data_list: List[dict], owner_id: int = None):
    """后台批量处理所有文件（顺序处理，便于进度跟踪）"""
    for file_data in file_data_list:
        _process_single_file(
            batch_id=batch_id,
            task_id=file_data["task_id"],
            file_bytes=file_data["file_bytes"],
            file_name=file_data["file_name"],
            owner_id=owner_id
        )

# ========== 辅助函数 ==========
def _get_all_schema_fields(db: Session) -> List[SchemaField]:
    """获取所有岗位的所有Schema字段（用于解析时覆盖所有可能的字段）"""
    return db.query(SchemaField).all()

def _validate_resume_content(text: str, candidate_name: str = None) -> tuple:
    """
    校验文本内容是否为有效简历
    返回: (is_valid: bool, invalid_reason: str)
    """
    import re

    # 检查1：非简历特征检测（网盘链接、纯URL等明显非简历内容）
    non_resume_indicators = [
        'pan.baidu.com', '百度网盘', '提取码', '阿里云盘', 'alipan',
        'quark.cn', '夸克网盘', 'lanzou', '蓝奏云', '123pan',
        '115.com', '115网盘', 'weiyun', '微云', 'jianguoyun', '坚果云',
        'mega.nz', 'mediafire', 'dropbox.com', 'drive.google.com',
    ]
    text_lower = text.lower()
    for indicator in non_resume_indicators:
        if indicator.lower() in text_lower:
            return False, f"文件内容包含网盘分享链接（{indicator}），该文件不是简历"

    # 检查2：内容是否主要是URL链接（URL占比超过60%）
    if len(text.strip()) > 0:
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, text)
        url_total_length = sum(len(u) for u in urls)
        if url_total_length / len(text.strip()) > 0.6:
            return False, "文件内容主要是URL链接，该文件不是简历"

    # 检查3：是否解析到候选人姓名
    if not candidate_name or not candidate_name.strip():
        return False, "无法识别候选人姓名，该文件可能不是有效简历"

    # 检查4：文本内容是否包含简历常见特征
    resume_keywords = ['姓名', '教育', '工作经历', '工作经验', '项目经验', '项目经历',
                      '技能', '求职意向', '自我评价', '证书', '学历', '专业', '毕业院校',
                      '联系方式', '电话', '邮箱', '籍贯', '出生', '年龄', '性别']
    keyword_count = sum(1 for kw in resume_keywords if kw in text)
    if keyword_count < 3:
        return False, f"文件内容仅包含{keyword_count}个简历相关信息，缺少教育/工作经历/技能等简历核心要素，该文件可能不是有效简历"

    # 检查5：文本长度过短（少于30字）
    if len(text.strip()) < 30:
        return False, "文件内容过短，无法识别为有效简历"

    return True, ""

def _save_resume_parsed(resume: Resume, parsed_data: dict):
    """将解析结果保存到简历对象"""
    resume.candidate_name = parsed_data.get('candidate_name')
    resume.parsed_education = parsed_data.get('parsed_education')
    resume.parsed_experience = parsed_data.get('parsed_experience')
    resume.parsed_skills = parsed_data.get('parsed_skills')
    resume.parsed_industry = parsed_data.get('parsed_industry')
    resume.parsed_projects = parsed_data.get('parsed_projects')
    resume.parsed_certificates = parsed_data.get('parsed_certificates')
    # 保存所有字段的完整解析结果
    parsed_fields = parsed_data.get('parsed_fields', {})
    resume.parsed_fields_json = json.dumps(parsed_fields, ensure_ascii=False)
    resume.parse_method = parsed_data.get('parse_method', 'rule')

def _resume_to_dict(resume: Resume) -> dict:
    """将简历对象转换为匹配引擎需要的字典格式"""
    result = {
        'candidate_name': resume.candidate_name,
        'parsed_education': resume.parsed_education,
        'parsed_experience': resume.parsed_experience,
        'parsed_skills': resume.parsed_skills,
        'parsed_industry': resume.parsed_industry,
        'parsed_projects': resume.parsed_projects,
        'parsed_certificates': resume.parsed_certificates,
    }
    # 加载完整的parsed_fields
    if resume.parsed_fields_json:
        try:
            result['parsed_fields'] = json.loads(resume.parsed_fields_json)
        except:
            result['parsed_fields'] = {}
    else:
        result['parsed_fields'] = {}
    return result

# ========== API Endpoints ==========

@router.get("/ai/status", response_model=AIStatusResponse, summary="获取AI服务状态")
def get_ai_status(current_user: User = Depends(get_current_user)):
    config = AIConfig.get_provider_config()
    return {
        "ai_enabled": AIConfig.ENABLED,
        "ai_configured": AIConfig.is_configured(),
        "provider": config["name"],
        "model": config["model"]
    }


@router.post("/upload", summary="批量上传简历（支持PDF/Word/图片，异步队列处理）")
async def upload_resumes(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    批量上传简历文件，支持PDF/Word/图片/文本格式
    创建异步处理任务，立即返回batch_id，前端轮询进度
    """
    if not files:
        raise HTTPException(status_code=400, detail="请选择要上传的文件")

    # 检查文件格式
    unsupported = []
    file_infos = []
    for f in files:
        if not FileParser.is_supported(f.filename):
            unsupported.append(f.filename)
        else:
            file_infos.append({"file_name": f.filename, "file_size": f.size or 0})

    if unsupported:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {', '.join(unsupported)}")

    # 创建批量任务
    batch_id = batch_manager.create_batch(file_infos)

    # 读取所有文件内容（在请求线程中读取，避免后台任务引用已关闭的文件）
    job = batch_manager.get_job(batch_id)
    file_data_list = []
    for i, file in enumerate(files):
        content = await file.read()
        task_id = list(job.tasks.keys())[i]
        file_data_list.append({
            "task_id": task_id,
            "file_name": file.filename,
            "file_bytes": content
        })

    # 启动后台处理
    background_tasks.add_task(_process_batch_files, batch_id, file_data_list, current_user.id)

    return {
        "batch_id": batch_id,
        "total_files": len(files),
        "message": "上传成功，正在后台解析中，请轮询 /api/resumes/batch/{batch_id} 获取进度"
    }


@router.get("/batch/{batch_id}", response_model=BatchJobResponse, summary="获取批量任务进度")
def get_batch_status(batch_id: str, current_user: User = Depends(get_current_user)):
    """查询批量上传任务的处理进度和各文件状态"""
    job = batch_manager.get_job(batch_id)
    if not job:
        raise HTTPException(status_code=404, detail="批量任务不存在")
    return job.to_dict()


@router.post("/batch/{batch_id}/retry/{task_id}", summary="重试单个失败任务")
async def retry_single_task(
    batch_id: str,
    task_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """重新解析单个失败的简历文件"""
    task = batch_manager.get_task(batch_id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 重试需要原始文件内容，但我们没有保存文件内容到内存
    # 这里提示用户重新上传，或者从已保存的resume记录中重新解析
    if task.resume_id:
        # 如果已经有resume_id，重新解析（从数据库取raw_text）
        resume = db.query(Resume).filter(Resume.id == task.resume_id).first()
        if resume and resume.raw_text:
            # 重置任务状态
            batch_manager.update_task(batch_id, task_id, status="pending", progress=0, error="", retry_count=task.retry_count + 1)
            # 后台重新解析（用文本方式）
            all_schema_fields = db.query(SchemaField).all()
            parsed_data = unified_ai_service.parse_resume(resume.raw_text, all_schema_fields)
            _save_resume_parsed(resume, parsed_data)
            db.commit()
            batch_manager.update_task(batch_id, task_id, status="success", progress=100, parse_method=parsed_data.get('parse_method', 'rule'))
            return {"message": "重新解析成功", "task_id": task_id}

    return {"message": "该任务无法重试（原始文件已丢失），请重新上传该简历", "task_id": task_id}


@router.post("/batch/{batch_id}/retry-all", summary="重试所有失败任务")
def retry_all_failed(batch_id: str, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    """批量重试所有失败的任务（仅对有resume_id记录的有效）"""
    job = batch_manager.get_job(batch_id)
    if not job:
        raise HTTPException(status_code=404, detail="批量任务不存在")

    retried = 0
    all_schema_fields = db.query(SchemaField).all()

    for task in job.tasks.values():
        if task.status == "failed" and task.resume_id:
            resume = db.query(Resume).filter(Resume.id == task.resume_id).first()
            if resume and resume.raw_text:
                parsed_data = unified_ai_service.parse_resume(resume.raw_text, all_schema_fields)
                _save_resume_parsed(resume, parsed_data)
                db.commit()
                batch_manager.update_task(
                    batch_id, task.task_id, status="success", progress=100,
                    parse_method=parsed_data.get('parse_method', 'rule'),
                    retry_count=task.retry_count + 1, error=""
                )
                retried += 1

    return {"message": f"已重试 {retried} 个失败任务", "retried_count": retried}


@router.post("/upload-text", summary="文本方式上传简历（测试用）")
async def upload_text_resume(
    data: TextResumeUpload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """通过文本内容模拟上传简历，AI语义解析基于Schema规则"""
    content = data.content
    file_name = data.file_name

    # 获取所有Schema字段
    all_schema_fields = _get_all_schema_fields(db)

    # AI语义解析（AI优先，降级规则引擎）
    parsed_data = unified_ai_service.parse_resume(content, all_schema_fields)

    # 简历有效性校验
    candidate_name = parsed_data.get('candidate_name')
    is_valid_resume, invalid_reason = _validate_resume_content(content, candidate_name)

    # 无效简历不落库，直接返回错误
    if not is_valid_resume:
        raise HTTPException(status_code=400, detail=f"非简历文件：{invalid_reason}")

    resume = Resume(
        file_name=file_name,
        file_size=len(content.encode('utf-8')),
        file_type='text',
        raw_text=content[:5000],
        status="已解析",
        business_status="有效",
        owner_id=current_user.id
    )
    _save_resume_parsed(resume, parsed_data)

    db.add(resume)
    db.commit()
    db.refresh(resume)

    return {
        "id": resume.id,
        "file_name": resume.file_name,
        "candidate_name": resume.candidate_name,
        "parse_method": resume.parse_method,
        "parsed_data": parsed_data
    }


@router.get("/", response_model=List[ResumeResponse], summary="获取简历列表")
def list_resumes(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Resume)
    if status:
        query = query.filter(Resume.status == status)
    # recruiter 只能看自己的简历
    if current_user.role == "recruiter":
        query = query.filter(Resume.owner_id == current_user.id)
    resumes = query.order_by(Resume.created_at.desc()).all()
    # 批量查询每个简历的匹配结果数量和岗位名称
    resume_ids = [r.id for r in resumes]
    match_counts = {}
    match_positions = {}
    if resume_ids:
        from models import MatchResult, Position
        counts = db.query(
            MatchResult.resume_id,
            func.count(MatchResult.id).label('cnt')
        ).filter(MatchResult.resume_id.in_(resume_ids)).group_by(MatchResult.resume_id).all()
        match_counts = {c.resume_id: c.cnt for c in counts}
        # 查询每个简历匹配的岗位名称
        position_results = db.query(
            MatchResult.resume_id,
            Position.name.label('position_name'),
            MatchResult.total_score,
            MatchResult.passed_hard
        ).join(Position, MatchResult.position_id == Position.id
        ).filter(MatchResult.resume_id.in_(resume_ids)
        ).order_by(MatchResult.total_score.desc()).all()
        for pr in position_results:
            if pr.resume_id not in match_positions:
                match_positions[pr.resume_id] = []
            match_positions[pr.resume_id].append({
                'name': pr.position_name,
                'score': pr.total_score,
                'passed_hard': pr.passed_hard
            })
    # 手动填充 owner_name 和 duplicate_info
    result = []
    for r in resumes:
        item = {c.name: getattr(r, c.name) for c in r.__table__.columns}
        item['owner_name'] = r.owner.name if r.owner else None
        item['matched_count'] = match_counts.get(r.id, 0)
        item['matched_positions'] = match_positions.get(r.id, [])
        if r.duplicate_of:
            item['duplicate_of_id'] = r.duplicate_of.id
            item['duplicate_of_name'] = r.duplicate_of.file_name
            item['duplicate_of_owner'] = r.duplicate_of.owner.name if r.duplicate_of.owner else None
        result.append(item)
    return result


@router.get("/{resume_id}", response_model=ResumeResponse, summary="获取简历详情")
def get_resume(resume_id: int, db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    # recruiter 只能看自己的
    if current_user.role == "recruiter" and resume.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看他人简历")
    return resume


@router.delete("/{resume_id}", summary="删除简历")
def delete_resume(resume_id: int, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    """删除简历及其所有匹配结果"""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    # recruiter 只能删自己的（super_admin 和 maintainer 可删除所有简历）
    if current_user.role == "recruiter" and resume.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除他人简历")
    # 级联删除匹配结果
    db.query(MatchResult).filter(MatchResult.resume_id == resume_id).delete()
    db.delete(resume)
    db.commit()
    # 同步清理内存中的内容哈希，防止删除后重复上传被误判为重复
    batch_manager.remove_content_by_resume_id(resume_id)
    return {"message": "删除成功", "id": resume_id}


@router.post("/match-all/{resume_id}", summary="全域遍历匹配（单份简历匹配所有岗位）")
def match_resume_to_all_positions(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """将一份简历匹配到所有在招岗位，基于Schema语义匹配"""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    # 检查简历是否有效
    if resume.business_status == "无效":
        raise HTTPException(status_code=400, detail=f"该简历已被标记为无效：{resume.invalid_reason or '无法识别为有效简历'}，不参与匹配")
    # recruiter 只能匹配自己的简历
    if current_user.role == "recruiter" and resume.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权匹配他人简历")

    # 获取所有在招岗位
    positions = db.query(Position).filter(Position.status == PositionStatus.RECRUITING).all()

    # 准备简历数据
    resume_data = _resume_to_dict(resume)

    results = []
    for position in positions:
        # 获取该岗位的Schema字段
        schema_fields = db.query(SchemaField).filter(
            SchemaField.position_id == position.id
        ).order_by(SchemaField.sort_order).all()

        company_name = position.company.name if position.company else ''

        # AI语义匹配（AI优先，降级规则引擎）
        match_result = unified_ai_service.match_resume_to_position(
            resume_data=resume_data,
            schema_fields=schema_fields,
            position_name=position.name,
            company_name=company_name
        )

        # 保存匹配结果
        existing = db.query(MatchResult).filter(
            MatchResult.resume_id == resume_id,
            MatchResult.position_id == position.id
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
            existing.match_details_json = json.dumps(
                match_result.get('match_details', []), ensure_ascii=False
            )
            existing.match_method = match_result.get('match_method', 'rule')
            existing.match_highlights = match_result.get('match_highlights', '')
            existing.match_gaps = match_result.get('match_gaps', '')
        else:
            new_result = MatchResult(
                resume_id=resume_id,
                position_id=position.id,
                total_score=match_result['total_score'],
                passed_hard=match_result['passed_hard'],
                reject_reason=match_result['reject_reason'],
                education_score=dimension_scores.get('学历', 0),
                experience_score=dimension_scores.get('工作年限', 0),
                skill_score=dimension_scores.get('核心技能', 0),
                industry_score=dimension_scores.get('行业经验', 0),
                project_score=dimension_scores.get('项目经验', 0),
                certificate_score=dimension_scores.get('证书', 0),
                match_details_json=json.dumps(
                    match_result.get('match_details', []), ensure_ascii=False
                ),
                match_method=match_result.get('match_method', 'rule'),
                match_highlights=match_result.get('match_highlights', ''),
                match_gaps=match_result.get('match_gaps', '')
            )
            db.add(new_result)
            db.flush()

        db.commit()

        results.append({
            'position_id': position.id,
            'position_name': position.name,
            'company_name': position.company.name if position.company else '',
            'total_score': match_result['total_score'],
            'passed_hard': match_result['passed_hard'],
            'reject_reason': match_result['reject_reason'],
            'dimension_scores': dimension_scores,
            'match_details': match_result.get('match_details', []),
            'match_method': match_result.get('match_method', 'rule'),
            'match_highlights': match_result.get('match_highlights', ''),
            'match_gaps': match_result.get('match_gaps', '')
        })

    # 按分数降序排列
    results.sort(key=lambda x: x['total_score'], reverse=True)

    return {
        'resume_id': resume_id,
        'candidate_name': resume.candidate_name,
        'parse_method': resume.parse_method,
        'total_positions': len(positions),
        'matched_positions': len([r for r in results if r['passed_hard']]),
        'results': results
    }


@router.post("/match-position/{resume_id}/{position_id}", summary="专项匹配（单份简历匹配单个岗位）")
def match_resume_to_single_position(
    resume_id: int,
    position_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """将一份简历专项匹配到指定岗位，基于Schema语义匹配"""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    # 检查简历是否有效
    if resume.business_status == "无效":
        raise HTTPException(status_code=400, detail=f"该简历已被标记为无效：{resume.invalid_reason or '无法识别为有效简历'}，不参与匹配")
    # recruiter 只能匹配自己的简历
    if current_user.role == "recruiter" and resume.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权匹配他人简历")

    position = db.query(Position).filter(Position.id == position_id).first()
    if not position:
        raise HTTPException(status_code=404, detail="岗位不存在")

    # 获取该岗位的Schema字段
    schema_fields = db.query(SchemaField).filter(
        SchemaField.position_id == position.id
    ).order_by(SchemaField.sort_order).all()

    company_name = position.company.name if position.company else ''

    # 准备简历数据
    resume_data = _resume_to_dict(resume)

    # AI语义匹配（AI优先，降级规则引擎）
    match_result = unified_ai_service.match_resume_to_position(
        resume_data=resume_data,
        schema_fields=schema_fields,
        position_name=position.name,
        company_name=company_name
    )

    # 保存匹配结果
    existing = db.query(MatchResult).filter(
        MatchResult.resume_id == resume_id,
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
        existing.certificate_score = dimension_scores.get('证书', 0)
        existing.project_score = dimension_scores.get('项目经历', 0)
        existing.match_method = match_result.get('match_method', 'rule')
        existing.match_highlights = match_result.get('match_highlights', '')
        existing.match_gaps = match_result.get('match_gaps', '')
        existing.updated_at = datetime.utcnow()
        result_id = existing.id
    else:
        new_result = MatchResult(
            resume_id=resume_id,
            position_id=position_id,
            total_score=match_result['total_score'],
            passed_hard=match_result['passed_hard'],
            reject_reason=match_result['reject_reason'],
            education_score=dimension_scores.get('学历', 0),
            experience_score=dimension_scores.get('工作年限', 0),
            skill_score=dimension_scores.get('核心技能', 0),
            industry_score=dimension_scores.get('行业经验', 0),
            certificate_score=dimension_scores.get('证书', 0),
            project_score=dimension_scores.get('项目经历', 0),
            match_method=match_result.get('match_method', 'rule'),
            match_highlights=match_result.get('match_highlights', ''),
            match_gaps=match_result.get('match_gaps', '')
        )
        db.add(new_result)
        db.flush()
        result_id = new_result.id

    db.commit()

    return {
        'resume_id': resume_id,
        'position_id': position_id,
        'candidate_name': resume.candidate_name,
        'position_name': position.name,
        'company_name': company_name,
        'total_score': match_result['total_score'],
        'passed_hard': match_result['passed_hard'],
        'match_method': match_result.get('match_method', 'rule'),
        'match_highlights': match_result.get('match_highlights', ''),
        'match_gaps': match_result.get('match_gaps', ''),
        'result_id': result_id
    }


@router.get("/match-results/", response_model=List[MatchResultWithDetail], summary="获取匹配结果列表")
def list_match_results(
    position_id: Optional[int] = None,
    passed_hard: Optional[bool] = None,
    min_score: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取所有匹配结果，支持筛选"""
    query = db.query(MatchResult, Resume, Position).join(
        Resume, MatchResult.resume_id == Resume.id
    ).join(
        Position, MatchResult.position_id == Position.id
    )

    # recruiter 只能看自己简历的匹配结果
    if current_user.role == "recruiter":
        query = query.filter(Resume.owner_id == current_user.id)

    if position_id:
        query = query.filter(MatchResult.position_id == position_id)
    if passed_hard is not None:
        query = query.filter(MatchResult.passed_hard == passed_hard)
    if min_score:
        query = query.filter(MatchResult.total_score >= min_score)

    results = query.order_by(MatchResult.total_score.desc()).all()

    response = []
    for mr, resume, position in results:
        response.append(MatchResultWithDetail(
            id=mr.id,
            resume_id=mr.resume_id,
            position_id=mr.position_id,
            total_score=mr.total_score,
            passed_hard=mr.passed_hard,
            reject_reason=mr.reject_reason,
            education_score=mr.education_score,
            experience_score=mr.experience_score,
            skill_score=mr.skill_score,
            industry_score=mr.industry_score,
            project_score=mr.project_score,
            certificate_score=mr.certificate_score,
            match_details_json=mr.match_details_json,
            match_method=mr.match_method,
            match_highlights=mr.match_highlights,
            match_gaps=mr.match_gaps,
            sent_to_company=mr.sent_to_company,
            sent_at=mr.sent_at,
            sent_by=mr.sent_by,
            interview_scheduled=mr.interview_scheduled,
            interview_scheduled_at=mr.interview_scheduled_at,
            created_at=mr.created_at,
            resume_name=resume.candidate_name or resume.file_name,
            position_name=position.name,
            company_name=position.company.name if position.company else ''
        ))

    return response


@router.delete("/match-results/{match_id}", summary="删除单条匹配结果")
def delete_match_result(match_id: int, db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    """删除指定的匹配结果记录"""
    match_result = db.query(MatchResult).filter(MatchResult.id == match_id).first()
    if not match_result:
        raise HTTPException(status_code=404, detail="匹配结果不存在")
    # super_admin 和 maintainer 可删除所有匹配结果
    # recruiter 只能删自己简历的
    if current_user.role == "recruiter":
        resume = db.query(Resume).filter(Resume.id == match_result.resume_id).first()
        if not resume or resume.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权删除他人简历的匹配结果")
    db.delete(match_result)
    db.commit()
    return {"message": "删除成功", "id": match_id}


@router.delete("/match-results/", summary="批量删除匹配结果")
def batch_delete_match_results(
    ids: str = None,
    resume_id: Optional[int] = None,
    position_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # super_admin 和 maintainer 可删除所有匹配结果
    """
    批量删除匹配结果
    - ids: 逗号分隔的ID列表，如 "1,2,3"
    - resume_id: 删除指定简历的所有匹配结果
    - position_id: 删除指定岗位的所有匹配结果
    """
    query = db.query(MatchResult)

    # recruiter 只能删自己简历的匹配结果
    if current_user.role == "recruiter":
        query = query.join(Resume, MatchResult.resume_id == Resume.id).filter(
            Resume.owner_id == current_user.id
        )

    if ids:
        id_list = [int(x.strip()) for x in ids.split(',') if x.strip()]
        query = query.filter(MatchResult.id.in_(id_list))
    if resume_id:
        query = query.filter(MatchResult.resume_id == resume_id)
    if position_id:
        query = query.filter(MatchResult.position_id == position_id)

    if not ids and not resume_id and not position_id:
        raise HTTPException(status_code=400, detail="请提供删除条件（ids/resume_id/position_id）")

    count = query.count()
    query.delete(synchronize_session=False)
    db.commit()
    return {"message": f"成功删除 {count} 条匹配结果", "deleted_count": count}

@router.patch("/{resume_id}/owner", summary="重新分配简历归属")
def reassign_resume_owner(
    resume_id: int,
    body: ReassignOwnerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "maintainer"))
):
    """重新分配简历归属（super_admin 和 maintainer 可操作）"""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    # 校验目标用户存在
    target = db.query(User).filter(User.id == body.owner_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="目标用户不存在")
    resume.owner_id = body.owner_id
    db.commit()
    db.refresh(resume)
    return {"message": "归属已更新", "resume_id": resume_id, "owner_id": body.owner_id}


@router.patch("/batch-reassign", summary="批量分配简历归属")
def batch_reassign_resumes(
    body: BatchReassignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "maintainer"))
):
    """批量分配多份简历给同一招聘人员（super_admin 和 maintainer 可操作）"""
    if not body.resume_ids:
        raise HTTPException(status_code=400, detail="请选择要分配的简历")
    # 校验目标用户存在且是招聘人员
    target = db.query(User).filter(User.id == body.owner_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="目标用户不存在")
    if target.role != "recruiter":
        raise HTTPException(status_code=400, detail="目标用户必须是招聘人员角色")
    # 批量更新
    resumes = db.query(Resume).filter(Resume.id.in_(body.resume_ids)).all()
    if not resumes:
        raise HTTPException(status_code=404, detail="未找到选中的简历")
    updated_count = 0
    for r in resumes:
        r.owner_id = body.owner_id
        updated_count += 1
    db.commit()
    return {"message": f"成功分配 {updated_count} 份简历给「{target.name or target.phone}」", "updated_count": updated_count}

# ========== 发送到公司邮箱 ==========
@router.post("/match-results/{match_id}/send", summary="发送单条匹配结果到公司邮箱")
def send_match_to_company(match_id: int, db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    """将匹配结果发送到对应公司的邮箱（真实SMTP发送）"""
    from email_sender import send_email, build_match_email_html
    match_result = db.query(MatchResult).filter(MatchResult.id == match_id).first()
    if not match_result:
        raise HTTPException(status_code=404, detail="匹配结果不存在")
    # 权限校验：招聘人员只能发自己的
    if current_user.role == "recruiter":
        resume = db.query(Resume).filter(Resume.id == match_result.resume_id).first()
        if not resume or resume.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权发送：只能发送自己名下的简历")
    # 获取公司邮箱
    position = db.query(Position).filter(Position.id == match_result.position_id).first()
    if not position:
        raise HTTPException(status_code=404, detail="岗位不存在")
    company = db.query(Company).filter(Company.id == position.company_id).first()
    if not company or not company.email:
        raise HTTPException(status_code=400, detail="该公司未配置接收邮箱，请先在公司管理中设置")
    # 获取简历信息
    resume = db.query(Resume).filter(Resume.id == match_result.resume_id).first()
    candidate_name = resume.candidate_name if resume and resume.candidate_name else "未知候选人"
    # 解析匹配详情
    match_details = {}
    if match_result.match_details_json:
        try:
            import json
            match_details = json.loads(match_result.match_details_json)
        except Exception:
            pass
    # 构建并发送邮件
    subject = f"候选人推荐 - {candidate_name} - {position.name}岗位"
    html_content = build_match_email_html(
        candidate_name=candidate_name,
        position_name=position.name,
        company_name=company.name,
        total_score=match_result.total_score,
        passed_hard=match_result.passed_hard,
        match_details=match_details,
        highlights=match_result.match_highlights,
        gaps=match_result.match_gaps
    )
    success, message = send_email(db, company.email, subject, html_content)
    # 标记发送状态 + 自动翻转业务状态为投递中
    match_result.sent_to_company = True
    match_result.sent_at = datetime.now()
    match_result.sent_by = current_user.id
    # 自动翻转简历业务状态为投递中
    if resume and resume.business_status != "已面试通过":
        resume.business_status = "投递中"
    db.commit()
    return {
        "message": message if success else f"邮件发送失败（已记录发送状态）：{message}",
        "email_sent": success,
        "company_email": company.email,
        "company_name": company.name,
        "sent_at": match_result.sent_at.isoformat()
    }


@router.post("/match-results/batch-send", summary="批量发送匹配结果到公司邮箱")
def batch_send_to_company(body: dict, db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    """批量发送匹配结果到公司邮箱"""
    match_ids = body.get("match_ids", [])
    if not match_ids:
        raise HTTPException(status_code=400, detail="请选择要发送的匹配结果")
    success = []
    failed = []
    for mid in match_ids:
        try:
            match_result = db.query(MatchResult).filter(MatchResult.id == mid).first()
            if not match_result:
                failed.append({"id": mid, "reason": "匹配结果不存在"})
                continue
            if current_user.role == "recruiter":
                resume = db.query(Resume).filter(Resume.id == match_result.resume_id).first()
                if not resume or resume.owner_id != current_user.id:
                    failed.append({"id": mid, "reason": "无权发送"})
                    continue
            position = db.query(Position).filter(Position.id == match_result.position_id).first()
            if not position:
                failed.append({"id": mid, "reason": "岗位不存在"})
                continue
            company = db.query(Company).filter(Company.id == position.company_id).first()
            if not company or not company.email:
                failed.append({"id": mid, "reason": "公司未配置邮箱"})
                continue
            match_result.sent_to_company = True
            match_result.sent_at = datetime.now()
            match_result.sent_by = current_user.id
            success.append({"id": mid, "company_email": company.email, "company_name": company.name})
        except Exception as e:
            failed.append({"id": mid, "reason": str(e)})
    db.commit()
    return {"success_count": len(success), "failed_count": len(failed), "success": success, "failed": failed}


@router.patch("/match-results/{match_id}/interview-scheduled", summary="标记面试安排状态")
def toggle_interview_scheduled(match_id: int, request: dict, db: Session = Depends(get_db),
                                current_user: User = Depends(get_current_user)):
    interview_scheduled = request.get("interview_scheduled")
    if interview_scheduled is None:
        raise HTTPException(status_code=400, detail="缺少 interview_scheduled 参数")
    match_result = db.query(MatchResult).filter(MatchResult.id == match_id).first()
    if not match_result:
        raise HTTPException(status_code=404, detail="匹配结果不存在")
    if current_user.role == "recruiter":
        resume = db.query(Resume).filter(Resume.id == match_result.resume_id).first()
        if not resume or resume.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权操作：只能操作自己名下的简历")
    match_result.interview_scheduled = interview_scheduled
    if interview_scheduled:
        match_result.interview_scheduled_at = datetime.now()
    else:
        match_result.interview_scheduled_at = None
    db.commit()
    return {
        "message": "已标记面试已安排" if interview_scheduled else "已取消面试安排标记",
        "interview_scheduled": interview_scheduled,
        "interview_scheduled_at": match_result.interview_scheduled_at.isoformat() if match_result.interview_scheduled_at else None
    }

# ========== 简历业务状态机 ==========

VALID_STATUSES = ["有效", "投递中", "已面试通过", "无效"]
# 招聘人员可设置的状态（不能设置已面试通过和无效，也不能重置这两个）
RECRUITER_SETTABLE_STATUSES = ["有效", "投递中"]


@router.patch("/{resume_id}/status", summary="变更简历业务状态")
def update_resume_status(resume_id: int, request: dict, db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    """
    变更简历业务状态：有效/投递中/已面试通过/无效
    - 招聘人员：只能改自己的简历，且只能在有效/投递中之间切换
    - 超管/维护：可改所有简历的所有状态，包括重置已面试通过/无效
    """
    new_status = request.get("business_status")
    if not new_status or new_status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"无效状态，可选：{', '.join(VALID_STATUSES)}")

    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")

    # 权限校验
    if current_user.role == "recruiter":
        if resume.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权操作：只能修改自己名下的简历")
        # 招聘人员不能设置已面试通过和无效
        if new_status not in RECRUITER_SETTABLE_STATUSES:
            raise HTTPException(status_code=403, detail="无权操作：招聘人员只能设置有效/投递中状态")
        # 招聘人员不能从已面试通过/无效重置（当前状态是这两个时不允许改）
        if resume.business_status in ["已面试通过", "无效"]:
            raise HTTPException(status_code=403, detail="无权操作：已面试通过/无效状态仅管理员可重置")

    old_status = resume.business_status
    resume.business_status = new_status
    # 如果改为有效，自动恢复路由
    if new_status == "有效":
        resume.routing_paused = False
    db.commit()
    return {"message": f"状态已从「{old_status}」变更为「{new_status}」", "business_status": new_status}


@router.patch("/{resume_id}/routing", summary="切换简历路由开关")
def toggle_resume_routing(resume_id: int, request: dict, db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    """
    切换投递中简历的路由开关（暂停/继续路由）
    - 仅投递中状态的简历可切换
    - 招聘人员只能改自己的简历
    """
    routing_paused = request.get("routing_paused")
    if routing_paused is None:
        raise HTTPException(status_code=400, detail="缺少 routing_paused 参数")

    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")

    # 仅投递中状态可切换路由
    if resume.business_status != "投递中":
        raise HTTPException(status_code=400, detail="仅投递中状态的简历可切换路由开关")

    # 权限校验
    if current_user.role == "recruiter" and resume.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作：只能修改自己名下的简历")

    resume.routing_paused = routing_paused
    db.commit()
    return {
        "message": "路由已暂停" if routing_paused else "路由已恢复",
        "routing_paused": routing_paused
    }
