"""
AI语义规则引擎 - Schema驱动的简历解析与智能匹配

核心设计理念：
1. 解析器不硬编码字段，而是根据人工配置的Schema动态提取
2. 匹配要求通过自然语言解析器转换为结构化规则
3. 支持自定义字段、小众岗位需求，通过语义相似度实现柔性匹配
"""

import re
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

# 向量语义嵌入（关键词匹配和LLM之间的中间层）
try:
    from ai.embedding import semantic_embedding
except ImportError:
    semantic_embedding = None


# ============================================================
# 第一部分：语义字段提取器（Schema驱动，动态适配）
# ============================================================

@dataclass
class ExtractedField:
    """提取结果"""
    field_name: str
    value: Any
    confidence: float  # 提取置信度 0-1
    source_text: str = ""  # 提取来源的原文片段


class FieldExtractorRegistry:
    """
    字段提取器注册表
    根据字段名称的语义自动匹配提取策略
    支持自定义字段扩展
    """

    def __init__(self):
        self.extractors = {}
        self._register_builtin_extractors()

    def _register_builtin_extractors(self):
        """注册内置提取器"""
        # 学历类
        self.register(['学历', '教育背景', '最高学历', '学位'], self._extract_education)
        # 年限类
        self.register(['工作年限', '工作经验', '从业年限', '经验年限', '工龄'], self._extract_experience)
        # 技能类
        self.register(['核心技能', '技能', '专业技能', '技术栈', '掌握技能'], self._extract_skills)
        # 行业类
        self.register(['行业经验', '行业背景', '所属行业', '行业'], self._extract_industry)
        # 证书类
        self.register(['证书', '资格证书', '专业证书', '认证'], self._extract_certificates)
        # 项目类
        self.register(['项目经验', '项目经历', '项目', '项目经验'], self._extract_projects)
        # 姓名类
        self.register(['姓名', '候选人姓名', '名字'], self._extract_name)
        # 学校类
        self.register(['毕业院校', '学校', '院校', '大学'], self._extract_school)
        # 专业类
        self.register(['专业', '所学专业'], self._extract_major)

    @staticmethod
    def _extract_section(text: str, start_keywords: List[str], end_keywords: List[str] = None) -> str:
        """
        定位并提取简历中的特定段落
        如"技能特长"段落、"证书荣誉"段落、"工作经历"段落
        """
        lines = text.split('\n')
        start_idx = -1
        for i, line in enumerate(lines):
            if any(kw in line for kw in start_keywords):
                start_idx = i + 1
                break
        if start_idx == -1:
            return ""

        end_idx = len(lines)
        if end_keywords:
            for i in range(start_idx, len(lines)):
                if any(kw in lines[i] for kw in end_keywords):
                    end_idx = i
                    break
        return '\n'.join(lines[start_idx:end_idx]).strip()

    def register(self, keywords: List[str], extractor_func):
        """注册新的字段提取器（支持扩展自定义字段）"""
        for kw in keywords:
            self.extractors[kw.lower()] = extractor_func

    def match_extractor(self, field_name: str):
        """根据字段名称语义匹配提取器"""
        field_name_lower = field_name.lower()
        # 精确匹配
        if field_name_lower in self.extractors:
            return self.extractors[field_name_lower]
        # 模糊匹配（包含关系）
        for key, func in self.extractors.items():
            if key in field_name_lower or field_name_lower in key:
                return func
        # 未匹配到，使用通用提取器
        return self._generic_extract

    # ========== 内置提取器实现 ==========

    EDUCATION_LEVELS = {
        '博士': 5, '博士后': 5, '博士研究生': 5,
        '硕士': 4, '研究生': 4, '硕士研究生': 4, 'MBA': 4,
        '本科': 3, '学士': 3, '大学本科': 3,
        '大专': 2, '专科': 2, '高职': 2,
        '高中': 1, '中专': 1, '职高': 1
    }

    def _extract_education(self, text: str) -> ExtractedField:
        """提取学历"""
        for edu in ['博士后', '博士研究生', '博士', '硕士研究生', '硕士', '研究生', 'MBA',
                     '大学本科', '本科', '学士', '大专', '专科', '高职', '高中', '中专']:
            if edu in text:
                return ExtractedField('学历', edu, 0.9, edu)
        return ExtractedField('学历', None, 0.1, '')

    def _extract_experience(self, text: str) -> ExtractedField:
        """提取工作年限"""
        patterns = [
            r'(\d+)\s*年(?:以上)?(?:工作)?(?:经验|从业|经历)',
            r'(\d+)\s*年(?:工作|从业)?经验',
            r'工作\s*(\d+)\s*年',
            r'(\d+)\s*年(?:以上)?'
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                years = int(match.group(1))
                return ExtractedField('工作年限', years, 0.85, match.group(0))
        return ExtractedField('工作年限', None, 0.1, '')

    SKILL_DICTIONARY = [
        # ===== 编程语言 =====
        'Python', 'Java', 'C++', 'C#', 'Go', 'Rust', 'PHP', 'Ruby', 'Swift', 'Kotlin',
        'JavaScript', 'TypeScript', 'HTML', 'CSS', 'SQL', 'R', 'MATLAB', 'Scala',
        # ===== 数据/AI =====
        '数据分析', '数据挖掘', '大数据', '机器学习', '深度学习', 'NLP', '自然语言处理',
        '计算机视觉', '推荐系统', '知识图谱', '数据建模', '数据仓库', 'ETL',
        # ===== 框架/工具 =====
        'TensorFlow', 'PyTorch', 'Keras', 'Scikit-learn', 'Pandas', 'NumPy',
        'Hadoop', 'Spark', 'Flink', 'Kafka', 'Hive', 'HBase', 'Redis', 'MongoDB',
        'React', 'Vue', 'Angular', 'Node.js', 'Spring', 'Spring Boot', 'Django', 'Flask',
        'Docker', 'Kubernetes', 'Jenkins', 'Git', 'Linux',
        # ===== 设计/产品 =====
        'Axure', 'Figma', 'Photoshop', 'Sketch', 'XD', '产品经理', '用户增长',
        '用户体验', '交互设计', 'UI设计', '需求分析', '产品设计', '原型设计',
        # ===== 办公/分析工具 =====
        'Excel', 'PPT', 'Word', 'Tableau', 'Power BI', 'FineBI', 'SPSS', 'SAS',
        # ===== 财务会计类 =====
        '财务分析', '财务管理', '财务报表', '账务处理', '会计核算', '审计',
        '税务申报', '纳税申报', '税务筹划', '税收筹划', '预算管理', '预算编制',
        '成本控制', '成本核算', '资金管理', '应收账款', '应付账款', '财务系统',
        '用友', '金蝶', 'SAP', 'Oracle财务', '合并报表', '内控', '风险管理',
        '财务共享', '业财融合', '管理会计', '财务BP',
        # ===== 市场营销类 =====
        '市场营销', '品牌推广', '品牌策划', '市场策划', '活动策划', '活动执行',
        '新媒体运营', '内容运营', '用户运营', '社群运营', '电商运营', '短视频运营',
        '直播运营', 'SEM', 'SEO', '信息流投放', '广告投放', '私域运营',
        '文案策划', '内容创作', '公众号运营', '小红书运营', '抖音运营',
        # ===== 人力资源类 =====
        '招聘', '招聘配置', '人才盘点', '绩效管理', '薪酬管理', '薪酬福利',
        '员工关系', '培训发展', '培训管理', '企业文化', '组织发展', 'OD',
        'HRBP', '人力资源规划', '人才发展', 'TD', '员工培训', '入离职管理',
        # ===== 行政/法务类 =====
        '行政管理', '办公管理', '会议管理', '档案管理', '采购管理', '后勤管理',
        '合同管理', '法律审核', '法律咨询', '合同审查', '知识产权', '合规管理',
        '诉讼', '仲裁',
        # ===== 供应链/物流类 =====
        '供应链', '供应链管理', '采购', '采购管理', '物流管理', '仓储管理',
        '库存管理', '生产计划', '物料管理', '供应商管理', '物流配送', '关务',
        # ===== 销售/商务类 =====
        '销售', '客户开发', '客户维护', '商务谈判', '大客户管理', '渠道管理',
        '销售管理', '业绩管理', '客户关系', 'CRM', '售前支持', '售后支持',
        # ===== 教育/培训类 =====
        '课程设计', '教学设计', '教学管理', '学生管理', '教研', '教学研究',
        '培训授课', '讲师', '教育咨询', '升学规划', '留学咨询',
        # ===== 医疗/健康类 =====
        '临床', '护理', '医学检验', '药学', '药剂', '公共卫生', '健康管理',
        '医疗器械', '医药销售', '医学编辑',
        # ===== 制造/工程类 =====
        '机械设计', '机械工程', '电气工程', '自动化', 'PLC', '工业设计',
        '质量管理', '质量控制', 'QC', 'QA', '生产管理', '车间管理', '设备管理',
        '工艺工程师', '结构设计', '电子电路', '嵌入式', '单片机',
        # ===== 建筑/房地产类 =====
        '建筑设计', '结构设计', '工程造价', '工程管理', '施工管理', '监理',
        '房地产开发', '置业顾问', '房产销售', '物业管理', '项目报批',
        # ===== 金融/银行类 =====
        '银行', '信贷', '风控', '风险控制', '投资理财', '财富管理', '证券',
        '基金', '保险', '金融产品', '客户服务', '柜员', '客户经理', '授信审批',
        # ===== 通用管理/软技能 =====
        '项目管理', '团队管理', '战略规划', '跨部门协作', '沟通能力', '组织协调',
        '问题解决', '决策能力', '领导力', '执行力', '抗压能力', '学习能力',
        # ===== 证书类技能 =====
        'PMP', 'NPDP', 'CPA', 'CFA', 'FRM', 'ACCA', 'CMA', '司法考试', '一级建造师',
        '教师资格证', '律师资格证', '注册会计师', '中级会计', '初级会计'
    ]

    def _extract_skills(self, text: str) -> ExtractedField:
        """提取技能（优先从"技能特长"段落提取，避免从自我评价等段落误提取）"""
        # 优先定位技能段落
        skill_section = self._extract_section(
            text,
            start_keywords=['技能特长', '专业技能', '核心技能', '技术栈', '掌握技能', '技能'],
            end_keywords=['工作经历', '教育背景', '项目经验', '项目经历', '证书', '自我评价', '个人信息', '求职意向']
        )
        search_text = skill_section if skill_section else text

        found = []
        text_lower = search_text.lower()
        for skill in self.SKILL_DICTIONARY:
            # 大小写不敏感匹配
            if skill.lower() in text_lower:
                found.append(skill)
        # 去重并保持顺序
        seen = set()
        unique = []
        for s in found:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        # 从工作经历补充提取技能（去重），捕捉职责描述中的技能词（如"税务筹划"）
        work_section = self._extract_section(
            text,
            start_keywords=['工作经历', '工作经验', '实习经历'],
            end_keywords=['教育背景', '项目经验', '技能', '证书', '自我评价']
        )
        if work_section:
            work_lower = work_section.lower()
            for skill in self.SKILL_DICTIONARY:
                if skill.lower() in work_lower and skill not in unique:
                    unique.append(skill)

        value = ','.join(unique) if unique else None
        confidence = 0.8 if unique else 0.2
        return ExtractedField('核心技能', value, confidence, value or '')

    INDUSTRY_DICTIONARY = [
        '互联网', '移动互联网', '电子商务', '电商', '金融', '金融科技', '银行', '证券',
        '保险', '基金', '教育', '在线教育', '医疗', '医疗健康', '生物医药', '制造',
        '智能制造', '汽车', '新能源', '房地产', '建筑', '游戏', '网络游戏', '社交',
        '搜索', '广告', '数字营销', '云计算', '人工智能', 'AI', '大数据', '物联网',
        '通信', '电信', '物流', '供应链', '零售', '快消', '餐饮', '旅游', '酒店',
        '文化娱乐', '传媒', '影视', '出版', '农业', '能源', '化工', '环保', '航空航天'
    ]

    def _extract_industry(self, text: str) -> ExtractedField:
        """提取行业背景（只从工作经历和求职意向提取，避免从学校/专业误提取）"""
        # 定位工作经历段落
        work_section = self._extract_section(
            text,
            start_keywords=['工作经历', '工作经验', '实习经历', '职业经历'],
            end_keywords=['教育背景', '项目经验', '项目经历', '技能', '证书', '自我评价', '个人信息']
        )
        # 也从求职意向中提取
        intent_section = self._extract_section(
            text,
            start_keywords=['求职意向', '求职目标', '期望职位'],
            end_keywords=['教育背景', '工作经历', '项目经验', '技能', '证书', '自我评价']
        )
        search_text = (work_section + '\n' + intent_section).strip()
        if not search_text:
            search_text = text

        found = []
        for industry in self.INDUSTRY_DICTIONARY:
            if industry in search_text:
                found.append(industry)
        # 去重
        unique = list(dict.fromkeys(found))
        value = ','.join(unique) if unique else None
        confidence = 0.75 if unique else 0.2
        return ExtractedField('行业经验', value, confidence, value or '')

    CERTIFICATE_DICTIONARY = [
        # 通用项目管理
        'PMP', 'NPDP',
        # 财务会计类
        'CPA', 'CFA', 'FRM', 'ACCA', 'CMA',
        '注册会计师', '注册税务师', '中级会计', '初级会计', '会计职称',
        '中级会计师', '初级会计师', '高级会计师', '税务师', '审计师',
        '经济师', '统计师', '资产评估师',
        # 建筑工程类
        '一级建造师', '二级建造师', '一级造价师', '二级造价师',
        '注册结构工程师', '注册岩土工程师', '注册安全工程师',
        # 法律类
        '教师资格证', '律师资格证', '法律职业资格', '司法考试',
        # 医疗类
        '执业医师', '执业药师', '护士资格证', '医师资格证',
        # 计算机类
        '计算机等级', '软件设计师', '系统架构师', '信息系统项目管理师',
        '网络工程师', '数据库系统工程师', '系统分析师',
        # 语言类
        '雅思', '托福', 'GRE', 'GMAT', '英语六级', '英语四级',
        'BEC', '日语能力考',
        # 其他
        '驾照', '驾驶证', '人力资源管理师', '心理咨询师', '导游证'
    ]

    def _extract_certificates(self, text: str) -> ExtractedField:
        """提取证书（优先从"证书荣誉"段落提取）"""
        # 优先定位证书段落
        cert_section = self._extract_section(
            text,
            start_keywords=['证书荣誉', '资格证书', '专业证书', '证书', '认证', '荣誉奖项', '获奖经历'],
            end_keywords=['工作经历', '教育背景', '项目经验', '项目经历', '技能', '自我评价', '个人信息', '求职意向']
        )
        search_text = cert_section if cert_section else text

        found = []
        text_lower = search_text.lower()
        for cert in self.CERTIFICATE_DICTIONARY:
            if cert.lower() in text_lower:
                found.append(cert)
        unique = list(dict.fromkeys(found))
        value = ','.join(unique) if unique else None
        confidence = 0.8 if unique else 0.2
        return ExtractedField('证书', value, confidence, value or '')

    def _extract_projects(self, text: str) -> ExtractedField:
        """提取项目经验（提取项目相关段落）"""
        # 简单实现：查找"项目"关键词附近的文本
        lines = text.split('\n')
        project_lines = []
        in_project = False
        for line in lines:
            if any(kw in line for kw in ['项目经验', '项目经历', '项目介绍', '主要项目']):
                in_project = True
                continue
            if in_project:
                if any(kw in line for kw in ['工作经历', '教育背景', '技能', '自我评价', '个人信息']):
                    break
                if line.strip():
                    project_lines.append(line.strip())
        value = '; '.join(project_lines[:5]) if project_lines else None
        confidence = 0.6 if project_lines else 0.2
        return ExtractedField('项目经验', value, confidence, value or '')

    def _extract_name(self, text: str) -> ExtractedField:
        """提取姓名"""
        # 清除BOM和不可见字符
        text = text.lstrip('\ufeff\u200b\u200c\u200d\ufeff').strip()

        # 策略1：优先匹配"姓名：张三"或"姓名: 张三"格式
        match = re.search(r'姓\s*名\s*[:：]\s*([\u4e00-\u9fa5·]{2,6})', text)
        if match:
            name = match.group(1).strip()
            return ExtractedField('姓名', name, 0.9, name)

        # 策略2：匹配"name: xxx"英文格式
        match = re.search(r'name\s*[:：]\s*([a-zA-Z\s]{2,30})', text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            return ExtractedField('姓名', name, 0.8, name)

        # 策略3：取文本第一行，如果是2-4个中文字且不是标签词
        first_line = text.strip().split('\n')[0].strip()
        # 再次清除可能的BOM
        first_line = first_line.lstrip('\ufeff\u200b').strip()
        match = re.match(r'^([\u4e00-\u9fa5·]{2,4})$', first_line)
        if match:
            name = match.group(1)
            exclude = ['求职', '简历', '应聘', '个人', '基本', '联系', '姓名', '性别', '年龄', '电话', '邮箱',
                       '学历', '本科', '硕士', '博士', '大专', '中专', '高中', '初中', '研究生',
                       '工作', '经验', '年限', '技能', '项目', '证书', '行业', '背景', '专业',
                       '学校', '大学', '学院', '教育', '自我', '评价', '求职意向', '期望', '薪资']
            if name not in exclude and not any(name.startswith(e) for e in exclude):
                return ExtractedField('姓名', name, 0.6, name)

        # 策略4：在文本前3行中寻找独立的人名词（排除所有标签词）
        lines = text.strip().split('\n')[:3]
        for line in lines:
            line = line.lstrip('\ufeff\u200b').strip()
            match = re.match(r'^([\u4e00-\u9fa5·]{2,4})(?:\s|[:：]|$)', line)
            if match:
                name = match.group(1)
                exclude = ['求职', '简历', '应聘', '个人', '基本', '联系', '姓名', '性别', '年龄', '电话', '邮箱',
                           '学历', '本科', '硕士', '博士', '大专', '中专', '高中', '初中', '研究生',
                           '工作', '经验', '年限', '技能', '项目', '证书', '行业', '背景', '专业',
                           '学校', '大学', '学院', '教育', '自我', '评价', '求职意向', '期望', '薪资',
                           '熟练', '熟悉', '掌握', '精通', '了解', '会用', '能够', '具有', '拥有']
                if name not in exclude and not any(name.startswith(e) for e in exclude):
                    return ExtractedField('姓名', name, 0.5, name)

        return ExtractedField('姓名', None, 0.1, '')

    def _extract_school(self, text: str) -> ExtractedField:
        """提取毕业院校"""
        match = re.search(r'([\u4e00-\u9fa5]{2,10}(?:大学|学院|学校))', text)
        if match:
            return ExtractedField('毕业院校', match.group(1), 0.8, match.group(1))
        return ExtractedField('毕业院校', None, 0.1, '')

    def _extract_major(self, text: str) -> ExtractedField:
        """提取专业"""
        match = re.search(r'([\u4e00-\u9fa5]{2,10}(?:专业|学|工程|管理))', text)
        if match:
            return ExtractedField('专业', match.group(1), 0.7, match.group(1))
        return ExtractedField('专业', None, 0.1, '')

    def _generic_extract(self, text: str, field_name: str = "自定义字段") -> ExtractedField:
        """
        通用提取器（用于未注册的自定义字段）
        策略：在文本中搜索字段名称关键词附近的内容
        """
        # 尝试在文本中找到字段名称附近的内容
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if field_name in line:
                # 提取冒号或空格后的内容
                match = re.search(r'[:：]\s*(.+?)(?:[,，;；\n]|$)', line)
                if match:
                    value = match.group(1).strip()
                    return ExtractedField(field_name, value, 0.6, value)
                # 如果当前行没有，看下一行
                if i + 1 < len(lines) and lines[i + 1].strip():
                    value = lines[i + 1].strip()[:100]
                    return ExtractedField(field_name, value, 0.5, value)
        return ExtractedField(field_name, None, 0.1, '')


# ============================================================
# 第二部分：匹配要求解析器（自然语言 -> 结构化规则）
# ============================================================

@dataclass
class ParsedRequirement:
    """解析后的匹配要求"""
    raw_text: str
    requirement_type: str  # 'threshold'（阈值型）, 'set'（集合型）, 'text'（文本型）, 'custom'
    operator: str = ""  # '>=', '<=', '==', 'contains', 'similar'
    threshold_value: Any = None
    threshold_unit: str = ""
    required_set: List[str] = field(default_factory=list)
    match_mode: str = "all"  # 'all'（全部满足）, 'any'（任一满足）


class RequirementParser:
    """
    匹配要求解析器
    将人工填写的自然语言要求（如"本科及以上"、"3年以上"、"Python,SQL"）
    解析为结构化的可比较规则
    """

    @staticmethod
    def parse(requirement: str, field_name: str = "", field_type: str = "") -> ParsedRequirement:
        """解析匹配要求"""
        req = requirement.strip()
        result = ParsedRequirement(raw_text=req, requirement_type='custom')

        # 0. 学历类字段优先处理（"本科及以上"、"硕士"等，避免被数值阈值误判）
        if field_name and any(kw in field_name for kw in ['学历', '教育', '学位']):
            result.requirement_type = 'threshold'
            result.operator = '>='
            result.threshold_unit = '学历'
            for edu in ['博士后', '博士研究生', '博士', '硕士研究生', '硕士', '研究生', 'MBA',
                         '大学本科', '本科', '学士', '大专', '专科', '高职', '高中', '中专']:
                if edu in req:
                    result.threshold_value = edu
                    return result
            return result

        # 1. 阈值型：包含"以上"、"以下"、"不低于"、"不超过"等
        if any(kw in req for kw in ['以上', '以下', '不低于', '不超过', '至少', '最多', '及以上', '及以下']):
            result.requirement_type = 'threshold'
            # 提取数值
            num_match = re.search(r'(\d+(?:\.\d+)?)', req)
            if num_match:
                result.threshold_value = float(num_match.group(1))
            # 判断操作符
            if any(kw in req for kw in ['以上', '不低于', '至少', '及以上']):
                result.operator = '>='
            elif any(kw in req for kw in ['以下', '不超过', '最多', '及以下']):
                result.operator = '<='
            # 提取单位
            unit_match = re.search(r'\d+(?:\.\d+)?\s*([\u4e00-\u9fa5a-zA-Z]+)', req)
            if unit_match:
                result.threshold_unit = unit_match.group(1)
            return result

        # 2. 集合型：包含逗号、顿号、斜杠分隔的多个值
        if any(delim in req for delim in [',', '，', '、', '/', '|']):
            result.requirement_type = 'set'
            result.operator = 'contains'
            # 分割
            parts = re.split(r'[,，、/|]', req)
            result.required_set = [p.strip() for p in parts if p.strip()]
            # 判断匹配模式
            if any(kw in req for kw in ['任一', '任意', '或者', '或', '其一']):
                result.match_mode = 'any'
            else:
                result.match_mode = 'all'  # 默认全部满足
            return result

        # 4. 等于型："是"、"必须"、"需要"等
        if any(kw in req for kw in ['必须', '需要', '要求', '是', '为']):
            result.requirement_type = 'text'
            result.operator = 'similar'
            # 提取关键词
            clean = re.sub(r'(必须|需要|要求|是|为|有|具备)', '', req).strip()
            result.required_set = [clean] if clean else []
            return result

        # 5. 默认：文本相似度匹配
        result.requirement_type = 'text'
        result.operator = 'similar'
        result.required_set = [req] if req else []
        return result


# ============================================================
# 第三部分：语义匹配器（相似度计算 + 硬性淘汰 + 加权打分）
# ============================================================

class SemanticMatcher:
    """
    语义匹配器
    支持多种匹配策略：
    - 层级比较（学历等有序字段）
    - 数值阈值比较（年限等数值字段）
    - 集合包含比较（技能、证书等多值字段）
    - 文本相似度比较（自定义字段、项目经验等）
    """

    # 学历层级映射
    EDUCATION_ORDER = {
        '高中': 1, '中专': 1, '职高': 1,
        '大专': 2, '专科': 2, '高职': 2,
        '本科': 3, '学士': 3, '大学本科': 3,
        '硕士': 4, '研究生': 4, 'MBA': 4, '硕士研究生': 4,
        '博士': 5, '博士后': 5, '博士研究生': 5
    }

    @staticmethod
    def _text_similarity(text1: str, text2: str) -> float:
        """
        计算文本语义相似度
        优先使用向量嵌入（FastEmbed），不可用时降级为字符Jaccard相似度
        """
        if not text1 or not text2:
            return 0.0

        # 向量语义匹配
        if semantic_embedding is not None and semantic_embedding.is_available():
            return semantic_embedding.similarity(text1, text2)

        # 降级：字符级Jaccard相似度
        t1 = set(text1.lower())
        t2 = set(text2.lower())
        if text2.lower() in text1.lower() or text1.lower() in text2.lower():
            return 0.9
        intersection = len(t1 & t2)
        union = len(t1 | t2)
        if union == 0:
            return 0.0
        return intersection / union

    @staticmethod
    def _compare_education(resume_value: str, requirement: ParsedRequirement) -> Tuple[bool, float, str]:
        """
        学历比较
        返回: (是否通过硬性, 相似度得分0-1, 原因)
        """
        if not resume_value:
            return False, 0.0, "未提供学历信息"

        resume_level = SemanticMatcher.EDUCATION_ORDER.get(resume_value, 0)
        req_edu = requirement.threshold_value
        req_level = SemanticMatcher.EDUCATION_ORDER.get(req_edu, 0)

        if req_level == 0:
            return True, 0.7, "学历要求不明确，默认通过"

        # 硬性检查
        passed = resume_level >= req_level

        # 柔性得分：超出要求越多分越高，最高100
        if req_level > 0:
            ratio = min(resume_level / req_level, 1.5)
            score = min(int(ratio * 100), 100)
        else:
            score = 70

        reason = "" if passed else f"学历未达标（要求{req_edu}及以上，实际{resume_value}）"
        return passed, score, reason

    @staticmethod
    def _compare_numeric(resume_value, requirement: ParsedRequirement) -> Tuple[bool, float, str]:
        """
        数值阈值比较（工作年限等）
        """
        if resume_value is None:
            return False, 0.0, "未提供相关信息"

        try:
            resume_num = float(resume_value)
        except (ValueError, TypeError):
            return False, 0.0, "数值解析失败"

        threshold = requirement.threshold_value
        if threshold is None:
            return True, 0.7, "阈值不明确，默认通过"

        # 硬性检查
        if requirement.operator == '>=':
            passed = resume_num >= threshold
        elif requirement.operator == '<=':
            passed = resume_num <= threshold
        else:
            passed = True

        # 柔性得分
        if threshold > 0:
            ratio = min(resume_num / threshold, 1.5)
            score = min(int(ratio * 100), 100)
        else:
            score = 70

        unit = requirement.threshold_unit or ""
        op_text = '以上' if requirement.operator == '>=' else '以下'
        reason = "" if passed else f"未达标（要求{threshold}{unit}{op_text}，实际{resume_num}{unit}）"
        return passed, score, reason

    @staticmethod
    def _compare_set(resume_value: str, requirement: ParsedRequirement) -> Tuple[bool, float, str]:
        """
        集合包含比较（技能、证书等）
        支持向量语义匹配（不要求精确一致，如"税务申报"≈"纳税申报"）
        """
        if not resume_value:
            return False, 0.0, "未提供相关信息"

        resume_items = [item.strip() for item in re.split(r'[,，、/|；;]', resume_value) if item.strip()]
        required_items = requirement.required_set

        if not required_items:
            return True, 0.7, "要求不明确，默认通过"

        # 优先使用向量语义批量匹配（更高效）
        if semantic_embedding is not None and semantic_embedding.is_available():
            passed, score, details = semantic_embedding.match_set_semantic(
                resume_value, required_items, requirement.match_mode
            )
            detail_strs = []
            for d in details:
                status = "✓" if d['is_matched'] else "✗"
                match_info = f"≈{d['matched']}({d['similarity']}%)" if d['matched'] else ""
                detail_strs.append(f"{d['required']}{status}{match_info}")
            reason = "" if passed else f"未满足要求（{', '.join(detail_strs)}）"
            return passed, score, reason

        # 降级：逐个计算文本相似度
        matched_count = 0
        matched_details = []
        for req_item in required_items:
            best_sim = 0.0
            best_match = None
            for resume_item in resume_items:
                sim = SemanticMatcher._text_similarity(resume_item, req_item)
                if sim > best_sim:
                    best_sim = sim
                    best_match = resume_item
            if best_sim >= 0.5:
                matched_count += 1
                matched_details.append(f"{req_item}✓")
            else:
                matched_details.append(f"{req_item}✗")

        if requirement.match_mode == 'all':
            passed = matched_count == len(required_items)
        else:
            passed = matched_count >= 1

        score = int(matched_count / len(required_items) * 100)
        reason = "" if passed else f"未满足要求（{', '.join(matched_details)}）"
        return passed, score, reason

    @staticmethod
    def _compare_text(resume_value: str, requirement: ParsedRequirement) -> Tuple[bool, float, str]:
        """
        文本相似度比较（自定义字段、项目经验等）
        """
        if not resume_value:
            return False, 0.0, "未提供相关信息"

        if not requirement.required_set:
            return True, 0.7, "要求不明确，默认通过"

        # 计算与所有要求项的最大相似度
        max_sim = 0.0
        for req_text in requirement.required_set:
            sim = SemanticMatcher._text_similarity(resume_value, req_text)
            max_sim = max(max_sim, sim)

        # 硬性检查：相似度超过0.4认为通过
        passed = max_sim >= 0.4
        score = int(max_sim * 100)
        reason = "" if passed else f"匹配度不足（相似度{int(max_sim*100)}%）"
        return passed, score, reason

    @staticmethod
    def match_field(
        resume_value: Any,
        requirement: ParsedRequirement,
        field_name: str = "",
        field_type: str = ""
    ) -> Tuple[bool, float, str]:
        """
        通用字段匹配入口
        根据字段名称和要求类型自动选择匹配策略
        """
        # 学历类字段
        if field_name and any(kw in field_name for kw in ['学历', '教育', '学位']):
            return SemanticMatcher._compare_education(str(resume_value) if resume_value else "", requirement)

        # 数值类字段（年限、年龄、数量等）
        if requirement.requirement_type == 'threshold' and requirement.threshold_unit in ['年', '岁', '个', '项', '篇']:
            return SemanticMatcher._compare_numeric(resume_value, requirement)

        # 纯数值阈值
        if requirement.requirement_type == 'threshold' and isinstance(requirement.threshold_value, (int, float)):
            return SemanticMatcher._compare_numeric(resume_value, requirement)

        # 集合类字段（技能、证书、行业等）
        if requirement.requirement_type == 'set':
            return SemanticMatcher._compare_set(str(resume_value) if resume_value else "", requirement)

        # 文本类字段
        if requirement.requirement_type == 'text':
            return SemanticMatcher._compare_text(str(resume_value) if resume_value else "", requirement)

        # 默认：文本相似度
        return SemanticMatcher._compare_text(str(resume_value) if resume_value else "", requirement)


# ============================================================
# 第四部分：统一AI解析与匹配引擎
# ============================================================

class AIResumeEngine:
    """
    统一的AI简历解析与智能匹配引擎
    Schema驱动，支持自定义字段和语义匹配
    """

    def __init__(self):
        self.extractor_registry = FieldExtractorRegistry()
        self.requirement_parser = RequirementParser()
        self.matcher = SemanticMatcher()

    def parse_resume(self, text: str, schema_fields: List = None) -> Dict:
        """
        基于Schema的AI语义解析
        如果提供了schema_fields，则只解析Schema中定义的字段
        否则解析所有内置字段
        """
        result = {
            'candidate_name': None,
            'parsed_fields': {},  # 所有提取的字段
            'raw_text': text[:5000]
        }

        # 提取姓名（始终提取）
        name_field = self.extractor_registry._extract_name(text)
        result['candidate_name'] = name_field.value

        if schema_fields:
            # 基于Schema动态提取
            for schema_field in schema_fields:
                field_name = schema_field.field_name
                extractor = self.extractor_registry.match_extractor(field_name)
                # 通用提取器需要传字段名
                if extractor == self.extractor_registry._generic_extract:
                    extracted = extractor(text, field_name)
                else:
                    extracted = extractor(text)
                result['parsed_fields'][field_name] = {
                    'value': extracted.value,
                    'confidence': extracted.confidence,
                    'source': extracted.source_text
                }
        else:
            # 无Schema时，提取所有内置字段
            all_fields = ['学历', '工作年限', '核心技能', '行业经验', '证书', '项目经验', '毕业院校', '专业']
            for field_name in all_fields:
                extractor = self.extractor_registry.match_extractor(field_name)
                extracted = extractor(text)
                result['parsed_fields'][field_name] = {
                    'value': extracted.value,
                    'confidence': extracted.confidence,
                    'source': extracted.source_text
                }

        # 兼容旧接口的扁平字段
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
        resume_data: Dict,
        schema_fields: List
    ) -> Dict:
        """
        将简历匹配到一个岗位
        基于Schema的语义匹配：硬性淘汰 + 多维度加权打分
        """
        result = {
            'passed_hard': True,
            'reject_reason': '',
            'total_score': 0,
            'dimension_scores': {},  # 各维度得分
            'match_details': []  # 每个字段的匹配详情
        }

        total_weight = 0
        weighted_score = 0

        parsed_fields = resume_data.get('parsed_fields', {})

        for schema_field in schema_fields:
            field_name = schema_field.field_name
            requirement_text = schema_field.requirement
            weight = schema_field.weight
            is_hard = schema_field.is_hard
            field_type = schema_field.field_type

            # 获取简历中该字段的值
            # 兼容旧格式（支持常见字段名别名）
            legacy_map = {
                '学历': 'parsed_education',
                '学历要求': 'parsed_education',
                '教育背景': 'parsed_education',
                '工作年限': 'parsed_experience',
                '工作经验': 'parsed_experience',
                '经验年限': 'parsed_experience',
                '核心技能': 'parsed_skills',
                '技能': 'parsed_skills',
                '专业技能': 'parsed_skills',
                '技能特长': 'parsed_skills',
                '行业经验': 'parsed_industry',
                '行业背景': 'parsed_industry',
                '所属行业': 'parsed_industry',
                '行业': 'parsed_industry',
                '证书': 'parsed_certificates',
                '证书资质': 'parsed_certificates',
                '资格证书': 'parsed_certificates',
                '项目经验': 'parsed_projects',
                '项目经历': 'parsed_projects',
            }
            if field_name in parsed_fields:
                resume_value = parsed_fields[field_name].get('value')
                # 如果parsed_fields中的值为空，回退到legacy_map从resume_data取
                if not resume_value:
                    resume_value = resume_data.get(legacy_map.get(field_name))
            else:
                resume_value = resume_data.get(legacy_map.get(field_name))

            # 解析匹配要求
            requirement = self.requirement_parser.parse(requirement_text, field_name, field_type)

            # 执行语义匹配
            passed, score, reason = self.matcher.match_field(
                resume_value, requirement, field_name, field_type
            )

            # 记录匹配详情
            detail = {
                'field_name': field_name,
                'requirement': requirement_text,
                'resume_value': str(resume_value) if resume_value else '未提供',
                'passed': passed,
                'score': score,
                'weight': weight,
                'is_hard': is_hard,
                'reason': reason
            }
            result['match_details'].append(detail)
            result['dimension_scores'][field_name] = score

            # 硬性条件检查
            if is_hard and not passed:
                result['passed_hard'] = False
                result['reject_reason'] = f"[{field_name}] {reason}"
                result['total_score'] = 0
                return result

            # 加权计分
            total_weight += weight
            weighted_score += score * weight

        # 计算加权总分
        if total_weight > 0:
            result['total_score'] = round(weighted_score / total_weight)

        return result


# 全局单例
ai_engine = AIResumeEngine()
