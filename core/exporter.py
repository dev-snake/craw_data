import csv
import json
import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, MetaData, Table
from sqlalchemy.orm import sessionmaker

from .utils import ensure_dir


class Exporter:
    def __init__(self, config):
        self.config = config
        self.output_dir = config["export"]["output_directory"]
        ensure_dir(self.output_dir)

        # Create filenames
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_file = os.path.join(self.output_dir, f"output_{timestamp}.csv")
        self.json_file = os.path.join(self.output_dir, f"output_{timestamp}.json")
        self.db_file = os.path.join(self.output_dir, f"output_{timestamp}.db")

        # Temporary storage
        self.data_list = []

    # =============================================
    # Add result for exporting
    # =============================================
    def add_result(self, item):
        """
        item is expected to be dict or string
        """
        self.data_list.append(item)

    # =============================================
    # Save CSV
    # =============================================
    def export_csv(self):
        if not self.config["export"]["export_csv"]:
            return

        try:
            with open(self.csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["data"])

                for item in self.data_list:
                    if isinstance(item, dict):
                        writer.writerow([json.dumps(item, ensure_ascii=False)])
                    else:
                        writer.writerow([str(item)])

        except Exception as e:
            print(f"[EXPORT][CSV] Error: {e}")

    # =============================================
    # Save JSON
    # =============================================
    def export_json(self):
        if not self.config["export"]["export_json"]:
            return

        try:
            with open(self.json_file, "w", encoding="utf-8") as f:
                json.dump(self.data_list, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[EXPORT][JSON] Error: {e}")

    # =============================================
    # Save SQLite
    # =============================================
    def export_sqlite(self):
        if not self.config["export"]["export_sqlite"]:
            return

        try:
            engine = create_engine(f"sqlite:///{self.db_file}")
            meta = MetaData()

            table = Table(
                "results",
                meta,
                Column("id", Integer, primary_key=True),
                Column("data", String),
            )

            meta.create_all(engine)
            Session = sessionmaker(bind=engine)
            session = Session()

            for item in self.data_list:
                text = json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else str(item)
                session.execute(table.insert().values(data=text))

            session.commit()
            session.close()

        except Exception as e:
            print(f"[EXPORT][SQLITE] Error: {e}")

    # =============================================
    # Export all formats
    # =============================================
    def export_all(self):
        try:
            self.export_csv()
            self.export_json()
            self.export_sqlite()
        except Exception as e:
            print(f"[EXPORT] Failed: {e}")
