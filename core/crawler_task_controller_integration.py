from .crawler_task_controller import TaskController
from .utils import log_time


class JobIntegration:
    """
    Lớp này giúp MainWindow dễ dàng tích hợp JobController.
    Nó cung cấp API cho UI:

    - create_new_job()
    - resume_job()
    - list_all_jobs()
    - save_progress()
    - update_status()
    """

    def __init__(self, log_func):
        self.controller = TaskController(log_func=log_func)

    # =================================================
    # Tạo job mới trước khi crawler bắt đầu chạy
    # =================================================
    def create_new_job(self, mode, start_url, config):
        job_id = self.controller.create_job(mode, start_url, config)
        return job_id

    # =================================================
    # Resume job cũ
    # =================================================
    def resume_job(self, job_id):
        job = self.controller.load_job(job_id)
        if not job:
            return None

        queue = self.controller.load_progress(job_id)
        config = job["config"]
        return queue, config

    # =================================================
    # Lưu trạng thái trong khi crawler chạy
    # =================================================
    def save_progress(self, job_id, queue):
        self.controller.save_progress(job_id, queue)

    # =================================================
    # Cập nhật trạng thái job
    # =================================================
    def update_status(self, job_id, status):
        self.controller.update_status(job_id, status)

    # =================================================
    # Lấy danh sách toàn bộ job
    # =================================================
    def list_all_jobs(self):
        return self.controller.list_jobs()
