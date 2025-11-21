import os
import json
import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, Text, MetaData, Table
)
from sqlalchemy.orm import sessionmaker
import uuid

from .queue_manager import CrawlQueue


class TaskRunner:
    def __init__(self, job_db_path="jobs.db"):
        self.job_db_path = job_db_path
        self.engine = create_engine(f"sqlite:///{self.job_db_path}")
        self.meta = MetaData()

        self.table = Table(
            "jobs",
            self.meta,
            Column("id", String, primary_key=True),
            Column("mode", String),
            Column("start_url", String),
            Column("config", Text),
            Column("queue_data", Text),
            Column("visited_data", Text),
            Column("status", String),
            Column("created_at", DateTime),
            Column("updated_at", DateTime),
        )

        self.meta.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    # =====================================================
    # Create new job (task)
    # =====================================================
    def create_job(self, mode, start_url, config):
        job_id = str(uuid.uuid4())

        job_data = {
            "id": job_id,
            "mode": mode,
            "start_url": start_url,
            "config": json.dumps(config),
            "queue_data": json.dumps([]),
            "visited_data": json.dumps([]),
            "status": "pending",
            "created_at": datetime.datetime.now(),
            "updated_at": datetime.datetime.now(),
        }

        session = self.Session()
        session.execute(self.table.insert().values(**job_data))
        session.commit()

        return job_id

    # =====================================================
    # Load job by ID
    # =====================================================
    def load_job(self, job_id):
        session = self.Session()
        result = session.execute(
            self.table.select().where(self.table.c.id == job_id)
        ).fetchone()

        if not result:
            return None

        return dict(result)

    # =====================================================
    # Save queue + visited for resume
    # =====================================================
    def save_progress(self, job_id, queue: CrawlQueue):
        session = self.Session()

        queue_list = list(queue.queue)
        visited_list = list(queue.visited)

        session.execute(
            self.table.update()
            .where(self.table.c.id == job_id)
            .values(
                queue_data=json.dumps(queue_list),
                visited_data=json.dumps(visited_list),
                updated_at=datetime.datetime.now(),
            )
        )

        session.commit()

    # =====================================================
    # Load saved queue + visited for resume
    # =====================================================
    def load_progress(self, job_id):
        job = self.load_job(job_id)
        if not job:
            return None

        q = CrawlQueue()
        q.queue.extend(json.loads(job["queue_data"]))
        q.visited = set(json.loads(job["visited_data"]))

        return q

    # =====================================================
    # Update job status
    # =====================================================
    def update_status(self, job_id, status):
        session = self.Session()

        session.execute(
            self.table.update()
            .where(self.table.c.id == job_id)
            .values(
                status=status,
                updated_at=datetime.datetime.now(),
            )
        )

        session.commit()

    # =====================================================
    # List all jobs
    # =====================================================
    def list_jobs(self):
        session = self.Session()
        rows = session.execute(self.table.select()).fetchall()
        return [dict(r) for r in rows]
