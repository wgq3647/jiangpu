from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Position, Resume, MatchResult, PositionStatus, User
from auth_utils import get_current_user, require_roles

router = APIRouter(prefix="/api/stats", tags=["统计数据"])

@router.get("/dashboard", summary="获取工作台统计数据")
def get_dashboard_stats(db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    # recruiter 只统计自己的简历和匹配结果
    resume_filter = []
    match_filter = []
    if current_user.role == "recruiter":
        resume_filter = [Resume.owner_id == current_user.id]
        match_filter = [Resume.owner_id == current_user.id]

    # 在招岗位数（所有角色都看全部岗位）
    open_positions = db.query(Position).filter(Position.status == PositionStatus.RECRUITING).count()
    total_positions_all = db.query(Position).count()

    # 简历统计
    resume_query = db.query(Resume)
    for f in resume_filter:
        resume_query = resume_query.filter(f)
    total_resumes = resume_query.count()
    parsed_resumes = resume_query.filter(Resume.status == "已解析").count()
    failed_resumes = resume_query.filter(Resume.status == "解析失败").count()

    # 匹配结果统计
    match_query = db.query(MatchResult)
    if match_filter:
        match_query = match_query.join(Resume, MatchResult.resume_id == Resume.id)
        for f in match_filter:
            match_query = match_query.filter(f)
    total_matches = match_query.count()
    passed_matches = match_query.filter(MatchResult.passed_hard == True).count()
    rejected_matches = match_query.filter(MatchResult.passed_hard == False).count()

    # AI匹配 vs 规则匹配
    ai_matches = match_query.filter(MatchResult.match_method == "ai").count()
    rule_matches = match_query.filter(MatchResult.match_method == "rule").count()

    # 匹配准确率
    match_accuracy = round(passed_matches / total_matches * 100, 1) if total_matches > 0 else 0

    # 平均分
    avg_score = 0
    if total_matches > 0:
        results = match_query.all()
        total_score = sum(r.total_score for r in results)
        avg_score = round(total_score / total_matches, 1)

    return {
        "open_positions": open_positions,
        "total_positions": total_positions_all,
        "total_resumes": total_resumes,
        "parsed_resumes": parsed_resumes,
        "failed_resumes": failed_resumes,
        "pending_resumes": total_resumes - parsed_resumes - failed_resumes,
        "total_matches": total_matches,
        "passed_matches": passed_matches,
        "rejected_matches": rejected_matches,
        "match_accuracy": match_accuracy,
        "ai_matches": ai_matches,
        "rule_matches": rule_matches,
        "avg_score": avg_score
    }


@router.get("/recruiters", summary="各招聘人员统计（super_admin/maintainer 可见）")
def get_recruiter_stats(db: Session = Depends(get_db),
                       current_user: User = Depends(require_roles("super_admin", "maintainer"))):
    """统计每个招聘人员的上传量/通过量/淘汰量/匹配度"""
    results = []
    recruiters = db.query(User).filter(User.role.in_(["recruiter", "maintainer"])).all()

    for u in recruiters:
        resume_q = db.query(Resume).filter(Resume.owner_id == u.id)
        total_up = resume_q.count()
        parsed_up = resume_q.filter(Resume.status == "已解析").count()

        match_q = db.query(MatchResult).join(Resume, MatchResult.resume_id == Resume.id).filter(
            Resume.owner_id == u.id
        )
        total_m = match_q.count()
        passed_m = match_q.filter(MatchResult.passed_hard == True).count()
        rejected_m = match_q.filter(MatchResult.passed_hard == False).count()
        avg_score = 0
        if total_m > 0:
            scores = [r.total_score for r in match_q.all()]
            avg_score = round(sum(scores) / len(scores), 1)

        results.append({
            "user_id": u.id,
            "phone": u.phone,
            "name": u.name or u.phone,
            "role": u.role,
            "total_resumes": total_up,
            "parsed_resumes": parsed_up,
            "total_matches": total_m,
            "passed_matches": passed_m,
            "rejected_matches": rejected_m,
            "avg_score": avg_score,
        })

    # 加上 owner_id 为 NULL 的（历史数据）
    null_count = db.query(Resume).filter(Resume.owner_id.is_(None)).count()
    if null_count > 0:
        results.append({
            "user_id": 0,
            "phone": "-",
            "name": "未分配",
            "role": "-",
            "total_resumes": null_count,
            "parsed_resumes": 0,
            "total_matches": 0,
            "passed_matches": 0,
            "rejected_matches": 0,
            "avg_score": 0,
        })

    return results

@router.get("/recruiter-daily", summary="招聘人员每日工作数据（按天粒度，super_admin/maintainer可见）")
def get_recruiter_daily_stats(
    days: int = 14,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("super_admin", "maintainer"))
):
    """
    按天统计各招聘人员的工作数据：
    - 上传简历数
    - AI成功匹配数 / 未匹配数
    - 发送到公司数
    - 面试安排数
    - 面试通过数 / 未通过数
    """
    from datetime import timedelta
    from models import InterviewFeedback

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days - 1)

    # 获取所有招聘人员
    recruiters = db.query(User).filter(User.role == "recruiter").order_by(User.id).all()
    recruiter_ids = [u.id for u in recruiters]

    # 生成日期列表
    date_list = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        date_list.append(d.isoformat())

    result = {
        "date_range": {"start": start_date.isoformat(), "end": end_date.isoformat(), "days": days},
        "dates": date_list,
        "recruiters": [],
        "daily_totals": []  # 每天的汇总数据
    }

    # 按招聘人员统计
    for u in recruiters:
        recruiter_data = {
            "user_id": u.id,
            "name": u.name or u.phone,
            "phone": u.phone,
            "daily": {}
        }
        for d_str in date_list:
            recruiter_data["daily"][d_str] = {
                "uploaded": 0, "matched": 0, "unmatched": 0,
                "sent": 0, "interview_scheduled": 0,
                "interview_passed": 0, "interview_failed": 0,
                "companies_created": 0, "positions_created": 0
            }

        # 上传简历（按天）
        resumes = db.query(Resume).filter(
            Resume.owner_id == u.id,
            func.date(Resume.created_at) >= start_date,
            func.date(Resume.created_at) <= end_date
        ).all()
        for r in resumes:
            d_str = r.created_at.date().isoformat()
            if d_str in recruiter_data["daily"]:
                recruiter_data["daily"][d_str]["uploaded"] += 1

        # 录入公司（按天）
        from models import Company
        companies = db.query(Company).filter(
            Company.creator_id == u.id,
            func.date(Company.created_at) >= start_date,
            func.date(Company.created_at) <= end_date
        ).all()
        for c in companies:
            d_str = c.created_at.date().isoformat()
            if d_str in recruiter_data["daily"]:
                recruiter_data["daily"][d_str]["companies_created"] += 1

        # 录入岗位（按天）
        positions_created = db.query(Position).filter(
            Position.creator_id == u.id,
            func.date(Position.created_at) >= start_date,
            func.date(Position.created_at) <= end_date
        ).all()
        for p in positions_created:
            d_str = p.created_at.date().isoformat()
            if d_str in recruiter_data["daily"]:
                recruiter_data["daily"][d_str]["positions_created"] += 1

        # 匹配结果（按天，按创建时间）
        matches = db.query(MatchResult).join(Resume, MatchResult.resume_id == Resume.id).filter(
            Resume.owner_id == u.id,
            func.date(MatchResult.created_at) >= start_date,
            func.date(MatchResult.created_at) <= end_date
        ).all()
        for m in matches:
            d_str = m.created_at.date().isoformat()
            if d_str in recruiter_data["daily"]:
                if m.passed_hard:
                    recruiter_data["daily"][d_str]["matched"] += 1
                else:
                    recruiter_data["daily"][d_str]["unmatched"] += 1
            # 发送到公司（按发送时间）
            if m.sent_to_company and m.sent_at:
                sent_d = m.sent_at.date().isoformat()
                if sent_d in recruiter_data["daily"]:
                    recruiter_data["daily"][sent_d]["sent"] += 1

        # 面试安排（按 interview_scheduled_at 时间）
        scheduled_matches = db.query(MatchResult).join(
            Resume, MatchResult.resume_id == Resume.id
        ).filter(
            Resume.owner_id == u.id,
            MatchResult.interview_scheduled == True,
            MatchResult.interview_scheduled_at.isnot(None),
            func.date(MatchResult.interview_scheduled_at) >= start_date,
            func.date(MatchResult.interview_scheduled_at) <= end_date
        ).all()
        for mr in scheduled_matches:
            d_str = mr.interview_scheduled_at.date().isoformat()
            if d_str in recruiter_data["daily"]:
                recruiter_data["daily"][d_str]["interview_scheduled"] += 1

        # 面试反馈（按创建时间）
        feedbacks = db.query(InterviewFeedback).join(MatchResult, InterviewFeedback.match_result_id == MatchResult.id).join(
            Resume, MatchResult.resume_id == Resume.id
        ).filter(
            Resume.owner_id == u.id,
            func.date(InterviewFeedback.created_at) >= start_date,
            func.date(InterviewFeedback.created_at) <= end_date
        ).all()
        for fb in feedbacks:
            d_str = fb.created_at.date().isoformat()
            if d_str in recruiter_data["daily"]:
                if fb.interview_result == "通过":
                    recruiter_data["daily"][d_str]["interview_passed"] += 1
                elif fb.interview_result == "不通过":
                    recruiter_data["daily"][d_str]["interview_failed"] += 1

        result["recruiters"].append(recruiter_data)

    # 每天的汇总数据（所有招聘人员合计）
    for d_str in date_list:
        daily_total = {"date": d_str, "uploaded": 0, "matched": 0, "unmatched": 0,
                        "sent": 0, "interview_scheduled": 0, "interview_passed": 0, "interview_failed": 0,
                        "companies_created": 0, "positions_created": 0}
        for r in result["recruiters"]:
            d = r["daily"].get(d_str, {})
            for key in ["uploaded", "matched", "unmatched", "sent", "interview_scheduled", "interview_passed", "interview_failed", "companies_created", "positions_created"]:
                daily_total[key] += d.get(key, 0)
        result["daily_totals"].append(daily_total)

    return result
