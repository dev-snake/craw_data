import json

from .crawler_task_runner import TaskRunner
from .queue_manager import CrawlQueue
from .utils import log_time


class TaskController:
    """
    Controller để UI điều khiển job hệ thống:
    - Tạo job mới
    - Resume job
    - Lưu progress khi crawling
    - Cập nhật trạng thái
    - List tất cả job
    """

    def __init__(self, log_func=None):
        self.runner = TaskRunner()
        self.log = log_func or (lambda x: None)

    # =====================================================
    # Create new job and return job_id
    # =====================================================
    def create_job(self, mode, start_url, config):
        job_id = self.runner.create_job(mode, start_url, config)
        self.log(log_time(f"[JOB] Created new job: {job_id}"))
        return job_id

    # =====================================================
    # Load job from DB
    # =====================================================
    def load_job(self, job_id):
        job = self.runner.load_job(job_id)
        if not job:
            self.log(log_time(f"[JOB] Not found: {job_id}"))
            return None

        self.log(log_time(f"[JOB] Loaded job {job_id}"))
        return job

    # =====================================================
    # Save queue + visited state
    # =====================================================
    def save_progress(self, job_id, queue: CrawlQueue):
        self.runner.save_progress(job_id, queue)
        self.log(log_time(f"[JOB] Saved progress for job {job_id}"))

    # =====================================================
    # Resume queue + visited
    # =====================================================
    def load_progress(self, job_id):
        queue = self.runner.load_progress(job_id)
        if queue:
            self.log(log_time(f"[JOB] Restored queue for job {job_id}"))
        return queue

    # =====================================================
    # Change status
    # =====================================================
    def update_status(self, job_id, status):
        self.runner.update_status(job_id, status)
        self.log(log_time(f"[JOB] Status update -> {job_id}: {status}"))

    # =====================================================
    # List all jobs
    # =====================================================
    def list_jobs(self):
        jobs = self.runner.list_jobs()
        self.log(log_time(f"[JOB] Found {len(jobs)} jobs"))
        return jobs
