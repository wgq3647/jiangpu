# -*- coding: utf-8 -*-
"""
人工评价+面试反馈+AI自学习优化 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json
from database import get_db
from models import (
    MatchResult, ManualReview, InterviewFeedback,
    OptimizationLog, AccuracyHistory, Position, SchemaField, Resume, User
)
from auth_utils import get_current_user, require_roles
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/feedback", tags=["人工评价与自学习优化"])

# ========== Pydantic 模型 ==========
class ManualReviewCreate(BaseModel):
    match_result_id: int
    hr_rating: int = Field(..., ge=1, le=5, description="星级打分1-5")
    hr_comment: Optional[str] = None
    ai_score_correction: Optional[int] = Field(None, ge=0, le=100)
    ai_deviation_type: Optional[str] = None
    reviewer_name: Optional[str] = None

class ManualReviewUpdate(BaseModel):
    hr_rating: Optional[int] = Field(None, ge=1, le=5)
    hr_comment: Optional[str] = None
    ai_score_correction: Optional[int] = Field(None, ge=0, le=100)
    ai_deviation_type: Optional[str] = None
    reviewer_name: Optional[str] = None

class InterviewFeedbackCreate(BaseModel):
    match_result_id: int
    interview_result: str  # 通过/不通过/待定
    fail_reasons: Optional[str] = None  # 逗号分隔
    custom_note: Optional[str] = None
    interviewer: Optional[str] = None
    interview_date: Optional[datetime] = None

class InterviewFeedbackUpdate(BaseModel):
    interview_result: Optional[str] = None
    fail_reasons: Optional[str] = None
    custom_note: Optional[str] = None
    interviewer: Optional[str] = None
    interview_date: Optional[datetime] = None

class OptimizeRequest(BaseModel):
    position_id: Optional[int] = None
    triggered_by: str = "手动触发"

# ========== 人工评价 API ==========
@router.post("/manual-reviews", summary="创建/更新人工评价")
def create_manual_review(data: ManualReviewCreate, db: Session = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    match_result = db.query(MatchResult).filter(MatchResult.id == data.match_result_id).first()
    if not match_result:
        raise HTTPException(status_code=404, detail="匹配结果不存在")
    # recruiter 只能评价自己简历的匹配结果
    if current_user.role == "recruiter":
        resume = db.query(Resume).filter(Resume.id == match_result.resume_id).first()
        if not resume or resume.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权评价他人简历的匹配结果")

    existing = db.query(ManualReview).filter(ManualReview.match_result_id == data.match_result_id).first()
    if existing:
        existing.hr_rating = data.hr_rating
        existing.hr_comment = data.hr_comment
        existing.ai_score_correction = data.ai_score_correction
        existing.ai_deviation_type = data.ai_deviation_type
        existing.reviewer_name = data.reviewer_name
        db.commit()
        db.refresh(existing)
        return existing

    review = ManualReview(**data.model_dump())
    db.add(review)
    db.commit()
    db.refresh(review)
    return review

@router.get("/manual-reviews/{match_result_id}", summary="获取某匹配结果的人工评价")
def get_manual_review(match_result_id: int, db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    review = db.query(ManualReview).filter(ManualReview.match_result_id == match_result_id).first()
    if not review:
        return None
    return review

@router.get("/manual-reviews", summary="获取人工评价列表")
def list_manual_reviews(
    position_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(ManualReview).join(MatchResult, ManualReview.match_result_id == MatchResult.id)
    if position_id:
        query = query.filter(MatchResult.position_id == position_id)
    # recruiter 只看自己简历的
    if current_user.role == "recruiter":
        query = query.join(Resume, MatchResult.resume_id == Resume.id).filter(
            Resume.owner_id == current_user.id
        )
    return query.order_by(ManualReview.created_at.desc()).all()

# ========== 面试反馈 API ==========
@router.post("/interview-feedbacks", summary="创建/更新面试反馈")
def create_interview_feedback(data: InterviewFeedbackCreate, db: Session = Depends(get_db),
                              current_user: User = Depends(get_current_user)):
    match_result = db.query(MatchResult).filter(MatchResult.id == data.match_result_id).first()
    if not match_result:
        raise HTTPException(status_code=404, detail="匹配结果不存在")
    # recruiter 只能反馈自己简历的
    if current_user.role == "recruiter":
        resume = db.query(Resume).filter(Resume.id == match_result.resume_id).first()
        if not resume or resume.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权反馈他人简历的匹配结果")

    existing = db.query(InterviewFeedback).filter(InterviewFeedback.match_result_id == data.match_result_id).first()
    if existing:
        existing.interview_result = data.interview_result
        existing.fail_reasons = data.fail_reasons
        existing.custom_note = data.custom_note
        existing.interviewer = data.interviewer
        existing.interview_date = data.interview_date
        # 面试通过自动翻转简历状态为已面试通过
        if data.interview_result == "通过":
            resume = db.query(Resume).filter(Resume.id == match_result.resume_id).first()
            if resume:
                resume.business_status = "已面试通过"
        db.commit()
        db.refresh(existing)
        # 触发准确率记录
        _record_accuracy(db, match_result.position_id)
        return existing

    feedback = InterviewFeedback(**data.model_dump())
    db.add(feedback)
    # 面试通过自动翻转简历状态为已面试通过
    if data.interview_result == "通过":
        resume = db.query(Resume).filter(Resume.id == match_result.resume_id).first()
        if resume:
            resume.business_status = "已面试通过"
    db.commit()
    db.refresh(feedback)
    # 触发准确率记录
    _record_accuracy(db, match_result.position_id)
    return feedback

@router.get("/interview-feedbacks/{match_result_id}", summary="获取某匹配结果的面试反馈")
def get_interview_feedback(match_result_id: int, db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    feedback = db.query(InterviewFeedback).filter(InterviewFeedback.match_result_id == match_result_id).first()
    if not feedback:
        return None
    return feedback

@router.get("/interview-feedbacks", summary="获取面试反馈列表")
def list_interview_feedbacks(
    position_id: Optional[int] = None,
    interview_result: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(InterviewFeedback).join(MatchResult, InterviewFeedback.match_result_id == MatchResult.id)
    if position_id:
        query = query.filter(MatchResult.position_id == position_id)
    if interview_result:
        query = query.filter(InterviewFeedback.interview_result == interview_result)
    # recruiter 只看自己简历的
    if current_user.role == "recruiter":
        query = query.join(Resume, MatchResult.resume_id == Resume.id).filter(
            Resume.owner_id == current_user.id
        )
    return query.order_by(InterviewFeedback.created_at.desc()).all()

# ========== AI自学习优化 API ==========
@router.post("/optimize/run", summary="触发AI自学习优化")
def run_optimization(data: OptimizeRequest, db: Session = Depends(get_db),
                     current_user: User = Depends(require_roles("super_admin", "maintainer"))):
    """
    AI自学习优化核心算法：
    1. 收集有面试结果的样本
    2. 分析假阳性（AI高分但面试不通过）和假阴性（AI低分但面试通过）
    3. 调整Schema权重
    4. 记录优化日志和准确率历史
    """
    # 获取有面试反馈的匹配结果
    query = db.query(MatchResult).join(InterviewFeedback).filter(
        InterviewFeedback.interview_result.in_(["通过", "不通过"])
    )
    if data.position_id:
        query = query.filter(MatchResult.position_id == data.position_id)

    samples = query.all()
    if len(samples) < 3:
        raise HTTPException(status_code=400, detail=f"样本不足（当前{len(samples)}条），至少需要3条有面试结果的样本才能进行优化")

    # 分析样本
    true_positive = []  # AI通过且面试通过
    false_positive = []  # AI通过但面试不通过
    true_negative = []  # AI不通过且面试不通过
    false_negative = []  # AI不通过但面试通过

    AI_PASS_THRESHOLD = 70

    for sample in samples:
        feedback = sample.interview_feedback
        ai_pass = sample.total_score >= AI_PASS_THRESHOLD
        interview_pass = feedback.interview_result == "通过"

        if ai_pass and interview_pass:
            true_positive.append(sample)
        elif ai_pass and not interview_pass:
            false_positive.append(sample)
        elif not ai_pass and not interview_pass:
            true_negative.append(sample)
        else:
            false_negative.append(sample)

    total = len(samples)
    accuracy = round((len(true_positive) + len(true_negative)) / total * 100, 1) if total > 0 else 0
    precision = round(len(true_positive) / (len(true_positive) + len(false_positive)) * 100, 1) if (len(true_positive) + len(false_positive)) > 0 else 0
    recall = round(len(true_positive) / (len(true_positive) + len(false_negative)) * 100, 1) if (len(true_positive) + len(false_negative)) > 0 else 0

    # 权重调整逻辑
    weight_adjustments = []
    positions_to_optimize = []

    if data.position_id:
        positions_to_optimize = [data.position_id]
    else:
        # 全局优化：对所有有样本的岗位
        position_ids = set(s.position_id for s in samples)
        positions_to_optimize = list(position_ids)

    for pos_id in positions_to_optimize:
        schema_fields = db.query(SchemaField).filter(SchemaField.position_id == pos_id).order_by(SchemaField.sort_order).all()
        if not schema_fields:
            continue

        pos_samples = [s for s in samples if s.position_id == pos_id]
        pos_fp = [s for s in false_positive if s.position_id == pos_id]
        pos_tp = [s for s in true_positive if s.position_id == pos_id]
        pos_fn = [s for s in false_negative if s.position_id == pos_id]

        # 分析各维度在假阳性中的得分情况
        dimension_scores = {
            '学历': 'education_score',
            '工作年限': 'experience_score',
            '核心技能': 'skill_score',
            '行业经验': 'industry_score',
            '项目经验': 'project_score',
            '证书': 'certificate_score',
        }

        adjustments = {}
        for field in schema_fields:
            field_name = field.field_name
            score_attr = dimension_scores.get(field_name)
            if not score_attr:
                continue

            # 假阳性中该维度的平均得分
            fp_avg = sum(getattr(s, score_attr, 0) for s in pos_fp) / len(pos_fp) if pos_fp else 0
            # 真阳性中该维度的平均得分
            tp_avg = sum(getattr(s, score_attr, 0) for s in pos_tp) / len(pos_tp) if pos_tp else 0
            # 假阴性中该维度的平均得分
            fn_avg = sum(getattr(s, score_attr, 0) for s in pos_fn) / len(pos_fn) if pos_fn else 0

            old_weight = field.weight
            new_weight = old_weight

            # 如果假阳性中该维度得分高（AI高估了），降低权重
            if fp_avg > 70 and fp_avg > tp_avg:
                reduction = min(15, int((fp_avg - tp_avg) / 10))
                new_weight = max(1, old_weight - reduction)
            # 如果假阴性中该维度得分高（AI低估了），提高权重
            elif fn_avg > 50 and fn_avg > tp_avg:
                increase = min(15, int((fn_avg - tp_avg) / 10))
                new_weight = min(100, old_weight + increase)
            # 如果真阳性中该维度得分高且假阳性低，适当提高权重
            elif tp_avg > 70 and tp_avg > fp_avg + 10:
                increase = min(10, int((tp_avg - fp_avg) / 15))
                new_weight = min(100, old_weight + increase)

            if new_weight != old_weight:
                adjustments[field_name] = {
                    'old': old_weight,
                    'new': new_weight,
                    'fp_avg': round(fp_avg, 1),
                    'tp_avg': round(tp_avg, 1),
                    'fn_avg': round(fn_avg, 1),
                }
                field.weight = new_weight

        if adjustments:
            weight_adjustments.append({
                'position_id': pos_id,
                'adjustments': adjustments,
            })

    db.commit()

    # 记录优化日志
    log = OptimizationLog(
        position_id=data.position_id,
        optimization_type="权重调整",
        description=f"基于{len(samples)}条面试反馈样本进行自学习优化，分析{len(false_positive)}例假阳性、{len(false_negative)}例假阴性案例，调整{sum(len(a['adjustments']) for a in weight_adjustments)}个字段权重",
        before_data=json.dumps({
            'true_positive': len(true_positive),
            'false_positive': len(false_positive),
            'true_negative': len(true_negative),
            'false_negative': len(false_negative),
        }, ensure_ascii=False),
        after_data=json.dumps(weight_adjustments, ensure_ascii=False),
        accuracy_before=accuracy,
        accuracy_after=accuracy,  # 优化后准确率需要重新匹配才能验证
        triggered_by=data.triggered_by,
        sample_count=len(samples),
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    # 记录准确率历史
    _record_accuracy(db, data.position_id)

    return {
        'log_id': log.id,
        'sample_count': len(samples),
        'true_positive': len(true_positive),
        'false_positive': len(false_positive),
        'true_negative': len(true_negative),
        'false_negative': len(false_negative),
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'weight_adjustments': weight_adjustments,
        'message': f"优化完成！分析{len(samples)}条样本，调整{sum(len(a['adjustments']) for a in weight_adjustments)}个字段权重"
    }

@router.get("/optimize/logs", summary="获取优化日志列表")
def list_optimization_logs(
    position_id: Optional[int] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "maintainer"))
):
    query = db.query(OptimizationLog)
    if position_id:
        query = query.filter(OptimizationLog.position_id == position_id)
    return query.order_by(OptimizationLog.created_at.desc()).limit(limit).all()

@router.get("/optimize/accuracy-trend", summary="获取准确率趋势数据")
def get_accuracy_trend(
    position_id: Optional[int] = None,
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "maintainer"))
):
    from datetime import timedelta
    start_date = datetime.now() - timedelta(days=days)
    query = db.query(AccuracyHistory).filter(AccuracyHistory.record_date >= start_date)
    if position_id:
        query = query.filter(AccuracyHistory.position_id == position_id)
    else:
        query = query.filter(AccuracyHistory.position_id.is_(None))
    records = query.order_by(AccuracyHistory.record_date.asc()).all()

    return {
        'dates': [r.record_date.strftime('%Y-%m-%d') for r in records],
        'accuracy': [r.accuracy for r in records],
        'precision': [r.precision for r in records],
        'recall': [r.recall for r in records],
        'total_matches': [r.total_matches for r in records],
        'interview_count': [r.interview_count for r in records],
    }

@router.get("/stats", summary="获取反馈优化统计概览")
def get_feedback_stats(db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    total_matches = db.query(MatchResult).count()
    reviewed_count = db.query(ManualReview).count()
    interview_count = db.query(InterviewFeedback).count()
    pass_count = db.query(InterviewFeedback).filter(InterviewFeedback.interview_result == "通过").count()
    fail_count = db.query(InterviewFeedback).filter(InterviewFeedback.interview_result == "不通过").count()
    pending_count = db.query(InterviewFeedback).filter(InterviewFeedback.interview_result == "待定").count()
    optimization_count = db.query(OptimizationLog).count()

    # 待评价数（有匹配结果但未人工评价）
    reviewed_match_ids = db.query(ManualReview.match_result_id).all()
    reviewed_ids = [r[0] for r in reviewed_match_ids]
    pending_review = db.query(MatchResult).filter(~MatchResult.id.in_(reviewed_ids)).count() if reviewed_ids else total_matches

    # 计算当前准确率
    interviewed = db.query(MatchResult).join(InterviewFeedback).filter(
        InterviewFeedback.interview_result.in_(["通过", "不通过"])
    ).all()
    if interviewed:
        tp = sum(1 for s in interviewed if s.total_score >= 70 and s.interview_feedback.interview_result == "通过")
        fp = sum(1 for s in interviewed if s.total_score >= 70 and s.interview_feedback.interview_result == "不通过")
        tn = sum(1 for s in interviewed if s.total_score < 70 and s.interview_feedback.interview_result == "不通过")
        fn = sum(1 for s in interviewed if s.total_score < 70 and s.interview_feedback.interview_result == "通过")
        current_accuracy = round((tp + tn) / len(interviewed) * 100, 1)
    else:
        current_accuracy = 0
        tp = fp = tn = fn = 0

    return {
        'total_matches': total_matches,
        'reviewed_count': reviewed_count,
        'pending_review': pending_review,
        'interview_count': interview_count,
        'interview_pass': pass_count,
        'interview_fail': fail_count,
        'interview_pending': pending_count,
        'interview_pass_rate': round(pass_count / interview_count * 100, 1) if interview_count > 0 else 0,
        'optimization_count': optimization_count,
        'current_accuracy': current_accuracy,
        'true_positive': tp,
        'false_positive': fp,
        'true_negative': tn,
        'false_negative': fn,
    }

# ========== 内部函数 ==========
def _record_accuracy(db: Session, position_id: Optional[int] = None):
    """记录准确率历史"""
    # 全局准确率
    _calc_and_save_accuracy(db, None)
    # 岗位准确率
    if position_id:
        _calc_and_save_accuracy(db, position_id)

def _calc_and_save_accuracy(db: Session, position_id: Optional[int]):
    query = db.query(MatchResult).join(InterviewFeedback).filter(
        InterviewFeedback.interview_result.in_(["通过", "不通过"])
    )
    if position_id:
        query = query.filter(MatchResult.position_id == position_id)

    samples = query.all()
    if not samples:
        return

    tp = sum(1 for s in samples if s.total_score >= 70 and s.interview_feedback.interview_result == "通过")
    fp = sum(1 for s in samples if s.total_score >= 70 and s.interview_feedback.interview_result == "不通过")
    tn = sum(1 for s in samples if s.total_score < 70 and s.interview_feedback.interview_result == "不通过")
    fn = sum(1 for s in samples if s.total_score < 70 and s.interview_feedback.interview_result == "通过")

    total = len(samples)
    accuracy = round((tp + tn) / total * 100, 1) if total > 0 else 0
    precision = round(tp / (tp + fp) * 100, 1) if (tp + fp) > 0 else 0
    recall = round(tp / (tp + fn) * 100, 1) if (tp + fn) > 0 else 0

    # 检查今天是否已有记录
    today = datetime.now().date()
    existing = db.query(AccuracyHistory).filter(
        AccuracyHistory.position_id == position_id,
        AccuracyHistory.record_date >= today
    ).first()

    if existing:
        existing.total_matches = total
        existing.interview_count = total
        existing.interview_pass_count = tp + fn
        existing.ai_predicted_pass = tp + fp
        existing.true_positive = tp
        existing.false_positive = fp
        existing.true_negative = tn
        existing.false_negative = fn
        existing.accuracy = accuracy
        existing.precision = precision
        existing.recall = recall
    else:
        record = AccuracyHistory(
            position_id=position_id,
            record_date=datetime.now(),
            total_matches=total,
            reviewed_count=db.query(ManualReview).count(),
            interview_count=total,
            interview_pass_count=tp + fn,
            ai_predicted_pass=tp + fp,
            true_positive=tp,
            false_positive=fp,
            true_negative=tn,
            false_negative=fn,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
        )
        db.add(record)

    db.commit()
