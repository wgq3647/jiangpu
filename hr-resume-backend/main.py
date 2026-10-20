from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base, SessionLocal
from models import User, Resume
from auth_utils import hash_password
from routers import system_config
from routers import companies, positions, schema_fields, resumes, stats, feedback, auth, users, batch_import, factors, position_templates, export

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI HR 智能简历筛选匹配平台",
    description="JD Schema 人工配置管理模块 API",
    version="1.0.0"
)

# 配置CORS，允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(companies.router)
app.include_router(positions.router)
app.include_router(schema_fields.router)
app.include_router(resumes.router)
app.include_router(stats.router)
app.include_router(feedback.router)
app.include_router(system_config.router)
app.include_router(batch_import.router)
app.include_router(factors.router)
app.include_router(position_templates.router)
app.include_router(export.router, prefix="/api")


@app.on_event("startup")
def startup_init():
    """启动时确保超级管理员存在，并将无主简历归属到超管"""
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "super_admin").first()
        if not admin:
            admin = User(
                phone="13800000000",
                password_hash=hash_password("Admin@123"),
                name="系统管理员",
                role="super_admin",
                status="active",
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            print("[Startup] 已创建超级管理员: 13800000000")
        # 将 owner_id 为 NULL 的简历归属到超管
        null_count = db.query(Resume).filter(Resume.owner_id.is_(None)).count()
        if null_count > 0:
            db.query(Resume).filter(Resume.owner_id.is_(None)).update(
                {Resume.owner_id: admin.id}, synchronize_session=False
            )
            db.commit()
            print(f"[Startup] 已将 {null_count} 条无主简历归属到超管 (id={admin.id})")

        # 初始化PDF和图片识别功能开关（默认关闭，且不可通过前端开启）
        from models import SystemConfig
        pdf_config = db.query(SystemConfig).filter(
            SystemConfig.config_key == "pdf_image_recognition_enabled"
        ).first()
        if not pdf_config:
            pdf_config = SystemConfig(
                config_key="pdf_image_recognition_enabled",
                config_value="false",
                description="PDF和图片简历识别功能开关（当前版本已禁用，不可开启）"
            )
            db.add(pdf_config)
            db.commit()
            print("[Startup] 已初始化PDF/图片识别功能开关: false（默认关闭）")
    finally:
        db.close()


@app.get("/", summary="健康检查")
def root():
    return {
        "message": "AI HR 后端服务运行中",
        "docs": "/docs",
        "redoc": "/redoc"
    }
