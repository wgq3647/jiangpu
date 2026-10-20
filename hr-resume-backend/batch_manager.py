"""
批量任务管理器
管理简历批量上传的队列、进度、失败重试、去重
"""
import uuid
import hashlib
import threading
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FileTask:
    """单个文件的处理任务"""
    task_id: str
    file_name: str
    file_size: int
    status: str = "pending"  # pending / parsing / success / failed
    progress: int = 0  # 0-100
    error: str = ""
    resume_id: Optional[int] = None
    parse_method: str = ""
    retry_count: int = 0
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "status": self.status,
            "progress": self.progress,
            "error": self.error,
            "resume_id": self.resume_id,
            "parse_method": self.parse_method,
            "retry_count": self.retry_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class BatchJob:
    """批量上传任务"""
    batch_id: str
    total_files: int = 0
    success_count: int = 0
    failed_count: int = 0
    pending_count: int = 0
    status: str = "processing"  # processing / completed / partial_failed
    tasks: Dict[str, FileTask] = field(default_factory=dict)
    created_at: str = ""
    completed_at: str = ""

    def to_dict(self, include_tasks: bool = True) -> Dict[str, Any]:
        result = {
            "batch_id": self.batch_id,
            "total_files": self.total_files,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "pending_count": self.pending_count,
            "status": self.status,
            "overall_progress": self._calc_overall_progress(),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }
        if include_tasks:
            result["tasks"] = [t.to_dict() for t in self.tasks.values()]
        return result

    def _calc_overall_progress(self) -> int:
        if self.total_files == 0:
            return 0
        total_progress = sum(t.progress for t in self.tasks.values())
        return int(total_progress / self.total_files)

    def update_counts(self):
        self.success_count = sum(1 for t in self.tasks.values() if t.status == "success")
        self.failed_count = sum(1 for t in self.tasks.values() if t.status == "failed")
        self.pending_count = sum(1 for t in self.tasks.values() if t.status in ("pending", "parsing"))

        if self.pending_count == 0:
            self.completed_at = datetime.now().isoformat()
            if self.failed_count == 0:
                self.status = "completed"
            else:
                self.status = "partial_failed"


class BatchTaskManager:
    """
    批量任务管理器（单例）
    管理所有批量上传任务的状态
    """

    def __init__(self):
        self.jobs: Dict[str, BatchJob] = {}
        self.lock = threading.Lock()
        # 内容哈希 -> resume_id，用于去重
        self.content_hash_map: Dict[str, int] = {}

    def create_batch(self, file_infos: List[Dict[str, Any]]) -> str:
        """
        创建批量任务
        Args:
            file_infos: [{"file_name": str, "file_size": int}, ...]
        Returns:
            batch_id
        """
        batch_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()

        job = BatchJob(
            batch_id=batch_id,
            total_files=len(file_infos),
            created_at=now,
        )

        for info in file_infos:
            task_id = str(uuid.uuid4())[:8]
            task = FileTask(
                task_id=task_id,
                file_name=info["file_name"],
                file_size=info["file_size"],
                created_at=now,
                updated_at=now,
            )
            job.tasks[task_id] = task

        job.update_counts()

        with self.lock:
            self.jobs[batch_id] = job

        logger.info(f"创建批量任务 {batch_id}，共{len(file_infos)}个文件")
        return batch_id

    def get_job(self, batch_id: str) -> Optional[BatchJob]:
        """获取批量任务状态"""
        with self.lock:
            return self.jobs.get(batch_id)

    def update_task(self, batch_id: str, task_id: str, **kwargs):
        """更新任务状态"""
        with self.lock:
            job = self.jobs.get(batch_id)
            if not job:
                return
            task = job.tasks.get(task_id)
            if not task:
                return

            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            task.updated_at = datetime.now().isoformat()
            job.update_counts()

    def get_task(self, batch_id: str, task_id: str) -> Optional[FileTask]:
        """获取单个任务"""
        with self.lock:
            job = self.jobs.get(batch_id)
            if job:
                return job.tasks.get(task_id)
        return None

    def calc_content_hash(self, content: str) -> str:
        """计算内容哈希，用于去重"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def check_duplicate(self, content_hash: str) -> Optional[int]:
        """检查是否重复，返回已存在的resume_id"""
        return self.content_hash_map.get(content_hash)

    def register_content(self, content_hash: str, resume_id: int):
        """注册内容哈希"""
        self.content_hash_map[content_hash] = resume_id

    def remove_content_by_resume_id(self, resume_id: int):
        """根据resume_id移除内容哈希（删除简历时调用，防止重复上传被误判）"""
        with self.lock:
            to_remove = [h for h, rid in self.content_hash_map.items() if rid == resume_id]
            for h in to_remove:
                del self.content_hash_map[h]
            if to_remove:
                logger.info(f"已清理resume_id={resume_id}的内容哈希（{len(to_remove)}条）")

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """清理超过指定时间的旧任务"""
        # 简单实现，实际可用定时任务
        pass


# 全局单例
batch_manager = BatchTaskManager()
