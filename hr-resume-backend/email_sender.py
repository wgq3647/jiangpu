# -*- coding: utf-8 -*-
"""
SMTP邮件发送工具
从数据库热加载SMTP配置，支持真实邮件发送
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
import logging

logger = logging.getLogger(__name__)


def get_smtp_config(db_session):
    """从数据库加载SMTP配置"""
    from models import SystemConfig
    configs = db_session.query(SystemConfig).all()
    config_map = {c.config_key: c.config_value for c in configs}
    return {
        "enabled": str(config_map.get("smtp_enabled", "false")).lower() == "true",
        "host": config_map.get("smtp_host", ""),
        "port": int(config_map.get("smtp_port", "465")),
        "user": config_map.get("smtp_user", ""),
        "password": config_map.get("smtp_password", ""),
        "from_name": config_map.get("smtp_from_name", "HR智能招聘系统"),
        "use_ssl": str(config_map.get("smtp_use_ssl", "true")).lower() == "true",
    }


def send_email(db_session, to_email, subject, html_content):
    """
    发送HTML邮件
    Returns: (success: bool, message: str)
    """
    config = get_smtp_config(db_session)

    if not config["enabled"]:
        return False, "SMTP邮件发送未启用，请先在系统配置中开启"

    if not config["host"] or not config["user"] or not config["password"]:
        return False, "SMTP配置不完整，请检查服务器地址、账号和授权码"

    if not to_email:
        return False, "收件人邮箱为空"

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = formataddr((str(Header(config["from_name"], "utf-8")), config["user"]))
        msg["To"] = to_email
        msg["Subject"] = Header(subject, "utf-8")

        html_part = MIMEText(html_content, "html", "utf-8")
        msg.attach(html_part)

        if config["use_ssl"]:
            server = smtplib.SMTP_SSL(config["host"], config["port"], timeout=30)
        else:
            server = smtplib.SMTP(config["host"], config["port"], timeout=30)
            server.starttls()

        server.login(config["user"], config["password"])
        server.sendmail(config["user"], [to_email], msg.as_string())
        server.quit()

        logger.info(f"邮件发送成功: {to_email} - {subject}")
        return True, "发送成功"

    except smtplib.SMTPAuthenticationError:
        return False, "SMTP认证失败，请检查邮箱账号和授权码"
    except smtplib.SMTPConnectError:
        return False, f"无法连接SMTP服务器 {config['host']}:{config['port']}"
    except Exception as e:
        logger.error(f"邮件发送失败: {e}")
        return False, f"发送失败: {str(e)}"


def build_match_email_html(candidate_name, position_name, company_name, total_score,
                           passed_hard, match_details, highlights=None, gaps=None):
    """构建匹配结果邮件HTML内容"""
    status_color = "#10B981" if passed_hard else "#EF4444"
    status_text = "通过硬性条件" if passed_hard else "未通过硬性条件"

    details_html = ""
    if match_details:
        # 兼容列表和字典两种格式
        if isinstance(match_details, dict):
            items = list(match_details.items())
        elif isinstance(match_details, list):
            items = []
            for d in match_details:
                if isinstance(d, dict):
                    field_name = d.get("field_name", d.get("field", d.get("name", "未知")))
                    items.append((field_name, d))
        else:
            items = []
        for field, detail in items:
            if isinstance(detail, dict):
                value = detail.get("resume_value", detail.get("value", detail.get("extracted", "-")))
                score = detail.get("score", detail.get("match_score", 0))
                matched = detail.get("passed", detail.get("matched", detail.get("is_match", False)))
                icon = "✅" if matched else "❌"
                details_html += f"""
                <tr>
                    <td style="padding:8px 12px;border:1px solid #E2E8F0;">{field}</td>
                    <td style="padding:8px 12px;border:1px solid #E2E8F0;">{value}</td>
                    <td style="padding:8px 12px;border:1px solid #E2E8F0;text-align:center;">{score}</td>
                    <td style="padding:8px 12px;border:1px solid #E2E8F0;text-align:center;">{icon}</td>
                </tr>"""

    highlights_html = f'<p style="color:#059669;margin:8px 0;"><strong>匹配亮点：</strong>{highlights}</p>' if highlights else ""
    gaps_html = f'<p style="color:#D97706;margin:8px 0;"><strong>待提升：</strong>{gaps}</p>' if gaps else ""

    # 匹配详情表格（在f-string外部构建，避免嵌套替换问题）
    if details_html:
        details_table_html = (
            "<h3 style='font-size:15px;color:#1E293B;margin:20px 0 10px;'>各维度匹配详情</h3>"
            "<table style='width:100%;border-collapse:collapse;font-size:13px;'>"
            "<thead><tr style='background:#F8FAFC;'>"
            "<th style='padding:8px 12px;border:1px solid #E2E8F0;text-align:left;'>维度</th>"
            "<th style='padding:8px 12px;border:1px solid #E2E8F0;text-align:left;'>提取值</th>"
            "<th style='padding:8px 12px;border:1px solid #E2E8F0;'>得分</th>"
            "<th style='padding:8px 12px;border:1px solid #E2E8F0;'>状态</th>"
            "</tr></thead><tbody>" + details_html + "</tbody></table>"
        )
    else:
        details_table_html = ""

    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #4F46E5, #7C3AED); color: white; padding: 24px; border-radius: 12px 12px 0 0;">
            <h2 style="margin:0;font-size:20px;">候选人匹配推荐</h2>
            <p style="margin:8px 0 0;opacity:0.9;">岗位：{position_name} · 公司：{company_name}</p>
        </div>
        <div style="background:#fff;border:1px solid #E2E8F0;border-top:none;padding:24px;border-radius:0 0 12px 12px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
                <div>
                    <div style="font-size:24px;font-weight:700;color:#1E293B;">{candidate_name}</div>
                    <div style="font-size:14px;color:#64748B;margin-top:4px;">候选人</div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:32px;font-weight:700;color:#4F46E5;">{total_score}<span style="font-size:16px;color:#94A3B8;">分</span></div>
                    <div style="display:inline-block;padding:4px 12px;background:{status_color}15;color:{status_color};border-radius:12px;font-size:12px;font-weight:600;margin-top:4px;">{status_text}</div>
                </div>
            </div>
            {highlights_html}
            {gaps_html}
            {details_table_html}
            <div style="margin-top:24px;padding-top:16px;border-top:1px solid #F1F5F9;font-size:12px;color:#94A3B8;text-align:center;">
                此邮件由 HR智能招聘系统 自动发送，请勿直接回复
            </div>
        </div>
    </div>
    """
