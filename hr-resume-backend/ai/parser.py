# -*- coding: utf-8 -*-
"""
AI简历智能解析器
依托人工配置的Schema，通过AI大模型像真人一样阅读和理解简历
核心设计：
1. AI通读完整简历，理解整体结构和内容（不依赖固定段落关键词）
2. 按字段语义分组，逐组调用AI从全文中智能提取
3. AI自由定位相关内容，适应各种格式、排版、标题风格的简历
4. 保留关键词分段解析器作为AI不可用时的降级方案
"""
import json
import re
import logging
from typing import List, Dict, Any, Optional, Tuple

from .client import ai_client, AIClientError
from .config import AIConfig

logger = logging.getLogger(__name__)


# ============================================================
# 降级方案：关键词分段解析器（AI不可用时使用）
# ============================================================

class ResumeSectionParser:
    """
    基于关键词的简历段落分割器（降级方案）
    将简历文本按标准段落分割，便于分段解析
    """

    SECTION_DEFINITIONS = [
        ('基本信息', ['个人信息', '基本信息', '个人资料', '联系方式'], ['教育背景', '工作经历', '求职意向', '技能', '项目', '证书', '自我评价']),
        ('求职意向', ['求职意向', '求职目标', '期望职位', '应聘岗位', '意向岗位'], ['教育背景', '工作经历', '技能', '项目', '证书', '自我评价']),
        ('教育背景', ['教育背景', '教育经历', '学历背景', '学习经历'], ['工作经历', '实习经历', '技能', '项目', '证书', '自我评价', '求职意向']),
        ('工作经历', ['工作经历', '工作经验', '职业经历', '实习经历', '工作履历'], ['教育背景', '项目经验', '项目经历', '技能', '证书', '自我评价', '求职意向']),
        ('技能特长', ['技能特长', '专业技能', '核心技能', '技术栈', '掌握技能', '技能', '专业能力'], ['工作经历', '教育背景', '项目经验', '项目经历', '证书', '自我评价', '求职意向']),
        ('项目经验', ['项目经验', '项目经历', '项目介绍', '主要项目', '项目实践'], ['工作经历', '教育背景', '技能', '证书', '自我评价', '求职意向']),
        ('证书荣誉', ['证书荣誉', '资格证书', '专业证书', '证书', '认证', '荣誉奖项', '获奖经历', '荣誉'], ['工作经历', '教育背景', '技能', '项目', '自我评价', '求职意向']),
        ('自我评价', ['自我评价', '个人评价', '个人总结', '自我描述', '个人简介'], None),
    ]

    @classmethod
    def parse_sections(cls, text: str) -> Dict[str, str]:
        lines = text.split('\n')
        sections = {}
        total_lines = len(lines)

        for sec_name, start_keywords, end_keywords in cls.SECTION_DEFINITIONS:
            start_idx = -1
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                if any(kw in line_stripped for kw in start_keywords):
                    if len(line_stripped) < 20 or line_stripped.startswith(tuple(start_keywords)):
                        start_idx = i + 1
                        break
            if start_idx == -1:
                continue
            end_idx = total_lines
            if end_keywords:
                for i in range(start_idx, total_lines):
                    line_stripped = lines[i].strip()
                    if any(kw in line_stripped for kw in end_keywords):
                        if len(line_stripped) < 20 or line_stripped.startswith(tuple(end_keywords)):
                            end_idx = i
                            break
            section_text = '\n'.join(lines[start_idx:end_idx]).strip()
            if section_text:
                sections[sec_name] = section_text
        if not sections:
            sections['全文'] = text
        return sections

    @classmethod
    def get_section_for_field(cls, field_name: str) -> List[str]:
        field_lower = field_name.lower()
        if any(kw in field_lower for kw in ['学历', '教育', '学位', '学校', '毕业', '专业']):
            return ['教育背景', '基本信息', '全文']
        if any(kw in field_lower for kw in ['工作年限', '工作经验', '从业年限', '经验年限', '工龄', '年限']):
            return ['工作经历', '基本信息', '求职意向', '全文']
        if any(kw in field_lower for kw in ['技能', '技术栈', '掌握', '能力', '专长']):
            return ['技能特长', '工作经历', '全文']
        if any(kw in field_lower for kw in ['行业', '行业背景', '所属行业']):
            return ['工作经历', '求职意向', '全文']
        if any(kw in field_lower for kw in ['证书', '资格', '认证', '荣誉', '获奖']):
            return ['证书荣誉', '教育背景', '全文']
        if any(kw in field_lower for kw in ['项目', '项目经验', '项目经历']):
            return ['项目经验', '工作经历', '全文']
        if any(kw in field_lower for kw in ['姓名', '名字', '候选人']):
            return ['基本信息', '全文']
        return ['全文']


# ============================================================
# 主方案：AI智能简历理解器
# ============================================================

class AIResumeParser:
    """
    AI驱动的简历智能解析器
    核心思路：让AI像真人一样通读完整简历，理解整体结构和内容，
    根据Schema字段定义，从全文中智能定位并提取结构化信息。
    不依赖固定段落关键词，适应各种格式、排版、标题风格的简历。
    """

    # 系统提示词：强调像真人一样阅读理解
    SYSTEM_PROMPT = """你是一个经验丰富的HR招聘专家，拥有10年以上简历筛选经验。
你的任务是像真人一样仔细阅读简历，理解简历的整体结构和内容，从中精准提取结构化信息。

阅读和提取原则：
1. 【通读理解】先完整阅读简历全文，理解候选人的整体背景，不要断章取义
2. 【智能定位】根据需要提取的字段，在简历全文中自由定位最相关的内容区域，不受固定段落标题限制
3. 【语义理解】基于语义理解提取信息，不要简单关键词匹配，要理解上下文和隐含含义
4. 【格式适应】简历可能有各种格式、排版、标题风格（如"工作履历""职业经历""Experience"等），你要能识别并适应
5. 【信息整合】如果某个信息分散在简历多处，综合判断后给出最准确的结果
6. 【不编造】如果简历中没有明确提到某个字段的信息，值设为null，不要编造或猜测
7. 【标准化】学历统一为：博士/硕士/本科/大专/高中/中专/初中及以下；工作年限提取为数字
8. 【多值字段】技能、行业、证书等多值字段，用英文逗号分隔多个值
9. 【准确优先】提取要准确，不确定的信息宁可设为null也不要错误提取"""

    # 字段语义分组定义（用于控制每次AI调用的字段数量，提高准确率）
    FIELD_GROUPS = [
        {
            'group_name': '个人基本信息',
            'keywords': ['姓名', '名字', '性别', '年龄', '电话', '手机', '邮箱', '地址', '所在地', '籍贯', '出生', '民族', '政治面貌', '婚姻', '照片'],
            'description': '候选人的个人基本信息，通常在简历开头'
        },
        {
            'group_name': '求职意向',
            'keywords': ['求职意向', '求职目标', '期望职位', '应聘岗位', '意向岗位', '期望薪资', '期望城市', '到岗时间', '工作状态'],
            'description': '候选人的求职意向和期望'
        },
        {
            'group_name': '教育背景',
            'keywords': ['学历', '教育', '学位', '学校', '毕业', '专业', '院系', 'GPA', '成绩', '奖学金', '留学'],
            'description': '候选人的教育背景和学历信息'
        },
        {
            'group_name': '工作经验',
            'keywords': ['工作年限', '工作经验', '从业年限', '经验年限', '工龄', '年限', '行业', '行业背景', '所属行业', '当前职位', '当前公司', '工作经历'],
            'description': '候选人的工作经验、年限和行业背景'
        },
        {
            'group_name': '技能能力',
            'keywords': ['技能', '技术栈', '掌握', '能力', '专长', '编程语言', '框架', '工具', '软件', '语言能力', '外语'],
            'description': '候选人的专业技能和能力'
        },
        {
            'group_name': '项目成果',
            'keywords': ['项目', '项目经验', '项目经历', '项目成果', '业绩', '成就', '获奖', '专利', '论文', '作品'],
            'description': '候选人的项目经验和成果成就'
        },
        {
            'group_name': '证书资质',
            'keywords': ['证书', '资格', '认证', '资质', '执照', '执业'],
            'description': '候选人的专业证书和资格认证'
        },
        {
            'group_name': '自我评价',
            'keywords': ['自我评价', '个人评价', '个人总结', '自我描述', '个人简介', '性格', '兴趣', '爱好'],
            'description': '候选人的自我评价和个人特质'
        },
    ]

    def __init__(self):
        self.client = ai_client
        self.section_parser = ResumeSectionParser()  # 降级方案

    def is_available(self) -> bool:
        """检查AI解析是否可用"""
        return AIConfig.ENABLED and self.client.is_available()

    def _build_field_description(self, schema_fields: List) -> str:
        """构建字段描述"""
        lines = []
        for i, field in enumerate(schema_fields, 1):
            field_type_desc = {
                '枚举': '枚举值',
                '数字': '数字',
                '多选': '多值（逗号分隔）',
                '单选': '单值'
            }.get(field.field_type, field.field_type)

            hard_desc = "【硬性条件】" if field.is_hard else ""
            lines.append(
                f"{i}. 字段名：{field.field_name}\n"
                f"   类型：{field_type_desc}\n"
                f"   匹配要求：{field.requirement}\n"
                f"   {hard_desc}"
            )
        return "\n".join(lines)

    def _group_fields_by_semantics(self, schema_fields: List) -> List[Dict[str, Any]]:
        """
        按字段语义智能分组
        不依赖固定段落名，而是根据字段名称的语义关键词分组
        返回: [{group_name, fields, description}, ...]
        """
        groups = []
        unassigned = []

        for field in schema_fields:
            field_name = field.field_name
            field_lower = field_name.lower()
            assigned = False

            for group_def in self.FIELD_GROUPS:
                if any(kw in field_lower for kw in group_def['keywords']):
                    # 找到对应组
                    found = False
                    for g in groups:
                        if g['group_name'] == group_def['group_name']:
                            g['fields'].append(field)
                            found = True
                            break
                    if not found:
                        groups.append({
                            'group_name': group_def['group_name'],
                            'description': group_def['description'],
                            'fields': [field]
                        })
                    assigned = True
                    break

            if not assigned:
                unassigned.append(field)

        # 未分配的字段放到"其他信息"组
        if unassigned:
            groups.append({
                'group_name': '其他信息',
                'description': '其他需要提取的信息',
                'fields': unassigned
            })

        return groups

    def _extract_group_with_ai(
        self,
        group_name: str,
        group_description: str,
        resume_text: str,
        fields: List
    ) -> Dict[str, Any]:
        """
        对一组字段调用AI从全文中智能提取
        核心：AI看到的是完整简历文本，自由定位相关内容，不受固定段落限制

        Args:
            group_name: 字段组名称
            group_description: 组描述
            resume_text: 完整简历文本
            fields: 需要提取的字段列表
        Returns:
            解析结果 {字段名: 值}
        """
        if not fields:
            return {}

        field_names = [f.field_name for f in fields]
        fields_json_template = {name: "提取到的值或null" for name in field_names}
        field_desc = self._build_field_description(fields)

        user_prompt = f"""请仔细阅读以下完整简历，从中提取【{group_name}】相关的字段信息。

## 字段组说明
{group_description}

## 需要提取的字段定义：
{field_desc}

## 完整简历内容：
```
{resume_text}
```

## 提取要求：
1. 像真人一样通读完整简历，理解候选人的整体背景
2. 在简历全文中自由定位最相关的内容，不受固定段落标题限制
3. 基于语义理解提取，不要简单关键词匹配
4. 如果信息分散在多处，综合判断后给出最准确的结果
5. 如果简历中没有明确提到某个字段，值设为null
6. 多值字段用英文逗号分隔

## 输出格式：
返回JSON对象，key为字段名，value为提取到的值：
{json.dumps(fields_json_template, ensure_ascii=False, indent=2)}"""

        try:
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ]
            result = self.client.chat_json(messages, temperature=0.1)

            # 验证和清洗
            cleaned = {}
            for name in field_names:
                value = result.get(name)
                if isinstance(value, str) and value.strip() in ['', '无', '未知', '未提及', 'N/A', 'null', '没有', '暂无']:
                    value = None
                cleaned[name] = value
            return cleaned
        except Exception as e:
            logger.warning(f"字段组[{group_name}]AI解析失败: {str(e)}")
            return {name: None for name in field_names}

    def _analyze_resume_structure(self, resume_text: str) -> Optional[Dict[str, Any]]:
        """
        （可选优化）AI简历结构理解
        让AI先通读简历，分析简历的整体结构，输出内容区块分析
        这一步帮助建立对简历的整体认知，类似真人先通读一遍
        返回: {sections: [{name, content_summary, location}], overall_impression}
        """
        user_prompt = f"""请分析以下简历的整体结构和内容布局。

简历可能有各种格式、排版、标题风格，请像真人一样理解它的结构。

## 简历内容：
```
{resume_text}
```

## 请输出：
1. 简历包含哪些主要内容区块（如个人信息、教育、工作、技能、项目、证书等，用简历中实际的标题或你理解的区块名）
2. 每个区块的内容摘要（一句话）
3. 简历的整体格式特点（如分栏、表格、时间线等）

输出JSON格式：
{{
  "sections": [
    {{"name": "区块名称", "summary": "内容摘要"}}
  ],
  "format_note": "格式特点说明",
  "overall_impression": "整体印象"
}}"""

        try:
            messages = [
                {"role": "system", "content": "你是一个专业的简历分析师，擅长理解各种格式的简历结构。"},
                {"role": "user", "content": user_prompt}
            ]
            result = self.client.chat_json(messages, temperature=0.1)
            logger.info(f"AI简历结构理解完成: 识别到{len(result.get('sections', []))}个区块")
            return result
        except Exception as e:
            logger.warning(f"AI简历结构理解失败（不影响主流程）: {str(e)}")
            return None

    def parse(self, resume_text: str, schema_fields: List) -> Optional[Dict[str, Any]]:
        """
        使用AI智能解析简历
        核心流程：
        1. （可选）AI通读简历，理解整体结构
        2. 按字段语义分组
        3. 逐组调用AI，从全文中智能提取
        4. 合并结果，对空值字段二次尝试

        Args:
            resume_text: 简历原始文本
            schema_fields: Schema字段列表
        Returns:
            解析结果字典 {字段名: 值}，失败返回None
        """
        if not self.is_available():
            logger.info("AI解析不可用，将使用规则引擎降级")
            return None

        if not schema_fields:
            logger.warning("Schema字段为空，无法解析")
            return None

        try:
            # 第一步：（可选优化）AI通读简历，理解整体结构
            # 这一步帮助建立整体认知，但不影响后续提取，失败也不阻塞
            structure = self._analyze_resume_structure(resume_text)
            if structure:
                logger.info(f"简历结构: {[s.get('name') for s in structure.get('sections', [])]}")

            # 第二步：按字段语义分组
            field_groups = self._group_fields_by_semantics(schema_fields)
            logger.info(f"字段分组: {[(g['group_name'], len(g['fields'])) for g in field_groups]}")

            # 第三步：逐组调用AI，从全文中智能提取
            final_result = {}
            for group in field_groups:
                group_name = group['group_name']
                fields = group['fields']
                logger.info(f"正在提取[{group_name}]，字段数: {len(fields)}")

                group_result = self._extract_group_with_ai(
                    group_name=group_name,
                    group_description=group['description'],
                    resume_text=resume_text,
                    fields=fields
                )
                final_result.update(group_result)

            # 第四步：对空值字段进行二次尝试（合并所有空值字段，从全文再提取一次）
            field_names = [f.field_name for f in schema_fields]
            empty_fields = [f for f in schema_fields if final_result.get(f.field_name) is None]

            if empty_fields and len(empty_fields) <= 5:
                logger.info(f"对 {len(empty_fields)} 个空值字段进行二次提取: {[f.field_name for f in empty_fields]}")
                retry_result = self._extract_group_with_ai(
                    group_name='补充提取',
                    group_description='对首次提取为空的字段进行二次确认',
                    resume_text=resume_text,
                    fields=empty_fields
                )
                # 只覆盖确实有值的字段
                for name, value in retry_result.items():
                    if value is not None:
                        final_result[name] = value

            # 第五步：确保所有字段都有结果
            for name in field_names:
                if name not in final_result:
                    final_result[name] = None

            extracted_count = len([v for v in final_result.values() if v is not None])
            logger.info(f"AI智能解析完成，提取到 {extracted_count}/{len(field_names)} 个字段")
            return final_result

        except AIClientError as e:
            logger.error(f"AI简历解析失败: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"AI简历解析异常: {str(e)}", exc_info=True)
            return None

    def parse_with_fallback(self, resume_text: str, schema_fields: List) -> Optional[Dict[str, Any]]:
        """
        带降级的解析：优先AI智能解析，失败后降级为关键词分段解析
        """
        # 优先AI智能解析
        result = self.parse(resume_text, schema_fields)
        if result is not None:
            return result

        # 降级：关键词分段 + AI逐段提取
        logger.info("AI智能解析不可用，降级为关键词分段解析")
        try:
            sections = self.section_parser.parse_sections(resume_text)

            # 按段落分组字段
            section_fields: Dict[str, List] = {}
            unassigned_fields = []

            for field in schema_fields:
                preferred_sections = self.section_parser.get_section_for_field(field.field_name)
                assigned = False
                for sec_name in preferred_sections:
                    if sec_name in sections:
                        if sec_name not in section_fields:
                            section_fields[sec_name] = []
                        section_fields[sec_name].append(field)
                        assigned = True
                        break
                if not assigned:
                    unassigned_fields.append(field)

            if unassigned_fields:
                if '全文' not in section_fields:
                    section_fields['全文'] = []
                section_fields['全文'].extend(unassigned_fields)
                if '全文' not in sections:
                    sections['全文'] = resume_text

            # 逐段提取（复用AI提取逻辑，但传入段落文本）
            final_result = {}
            for sec_name, fields in section_fields.items():
                sec_text = sections.get(sec_name, '')
                if not sec_text:
                    for f in fields:
                        final_result[f.field_name] = None
                    continue
                # 降级时也用AI提取（如果可用），只是输入是段落文本
                if self.is_available():
                    group_result = self._extract_group_with_ai(
                        group_name=sec_name,
                        group_description=f'简历的{sec_name}段落',
                        resume_text=sec_text,
                        fields=fields
                    )
                    final_result.update(group_result)
                else:
                    for f in fields:
                        final_result[f.field_name] = None

            field_names = [f.field_name for f in schema_fields]
            for name in field_names:
                if name not in final_result:
                    final_result[name] = None

            return final_result

        except Exception as e:
            logger.error(f"降级解析也失败: {str(e)}")
            return None


# 全局单例
ai_resume_parser = AIResumeParser()
