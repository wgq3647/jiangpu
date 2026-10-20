"""
AI智能匹配器
基于AI语义理解，将简历与JD Schema要求进行深度匹配
输出硬性淘汰判断、多维度打分、匹配理由
"""
import json
import logging
from typing import List, Dict, Any, Optional

from .client import ai_client, AIClientError
from .config import AIConfig

logger = logging.getLogger(__name__)


class AIMatchEngine:
    """
    AI驱动的智能匹配引擎
    让AI基于语义理解判断简历与岗位要求的匹配度
    """

    SYSTEM_PROMPT = """你是一个资深的HR招聘专家，擅长评估候选人与岗位的匹配度。

你的任务：
1. 仔细阅读候选人简历信息和岗位招聘要求（Schema）
2. 对每个匹配维度进行语义层面的评估，不要只看关键词字面匹配
3. 判断是否满足硬性条件，不满足则直接淘汰
4. 对通过硬性条件的维度进行0-100分的匹配度打分
5. 给出具体的匹配理由和亮点/不足分析

评分标准：
- 90-100分：完全匹配，超出预期
- 75-89分：良好匹配，基本满足且有亮点
- 60-74分：基本匹配，满足核心要求
- 40-59分：部分匹配，有明显不足
- 0-39分：不匹配"""

    def __init__(self):
        self.client = ai_client

    def is_available(self) -> bool:
        """检查AI匹配是否可用"""
        return AIConfig.ENABLED and self.client.is_available()

    def _build_schema_description(self, schema_fields: List) -> str:
        """构建Schema要求描述"""
        lines = []
        for i, field in enumerate(schema_fields, 1):
            hard_mark = "⭐【硬性淘汰条件】" if field.is_hard else "柔性匹配"
            lines.append(
                f"{i}. {field.field_name}（{hard_mark}，权重{field.weight}分）\n"
                f"   要求：{field.requirement}"
            )
        return "\n".join(lines)

    def _build_resume_description(self, parsed_resume: Dict[str, Any]) -> str:
        """构建简历信息描述"""
        lines = []
        for field_name, value in parsed_resume.items():
            if value is not None and value != "":
                lines.append(f"- {field_name}：{value}")
        return "\n".join(lines) if lines else "（未提取到有效信息）"

    def _build_user_prompt(
        self,
        position_name: str,
        company_name: str,
        schema_fields: List,
        parsed_resume: Dict[str, Any]
    ) -> str:
        """构建匹配Prompt"""
        schema_desc = self._build_schema_description(schema_fields)
        resume_desc = self._build_resume_description(parsed_resume)

        field_names = [f.field_name for f in schema_fields]
        dimension_scores = {name: 0 for name in field_names}

        return f"""请评估以下候选人与岗位的匹配度。

## 岗位信息
- 公司：{company_name}
- 岗位：{position_name}

## 岗位招聘要求（Schema）
{schema_desc}

## 候选人简历信息
{resume_desc}

## 评估要求
1. 逐个维度评估，注意语义匹配而非字面匹配
2. 硬性条件不满足则整体淘汰，reject_reason说明具体原因
3. 每个维度给出0-100分的匹配度
4. total_score为各维度按权重加权后的总分

## 输出JSON格式：
{{
  "passed_hard": true/false,
  "reject_reason": "淘汰原因（通过则为空字符串）",
  "total_score": 0-100的整数,
  "dimension_scores": {json.dumps(dimension_scores, ensure_ascii=False)},
  "match_highlights": "匹配亮点（简短）",
  "match_gaps": "不足/差距（简短）"
}}"""

    def match(
        self,
        position_name: str,
        company_name: str,
        schema_fields: List,
        parsed_resume: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        使用AI进行简历-岗位匹配
        Args:
            position_name: 岗位名称
            company_name: 公司名称
            schema_fields: Schema字段列表
            parsed_resume: 解析后的简历信息 {字段名: 值}
        Returns:
            匹配结果字典，失败返回None
        """
        if not self.is_available():
            logger.info("AI匹配不可用，将使用规则引擎降级")
            return None

        if not schema_fields:
            logger.warning("Schema字段为空，无法匹配")
            return None

        try:
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": self._build_user_prompt(
                    position_name, company_name, schema_fields, parsed_resume
                )}
            ]

            logger.info(f"开始AI匹配：{company_name}/{position_name}")
            result = self.client.chat_json(messages, temperature=0.2)

            # 规范化结果
            normalized = {
                'passed_hard': bool(result.get('passed_hard', False)),
                'reject_reason': str(result.get('reject_reason', '') or ''),
                'total_score': int(result.get('total_score', 0)),
                'dimension_scores': result.get('dimension_scores', {}),
                'match_highlights': str(result.get('match_highlights', '') or ''),
                'match_gaps': str(result.get('match_gaps', '') or ''),
            }

            # 确保分数在合理范围
            normalized['total_score'] = max(0, min(100, normalized['total_score']))

            logger.info(
                f"AI匹配完成：{company_name}/{position_name} - "
                f"{'通过' if normalized['passed_hard'] else '淘汰'} "
                f"得分:{normalized['total_score']}"
            )
            return normalized

        except AIClientError as e:
            logger.error(f"AI匹配失败: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"AI匹配异常: {str(e)}", exc_info=True)
            return None


# 全局单例
ai_match_engine = AIMatchEngine()
