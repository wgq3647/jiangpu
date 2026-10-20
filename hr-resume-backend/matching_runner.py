# -*- coding: utf-8 -*-
"""
匹配运行器：将岗位匹配所有简历的核心逻辑抽取为独立函数，
供路由接口和后台任务共用。
"""
import json
import logging
from database import SessionLocal
from models import Position, Resume, MatchResult, SchemaField, PositionStatus
from ai_service import unified_ai_service

logger = logging.getLogger(__name__)


def run_match_for_position(position_id: int) -> dict:
    """
    对指定岗位匹配所有已解析简历（独立运行，自己管理DB session）。
    用于后台任务异步执行，不阻塞HTTP请求。
    返回匹配统计结果。
    """
    db = SessionLocal()
    try:
        position = db.query(Position).filter(Position.id == position_id).first()
        if not position:
            logger.warning(f"[自动匹配] 岗位ID={position_id} 不存在，跳过")
            return {"error": "岗位不存在"}

        # 获取该岗位的Schema字段
        schema_fields = db.query(SchemaField).filter(
            SchemaField.position_id == position_id
        ).order_by(SchemaField.sort_order).all()

        if not schema_fields:
            logger.info(f"[自动匹配] 岗位ID={position_id} 尚未配置Schema，跳过")
            return {"error": "无Schema字段", "skipped": True}

        # 获取所有已解析且可参与匹配的简历（业务状态机过滤）
        # 有效：可正常匹配；投递中且未暂停路由：可继续匹配；已面试通过/无效：禁止匹配
        from sqlalchemy import or_, and_
        resumes = db.query(Resume).filter(
            Resume.status == "已解析",
            or_(
                Resume.business_status == "有效",
                and_(Resume.business_status == "投递中", Resume.routing_paused == False)
            )
        ).all()

        if not resumes:
            logger.info(f"[自动匹配] 暂无已解析简历，跳过")
            return {"error": "无简历", "skipped": True}

        company_name = position.company.name if position.company else ''
        total = len(resumes)
        matched = 0
        passed = 0
        resume_passed_map = {}  # 记录每份简历是否通过硬性条件

        logger.info(f"[自动匹配] 开始匹配岗位「{position.name}」，共{total}份简历")

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
                    except Exception:
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
                    resume_passed_map[resume.id] = True
                else:
                    if resume.id not in resume_passed_map:
                        resume_passed_map[resume.id] = False

            except Exception as e:
                logger.error(f"[自动匹配] 简历ID={resume.id} 匹配失败: {e}")

        db.commit()

        # 自动翻转业务状态：匹配成功→有效
        # 注意：匹配失败不改变状态（"无效"仅表示简历解析失败，不是匹配失败）
        # 不覆盖投递中、已面试通过状态（后续流程状态）
        for resume in resumes:
            if resume.business_status in ["投递中", "已面试通过"]:
                continue  # 不覆盖后续流程状态
            is_passed = resume_passed_map.get(resume.id, False)
            if is_passed:
                if resume.business_status != "有效":
                    resume.business_status = "有效"
            # 匹配失败时保持原状态，不改为"无效"
        db.commit()

        logger.info(f"[自动匹配] 岗位「{position.name}」匹配完成：共{total}份，成功{matched}份，通过{passed}份")
        return {
            "position_id": position_id,
            "position_name": position.name,
            "total_resumes": total,
            "matched_count": matched,
            "passed_count": passed,
        }

    except Exception as e:
        logger.error(f"[自动匹配] 岗位ID={position_id} 执行异常: {e}", exc_info=True)
        return {"error": str(e)}
    finally:
        db.close()
