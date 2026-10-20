"""
统一AI服务层
整合AI简历解析和智能匹配，实现AI优先、规则引擎降级的策略
"""
import json
import logging
from typing import List, Dict, Any, Optional

from ai import ai_resume_parser, ai_match_engine, AIConfig
from matching_engine import ai_engine as rule_engine

logger = logging.getLogger(__name__)


class UnifiedAIService:
    """
    统一AI服务
    - AI可用时：使用AI大模型进行语义解析和智能匹配
    - AI不可用/调用失败时：自动降级到规则引擎
    - 记录使用的是AI还是规则引擎，便于追溯
    """

    def __init__(self):
        self.ai_parser = ai_resume_parser
        self.ai_matcher = ai_match_engine
        self.rule_engine = rule_engine

    def is_ai_available(self) -> bool:
        """检查AI服务是否可用"""
        return AIConfig.ENABLED and self.ai_parser.is_available()

    def _reload_config(self):
        """从数据库热加载AI配置"""
        try:
            from database import SessionLocal
            db = SessionLocal()
            try:
                AIConfig.load_from_db(db)
            finally:
                db.close()
        except Exception:
            pass  # 热加载失败继续使用默认配置

    def parse_resume(
        self,
        text: str,
        schema_fields: List
    ) -> Dict[str, Any]:
        """
        解析简历（AI优先，降级到规则引擎）
        Returns:
            {
                'candidate_name': str,
                'parsed_fields': {字段名: {value, confidence, source}},
                'parsed_education': ...,
                ...
                'parse_method': 'ai' | 'rule',
                'raw_text': str
            }
        """
        self._reload_config()  # 热加载最新配置
        # 优先使用AI解析
        if self.is_ai_available():
            ai_result = self.ai_parser.parse(text, schema_fields)
            if ai_result is not None:
                logger.info("使用AI解析简历")
                return self._normalize_ai_parse_result(text, ai_result, schema_fields)
            logger.warning("AI解析返回空，降级到规则引擎")

        # 降级到规则引擎
        logger.info("使用规则引擎解析简历（降级）")
        rule_result = self.rule_engine.parse_resume(text, schema_fields)
        rule_result['parse_method'] = 'rule'
        return rule_result

    def _normalize_ai_parse_result(
        self,
        text: str,
        ai_fields: Dict[str, Any],
        schema_fields: List
    ) -> Dict[str, Any]:
        """将AI解析结果规范化为统一格式"""
        result = {
            'candidate_name': None,
            'parsed_fields': {},
            'parse_method': 'ai',
            'raw_text': text[:5000]
        }

        # 提取姓名（AI可能没有专门提取姓名，用规则引擎补一下）
        name_field = self.rule_engine.extractor_registry._extract_name(text)
        result['candidate_name'] = name_field.value

        # 整理AI提取的字段
        for field in schema_fields:
            field_name = field.field_name
            value = ai_fields.get(field_name)
            result['parsed_fields'][field_name] = {
                'value': value,
                'confidence': 0.85 if value is not None else 0.2,
                'source': 'AI语义提取'
            }

        # 兼容扁平字段
        pf = result['parsed_fields']
        result['parsed_education'] = pf.get('学历', {}).get('value')
        result['parsed_experience'] = pf.get('工作年限', {}).get('value')
        result['parsed_skills'] = pf.get('核心技能', {}).get('value')
        result['parsed_industry'] = pf.get('行业经验', {}).get('value')
        result['parsed_certificates'] = pf.get('证书', {}).get('value')
        result['parsed_projects'] = pf.get('项目经验', {}).get('value')

        return result

    def match_resume_to_position(
        self,
        resume_data: Dict[str, Any],
        schema_fields: List,
        position_name: str = "",
        company_name: str = ""
    ) -> Dict[str, Any]:
        """
        简历匹配岗位（AI优先，降级到规则引擎）
        Returns:
            {
                'passed_hard': bool,
                'reject_reason': str,
                'total_score': int,
                'dimension_scores': {字段名: 分数},
                'match_details': [...],
                'match_highlights': str,
                'match_gaps': str,
                'match_method': 'ai' | 'rule'
            }
        """
        self._reload_config()  # 热加载最新配置（确保系统设置中关闭AI后立即生效）
        # 准备简历字段值（AI匹配需要简单的字段名->值映射）
        parsed_fields = resume_data.get('parsed_fields', {})
        simple_resume = {}
        for field_name, field_data in parsed_fields.items():
            simple_resume[field_name] = field_data.get('value')

        # 优先使用AI匹配
        if self.is_ai_available():
            try:
                ai_result = self.ai_matcher.match(
                    position_name=position_name,
                    company_name=company_name,
                    schema_fields=schema_fields,
                    parsed_resume=simple_resume
                )
                if ai_result is not None:
                    logger.info(f"使用AI匹配：{company_name}/{position_name}")
                    return self._normalize_ai_match_result(ai_result, schema_fields)
                logger.warning("AI匹配返回空，降级到规则引擎")
            except Exception as e:
                logger.error(f"AI匹配异常，降级到规则引擎：{e}", exc_info=True)
        
        # 降级到规则引擎
        logger.info(f"使用规则引擎匹配（降级）：{company_name}/{position_name}")
        rule_result = self.rule_engine.match_resume_to_position(resume_data, schema_fields)
        rule_result['match_method'] = 'rule'
        rule_result['match_highlights'] = ''
        rule_result['match_gaps'] = ''
        return rule_result

    def _normalize_ai_match_result(
        self,
        ai_result: Dict[str, Any],
        schema_fields: List
    ) -> Dict[str, Any]:
        """将AI匹配结果规范化为统一格式"""
        dimension_scores = ai_result.get('dimension_scores', {})

        # 构建匹配详情
        match_details = []
        for field in schema_fields:
            field_name = field.field_name
            score = dimension_scores.get(field_name, 0)
            match_details.append({
                'field_name': field_name,
                'requirement': field.requirement,
                'resume_value': '',  # AI结果不包含简历值，留空
                'passed': ai_result['passed_hard'] or score >= 60,
                'score': score,
                'weight': field.weight,
                'is_hard': field.is_hard,
                'reason': ''
            })

        return {
            'passed_hard': ai_result['passed_hard'],
            'reject_reason': ai_result['reject_reason'],
            'total_score': ai_result['total_score'],
            'dimension_scores': dimension_scores,
            'match_details': match_details,
            'match_highlights': ai_result.get('match_highlights', ''),
            'match_gaps': ai_result.get('match_gaps', ''),
            'match_method': 'ai'
        }


# 全局单例
unified_ai_service = UnifiedAIService()
