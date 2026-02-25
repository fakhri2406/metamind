"""SQLAlchemy + SQLite logger for all pipeline runs."""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, Float, String, Boolean, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

import config
from models.meta_data import PastRunSummary


class Base(DeclarativeBase):
    pass


class RunLog(Base):
    """Database model for a single pipeline run."""

    __tablename__ = "run_logs"

    run_id = Column(String, primary_key=True)
    account_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Phase 1: Ingest
    ingested_data_json = Column(Text, nullable=True)

    # Phase 2: Strategy
    raw_claude_response = Column(Text, nullable=True)
    campaign_config_json = Column(Text, nullable=True)
    campaign_name = Column(String, nullable=True)
    objective = Column(String, nullable=True)
    budget_daily_usd = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)
    strategy_error = Column(Text, nullable=True)

    # Approval
    approved = Column(Boolean, nullable=True)
    approval_timestamp = Column(DateTime, nullable=True)

    # Phase 3: Execute
    dry_run = Column(Boolean, nullable=True)
    created_campaign_id = Column(String, nullable=True)
    created_ad_set_ids = Column(Text, nullable=True)
    created_ad_ids = Column(Text, nullable=True)
    execution_error = Column(Text, nullable=True)


class RunLogger:
    """Logger for pipeline runs backed by SQLite."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        db_url = f"sqlite:///{db_path or config.DB_PATH}"
        self._engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(self._engine)
        self._session_factory = sessionmaker(bind=self._engine)

    def _session(self) -> Session:
        return self._session_factory()

    def create_run(self, account_id: Optional[str] = None) -> str:
        """Create a new run and return its ID.

        Args:
            account_id: Optional account UUID to associate with this run.
        """
        run_id = str(uuid.uuid4())
        with self._session() as session:
            session.add(RunLog(run_id=run_id, account_id=account_id))
            session.commit()
        return run_id

    def log_ingested_data(self, run_id: str, data_json: str) -> None:
        """Log Phase 1 ingested data."""
        with self._session() as session:
            run = session.get(RunLog, run_id)
            if run:
                run.ingested_data_json = data_json
                session.commit()

    def log_strategy(
            self,
            run_id: str,
            raw_response: str,
            config_json: Optional[str] = None,
            campaign_name: Optional[str] = None,
            objective: Optional[str] = None,
            budget_daily_usd: Optional[float] = None,
            reasoning: Optional[str] = None,
            error: Optional[str] = None,
    ) -> None:
        """Log Phase 2 strategy results."""
        with self._session() as session:
            run = session.get(RunLog, run_id)
            if run:
                run.raw_claude_response = raw_response
                run.campaign_config_json = config_json
                run.campaign_name = campaign_name
                run.objective = objective
                run.budget_daily_usd = budget_daily_usd
                run.reasoning = reasoning
                run.strategy_error = error
                session.commit()

    def log_approval(self, run_id: str, approved: bool) -> None:
        """Log the human approval decision."""
        with self._session() as session:
            run = session.get(RunLog, run_id)
            if run:
                run.approved = approved
                run.approval_timestamp = datetime.now(timezone.utc)
                session.commit()

    def log_execution(
            self,
            run_id: str,
            dry_run: bool,
            campaign_id: Optional[str] = None,
            ad_set_ids: Optional[list[str]] = None,
            ad_ids: Optional[list[str]] = None,
            error: Optional[str] = None,
    ) -> None:
        """Log Phase 3 execution results."""
        with self._session() as session:
            run = session.get(RunLog, run_id)
            if run:
                run.dry_run = dry_run
                run.created_campaign_id = campaign_id
                run.created_ad_set_ids = json.dumps(ad_set_ids) if ad_set_ids else None
                run.created_ad_ids = json.dumps(ad_ids) if ad_ids else None
                run.execution_error = error
                session.commit()

    def get_run(self, run_id: str) -> Optional[RunLog]:
        """Fetch a single run by ID."""
        with self._session() as session:
            return session.get(RunLog, run_id)

    def get_all_runs(self, account_id: Optional[str] = None) -> list[RunLog]:
        """Fetch all runs ordered by creation date descending.

        Args:
            account_id: If provided, filter to runs for this account only.
        """
        with self._session() as session:
            query = session.query(RunLog)
            if account_id is not None:
                query = query.filter(RunLog.account_id == account_id)
            return query.order_by(RunLog.created_at.desc()).all()

    def get_past_run_summaries(self, account_id: Optional[str] = None) -> list[PastRunSummary]:
        """Get summaries of past runs for inclusion in the analysis prompt.

        Args:
            account_id: If provided, filter to runs for this account only.
        """
        with self._session() as session:
            query = (
                session.query(RunLog)
                .filter(RunLog.campaign_config_json.isnot(None))
            )
            if account_id is not None:
                query = query.filter(RunLog.account_id == account_id)
            runs = (
                query.order_by(RunLog.created_at.desc())
                .limit(10)
                .all()
            )
            return [
                PastRunSummary(
                    run_id=run.run_id,
                    created_at=run.created_at.isoformat() if run.created_at else "",
                    campaign_name=run.campaign_name or "",
                    objective=run.objective or "",
                    budget_daily_usd=run.budget_daily_usd or 0.0,
                    reasoning=run.reasoning or "",
                    was_executed=run.created_campaign_id is not None,
                )
                for run in runs
            ]
