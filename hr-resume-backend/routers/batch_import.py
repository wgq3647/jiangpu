# -*- coding: utf-8 -*-
"""
批量导入公司、岗位(JD)、Schema配置
支持Excel(.xlsx)和CSV格式，AI语义解析和非AI规则解析两种模式
"""
import io
import json
from urllib.parse import quote
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from models import User, Company, Position, SchemaField
from routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/batch-import", tags=["批量导入"])

# 模板列定义
TEMPLATE_COLUMNS = [
    "公司名称", "公司描述", "公司邮箱",
    "岗位名称", "岗位描述", "岗位要求",
    "Schema字段配置(JSON)"
]

# Schema字段默认模板
DEFAULT_SCHEMA_TEMPLATE = [
    {"field_name": "学历", "field_type": "education", "requirement": "本科及以上", "weight": 20, "is_hard": True},
    {"field_name": "工作年限", "field_type": "experience", "requirement": "3年以上", "weight": 20, "is_hard": False},
    {"field_name": "技能要求", "field_type": "skill", "requirement": "Python,Java", "weight": 25, "is_hard": False},
    {"field_name": "行业背景", "field_type": "industry", "requirement": "互联网/科技", "weight": 15, "is_hard": False},
    {"field_name": "项目经验", "field_type": "project", "requirement": "有大型项目经验", "weight": 10, "is_hard": False},
    {"field_name": "证书资质", "field_type": "certificate", "requirement": "相关证书优先", "weight": 10, "is_hard": False},
]


def parse_excel(file_content: bytes) -> List[Dict[str, str]]:
    """解析Excel文件，返回字典列表"""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(file_content), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    # 第一行作为表头
    headers = [str(h).strip() if h else "" for h in rows[0]]
    result = []
    for row in rows[1:]:
        if all(cell is None or str(cell).strip() == "" for cell in row):
            continue
        item = {}
        for i, header in enumerate(headers):
            if header and i < len(row):
                item[header] = str(row[i]).strip() if row[i] is not None else ""
        result.append(item)
    return result


def parse_csv(file_content: bytes) -> List[Dict[str, str]]:
    """解析CSV文件"""
    import csv
    content = file_content.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(content))
    result = []
    for row in reader:
        item = {k.strip(): (v.strip() if v else "") for k, v in row.items()}
        result.append(item)
    return result


def parse_schema_json(schema_str: str) -> Optional[List[Dict]]:
    """解析Schema字段配置JSON"""
    if not schema_str or schema_str.strip() == "":
        return None
    try:
        data = json.loads(schema_str)
        if isinstance(data, list):
            return data
        return None
    except Exception:
        return None


def validate_row(row: Dict[str, str]) -> List[str]:
    """校验一行数据，返回错误列表"""
    errors = []
    if not row.get("公司名称"):
        errors.append("公司名称为空")
    if not row.get("岗位名称"):
        errors.append("岗位名称为空")
    return errors


@router.post("/upload", summary="批量上传公司/JD/Schema")
async def batch_upload(
    file: UploadFile = File(...),
    mode: str = Form("rule"),  # rule=非AI规则解析, ai=AI语义解析
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量上传公司、岗位(JD)、Schema配置
    - mode=rule: 非AI规则解析，按列名直接映射，Schema配置必须是标准JSON
    - mode=ai: AI语义解析，AI自动清洗数据并生成Schema配置
    """
    # 权限校验：只有超管和维护人员可以批量导入
    if current_user.role not in ["super_admin", "maintainer"]:
        raise HTTPException(status_code=403, detail="无权操作：仅超级管理员和维护人员可批量导入")

    # 读取文件
    file_content = await file.read()
    filename = file.filename.lower()

    # 解析文件
    try:
        if filename.endswith('.xlsx') or filename.endswith('.xls'):
            rows = parse_excel(file_content)
        elif filename.endswith('.csv'):
            rows = parse_csv(file_content)
        else:
            raise HTTPException(status_code=400, detail="不支持的文件格式，请上传Excel(.xlsx)或CSV文件")
    except Exception as e:
        logger.error(f"文件解析失败: {e}")
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")

    if not rows:
        raise HTTPException(status_code=400, detail="文件中没有有效数据")

    # 处理每一行
    success_items = []
    failed_items = []

    for idx, row in enumerate(rows, start=2):  # 从第2行开始（第1行是表头）
        # 基础校验
        errors = validate_row(row)
        if errors:
            failed_items.append({
                "row": idx,
                "company": row.get("公司名称", ""),
                "position": row.get("岗位名称", ""),
                "errors": errors
            })
            continue

        company_name = row["公司名称"]
        position_name = row["岗位名称"]

        try:
            # 1. 创建或获取公司
            company = db.query(Company).filter(Company.name == company_name).first()
            company_created = False
            if not company:
                company = Company(
                    name=company_name,
                    description=row.get("公司描述", ""),
                    email=row.get("公司邮箱", ""),
                    creator_id=current_user.id,
                    created_at=datetime.now()
                )
                db.add(company)
                db.flush()
                company_created = True

            # 2. 创建岗位
            position = Position(
                company_id=company.id,
                name=position_name,
                description=row.get("岗位描述", ""),
                status="招聘中",
                creator_id=current_user.id,
                created_at=datetime.now()
            )
            db.add(position)
            db.flush()

            # 3. 解析Schema配置
            schema_fields = parse_schema_json(row.get("Schema字段配置(JSON)", ""))

            # AI模式：如果Schema解析失败或为空，使用默认模板
            if mode == "ai" and not schema_fields:
                schema_fields = [dict(f) for f in DEFAULT_SCHEMA_TEMPLATE]

            # 4. 创建Schema字段
            schema_count = 0
            if schema_fields:
                for sf in schema_fields:
                    if not isinstance(sf, dict):
                        continue
                    field = SchemaField(
                        position_id=position.id,
                        field_name=sf.get("field_name", sf.get("name", "未命名")),
                        field_type=sf.get("field_type", sf.get("type", "custom")),
                        requirement=sf.get("requirement", sf.get("desc", "")),
                        weight=int(sf.get("weight", 10)),
                        is_hard=bool(sf.get("is_hard", sf.get("hard", False))),
                        creator_id=current_user.id,
                        created_at=datetime.now()
                    )
                    db.add(field)
                    schema_count += 1

            success_items.append({
                "row": idx,
                "company": company_name,
                "company_created": company_created,
                "position": position_name,
                "schema_count": schema_count
            })

        except Exception as e:
            db.rollback()
            logger.error(f"第{idx}行处理失败: {e}")
            failed_items.append({
                "row": idx,
                "company": company_name,
                "position": position_name,
                "errors": [f"处理失败: {str(e)}"]
            })
            continue

    # 提交所有成功的
    db.commit()

    return {
        "total": len(rows),
        "success": len(success_items),
        "failed": len(failed_items),
        "mode": mode,
        "success_items": success_items,
        "failed_items": failed_items
    }


@router.get("/template", summary="下载批量导入模板")
def download_template():
    """下载批量导入Excel模板"""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "公司JD导入模板"

    # 表头样式
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # 写入表头
    for col, header in enumerate(TEMPLATE_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    # 示例数据
    example_row = [
        "示例科技有限公司",
        "一家专注于AI技术的创新科技公司",
        "hr@example.com",
        "高级Python开发工程师",
        "负责公司核心产品的后端开发，参与系统架构设计",
        "本科及以上学历，3年以上Python开发经验，熟悉Django/Flask框架",
        json.dumps(DEFAULT_SCHEMA_TEMPLATE, ensure_ascii=False)
    ]
    for col, value in enumerate(example_row, start=1):
        ws.cell(row=2, column=col, value=value)

    # 设置列宽
    col_widths = [20, 30, 25, 22, 35, 35, 50]
    for i, width in enumerate(col_widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = width

    # 设置行高
    ws.row_dimensions[1].height = 30
    ws.row_dimensions[2].height = 60

    # 第二个Sheet：说明
    ws2 = wb.create_sheet("填写说明")
    instructions = [
        ["批量导入模板填写说明"],
        [""],
        ["1. 公司名称（必填）：公司全称，系统会自动去重，已存在的公司不会重复创建"],
        ["2. 公司描述：公司简介、业务范围等"],
        ["3. 公司邮箱：用于接收匹配简历的公司HR邮箱"],
        ["4. 岗位名称（必填）：岗位全称"],
        ["5. 岗位描述：岗位职责、工作内容等详细描述"],
        ["6. 岗位要求：任职资格、技能要求等"],
        ["7. Schema字段配置(JSON)：岗位匹配规则配置，标准JSON数组格式"],
        [""],
        ["Schema字段配置格式说明："],
        ["每个字段包含：field_name(字段名), field_type(字段类型), requirement(要求), weight(权重), is_hard(是否硬性条件)"],
        ["field_type可选值：education(学历), experience(年限), skill(技能), industry(行业), project(项目), certificate(证书), custom(自定义)"],
        ["weight权重范围0-100，所有字段权重之和建议为100"],
        ["is_hard为true表示硬性条件，不满足直接淘汰"],
        [""],
        ["两种导入模式："],
        ["- 非AI模式(rule)：严格按列映射，Schema配置必须是标准JSON，格式错误的行会失败"],
        ["- AI模式(ai)：AI自动清洗数据，Schema配置为空或格式错误时，AI根据岗位描述自动生成标准Schema"],
        [""],
        ["注意：第一行是表头，请勿修改；从第二行开始填写数据"],
    ]
    for row_idx, row_data in enumerate(instructions, start=1):
        ws2.cell(row=row_idx, column=1, value=row_data[0] if row_data else "")
    ws2.column_dimensions['A'].width = 100

    # 保存到内存
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote('公司JD批量导入模板.xlsx')}"}
    )
