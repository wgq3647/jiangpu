from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, nullable=False, index=True, comment="手机号（登录ID）")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    name = Column(String(50), nullable=True, comment="姓名")
    role = Column(String(20), nullable=False, default="recruiter", comment="角色：super_admin/maintainer/recruiter")
    status = Column(String(20), nullable=False, default="active", comment="状态：active/pending/disabled")
    created_at = Column(DateTime, default=datetime.now)


class PositionStatus(str, enum.Enum):
    RECRUITING = "招聘中"
    PAUSED = "暂停"
    FILLED = "已满岗"

class FieldType(str, enum.Enum):
    ENUM = "枚举"
    NUMBER = "数字"
    MULTI_SELECT = "多选"
    SINGLE_SELECT = "单选"
    TEXT = "文本"

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="公司名称")
    description = Column(Text, nullable=True, comment="公司描述")
    status = Column(String(20), default="合作中", comment="合作状态")
    email = Column(String(100), nullable=True, comment="公司接收简历邮箱")
    city = Column(String(50), nullable=True, comment="所在城市")
    address = Column(String(200), nullable=True, comment="详细地址")
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建者ID")
    is_deleted = Column(Boolean, default=False, comment="是否已删除（软删除）")
    deleted_at = Column(DateTime, nullable=True, comment="删除时间")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    positions = relationship("Position", back_populates="company", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[creator_id])

class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    name = Column(String(100), nullable=False, comment="岗位名称")
    description = Column(Text, nullable=True, comment="岗位描述")
    status = Column(String(20), default=PositionStatus.RECRUITING, comment="岗位状态")
    headcount = Column(Integer, default=1, comment="招聘人数")
    work_locations = Column(String(500), nullable=True, comment="工作地区（多选，逗号分隔）")
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建者ID")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    company = relationship("Company", back_populates="positions")
    creator = relationship("User", foreign_keys=[creator_id])
    schema_fields = relationship("SchemaField", back_populates="position", cascade="all, delete-orphan")

class SchemaField(Base):
    __tablename__ = "schema_fields"

    id = Column(Integer, primary_key=True, index=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=False)
    field_name = Column(String(50), nullable=False, comment="字段名称")
    field_type = Column(String(20), nullable=False, comment="字段类型")
    requirement = Column(String(200), nullable=False, comment="匹配要求")
    is_hard = Column(Boolean, default=False, comment="是否硬性淘汰")
    weight = Column(Integer, default=10, comment="匹配权重")
    sort_order = Column(Integer, default=0, comment="排序")
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建者ID")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    position = relationship("Position", back_populates="schema_fields")
    creator = relationship("User", foreign_keys=[creator_id])


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String(200), nullable=False, comment="文件名")
    file_size = Column(Integer, nullable=True, comment="文件大小（字节）")
    file_type = Column(String(20), nullable=True, comment="文件格式：pdf/word/text/image")
    candidate_name = Column(String(50), nullable=True, comment="候选人姓名")
    raw_text = Column(Text, nullable=True, comment="原始简历文本")
    # 结构化解析结果（JSON格式存储）
    parsed_education = Column(String(100), nullable=True, comment="学历")
    parsed_experience = Column(Integer, nullable=True, comment="工作年限")
    parsed_skills = Column(String(500), nullable=True, comment="技能列表（逗号分隔）")
    parsed_industry = Column(String(200), nullable=True, comment="行业背景")
    parsed_projects = Column(String(500), nullable=True, comment="项目经历")
    parsed_certificates = Column(String(300), nullable=True, comment="证书")
    parsed_fields_json = Column(Text, nullable=True, comment="所有Schema字段的解析结果（JSON）")
    parse_method = Column(String(20), default="rule", comment="解析方式：ai/rule")
    # 状态
    status = Column(String(20), default="待解析", comment="解析状态")
    business_status = Column(String(20), default="有效", comment="业务状态：有效/投递中/已面试通过/无效")
    routing_paused = Column(Boolean, default=False, comment="是否暂停路由（投递中状态生效）")
    parse_error = Column(String(500), nullable=True, comment="解析错误")
    invalid_reason = Column(String(500), nullable=True, comment="无效原因（当business_status为无效时）")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="归属招聘人员ID")
    content_hash = Column(String(64), nullable=True, index=True, comment="简历内容哈希（去重用）")
    duplicate_of_id = Column(Integer, ForeignKey("resumes.id"), nullable=True, comment="重复简历指向的原始简历ID")
    created_at = Column(DateTime, default=datetime.now)

    match_results = relationship("MatchResult", back_populates="resume", cascade="all, delete-orphan")
    owner = relationship("User", foreign_keys=[owner_id])
    duplicate_of = relationship("Resume", remote_side=[id], foreign_keys=[duplicate_of_id])


class MatchResult(Base):
    __tablename__ = "match_results"

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=False)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=False)
    total_score = Column(Integer, default=0, comment="总匹配分")
    passed_hard = Column(Boolean, default=False, comment="是否通过硬性条件")
    reject_reason = Column(String(500), nullable=True, comment="淘汰原因")
    # 各维度得分
    education_score = Column(Integer, default=0, comment="学历得分")
    experience_score = Column(Integer, default=0, comment="年限得分")
    skill_score = Column(Integer, default=0, comment="技能得分")
    industry_score = Column(Integer, default=0, comment="行业得分")
    project_score = Column(Integer, default=0, comment="项目得分")
    certificate_score = Column(Integer, default=0, comment="证书得分")
    match_details_json = Column(Text, nullable=True, comment="各字段匹配详情（JSON）")
    match_method = Column(String(20), default="rule", comment="匹配方式：ai/rule")
    match_highlights = Column(String(500), nullable=True, comment="匹配亮点（AI生成）")
    match_gaps = Column(String(500), nullable=True, comment="不足/差距（AI生成）")
    # 发送到公司
    sent_to_company = Column(Boolean, default=False, comment="是否已发送到公司邮箱")
    sent_at = Column(DateTime, nullable=True, comment="发送到公司的时间")
    sent_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="发送人ID")
    # 面试安排
    interview_scheduled = Column(Boolean, default=False, comment="是否已安排面试")
    interview_scheduled_at = Column(DateTime, nullable=True, comment="面试安排时间")
    # 人工反馈
    feedback_status = Column(String(20), nullable=True, comment="人工反馈状态")
    feedback_note = Column(Text, nullable=True, comment="人工评价")
    created_at = Column(DateTime, default=datetime.now)

    resume = relationship("Resume", back_populates="match_results")
    position = relationship("Position")
    manual_review = relationship("ManualReview", back_populates="match_result", uselist=False, cascade="all, delete-orphan")
    interview_feedback = relationship("InterviewFeedback", back_populates="match_result", uselist=False, cascade="all, delete-orphan")


class InterviewResult(str, enum.Enum):
    PASS = "通过"
    FAIL = "不通过"
    PENDING = "待定"


class ManualReview(Base):
    """人工初审评价表"""
    __tablename__ = "manual_reviews"

    id = Column(Integer, primary_key=True, index=True)
    match_result_id = Column(Integer, ForeignKey("match_results.id"), nullable=False, unique=True, comment="关联匹配结果")
    hr_rating = Column(Integer, nullable=False, comment="HR星级打分（1-5星）")
    hr_comment = Column(Text, nullable=True, comment="HR文字评价")
    ai_score_correction = Column(Integer, nullable=True, comment="AI分数修正（0-100，为空表示不修正）")
    ai_deviation_type = Column(String(50), nullable=True, comment="AI偏差类型：高估/低估/识别错误/维度遗漏/其他")
    reviewer_name = Column(String(50), nullable=True, comment="评价人姓名")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    match_result = relationship("MatchResult", back_populates="manual_review")


class InterviewFeedback(Base):
    """面试结果反馈表"""
    __tablename__ = "interview_feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    match_result_id = Column(Integer, ForeignKey("match_results.id"), nullable=False, unique=True, comment="关联匹配结果")
    interview_result = Column(String(20), nullable=False, comment="面试结果：通过/不通过/待定")
    fail_reasons = Column(String(500), nullable=True, comment="标准化失败原因（逗号分隔，多选）")
    custom_note = Column(Text, nullable=True, comment="自定义备注")
    interviewer = Column(String(50), nullable=True, comment="面试官")
    interview_date = Column(DateTime, nullable=True, comment="面试日期")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    match_result = relationship("MatchResult", back_populates="interview_feedback")


class OptimizationLog(Base):
    """AI自学习优化日志表"""
    __tablename__ = "optimization_logs"

    id = Column(Integer, primary_key=True, index=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=True, comment="关联岗位（为空表示全局优化）")
    optimization_type = Column(String(50), nullable=False, comment="优化类型：权重调整/规则优化/语义识别优化/阈值调整")
    description = Column(Text, nullable=False, comment="优化描述")
    before_data = Column(Text, nullable=True, comment="优化前数据（JSON）")
    after_data = Column(Text, nullable=True, comment="优化后数据（JSON）")
    accuracy_before = Column(Integer, nullable=True, comment="优化前准确率（%）")
    accuracy_after = Column(Integer, nullable=True, comment="优化后准确率（%）")
    triggered_by = Column(String(50), default="人工评价", comment="触发原因：人工评价/面试反馈/定期优化/手动触发")
    sample_count = Column(Integer, default=0, comment="参与优化的样本数")
    created_at = Column(DateTime, default=datetime.now)

    position = relationship("Position")


class AccuracyHistory(Base):
    """匹配准确率历史表（用于趋势图）"""
    __tablename__ = "accuracy_history"

    id = Column(Integer, primary_key=True, index=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=True, comment="关联岗位（为空表示全局）")
    record_date = Column(DateTime, default=datetime.now, comment="记录日期")
    total_matches = Column(Integer, default=0, comment="总匹配数")
    reviewed_count = Column(Integer, default=0, comment="已人工评价数")
    interview_count = Column(Integer, default=0, comment="已面试数")
    interview_pass_count = Column(Integer, default=0, comment="面试通过数")
    ai_predicted_pass = Column(Integer, default=0, comment="AI预测通过数（AI分>=70）")
    true_positive = Column(Integer, default=0, comment="真阳性（AI通过且面试通过）")
    false_positive = Column(Integer, default=0, comment="假阳性（AI通过但面试不通过）")
    true_negative = Column(Integer, default=0, comment="真阴性（AI不通过且面试不通过）")
    false_negative = Column(Integer, default=0, comment="假阴性（AI不通过但面试通过）")
    accuracy = Column(Integer, default=0, comment="整体准确率（%）")
    precision = Column(Integer, default=0, comment="精确率（%）")
    recall = Column(Integer, default=0, comment="召回率（%）")
    created_at = Column(DateTime, default=datetime.now)

    position = relationship("Position")

class SystemConfig(Base):
    """系统热配置（键值对存储，支持AI配置等运行时修改）"""
    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String(100), unique=True, nullable=False, index=True, comment="配置键")
    config_value = Column(Text, nullable=True, comment="配置值")
    description = Column(String(200), nullable=True, comment="配置说明")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Factor(Base):
    """岗位要求因子库（维护组预定义的字段和类型）"""
    __tablename__ = "factors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, comment="因子名称（字段名）")
    field_type = Column(String(20), nullable=False, comment="字段类型：education/experience/skill/certification/project/industry/age/gender/custom")
    description = Column(String(200), nullable=True, comment="因子说明")
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建者ID")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    creator = relationship("User", foreign_keys=[creator_id])
    template_factors = relationship("TemplateFactor", back_populates="factor", cascade="all, delete-orphan")


class PositionTemplate(Base):
    """岗位模板（由因子组合而成，可快速应用到岗位Schema配置）"""
    __tablename__ = "position_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="模板名称")
    description = Column(String(200), nullable=True, comment="模板说明")
    is_default = Column(Boolean, default=False, comment="是否为系统默认模板（不可删除）")
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建者ID")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    creator = relationship("User", foreign_keys=[creator_id])
    template_factors = relationship("TemplateFactor", back_populates="template", cascade="all, delete-orphan")


class TemplateFactor(Base):
    """模板与因子的关联关系"""
    __tablename__ = "template_factors"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("position_templates.id"), nullable=False)
    factor_id = Column(Integer, ForeignKey("factors.id"), nullable=False)
    sort_order = Column(Integer, default=0, comment="排序")

    template = relationship("PositionTemplate", back_populates="template_factors")
    factor = relationship("Factor", back_populates="template_factors")
