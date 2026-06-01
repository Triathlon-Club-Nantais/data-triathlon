from datetime import datetime

from sqlalchemy import JSON, Column, Date, DateTime, Integer, String

from database import Base


class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, index=True)
    source_url = Column(String)
    provider = Column(String)
    athlete_name = Column(String, index=True)
    athlete_firstname = Column(String)
    club = Column(String)
    category = Column(String)
    gender = Column(String)
    bib_number = Column(String)
    event_name = Column(String, index=True)
    event_date = Column(Date, nullable=True)
    event_type = Column(String, index=True)
    rank_overall = Column(Integer, nullable=True)
    rank_category = Column(Integer, nullable=True)
    rank_gender = Column(Integer, nullable=True)
    total_time = Column(String, nullable=True)
    swim_time = Column(String, nullable=True)
    t1_time = Column(String, nullable=True)
    bike_time = Column(String, nullable=True)
    t2_time = Column(String, nullable=True)
    run_time = Column(String, nullable=True)
    raw_data = Column(JSON, nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow)
