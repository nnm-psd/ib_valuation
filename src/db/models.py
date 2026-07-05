"""
SQLAlchemy schema for storing normalized financials, so the crawler only
has to run once per company/year and every model reads from this DB
instead of re-parsing XBRL every time.
"""
from __future__ import annotations

from sqlalchemy import Column, Integer, String, Float, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from config.settings import DB_URL, DB_PATH

Base = declarative_base()


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    ticker = Column(String, nullable=True)
    country = Column(String, nullable=False)
    sector = Column(String, nullable=True)

    financial_lines = relationship("FinancialLine", back_populates="company")


class FinancialLine(Base):
    """
    One row per (company, fiscal_year, canonical_field). Storing it long-form
    rather than one wide table per statement keeps schema migrations cheap
    as you add new canonical fields over time.
    """
    __tablename__ = "financial_lines"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    statement = Column(String, nullable=False)   # "income_statement" | "balance_sheet" | "cash_flow"
    field_name = Column(String, nullable=False)  # canonical field, e.g. "revenue"
    value = Column(Float, nullable=True)

    company = relationship("Company", back_populates="financial_lines")


class MarketDataPoint(Base):
    __tablename__ = "market_data"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    date = Column(String, nullable=False)
    close_price = Column(Float, nullable=True)
    shares_outstanding = Column(Float, nullable=True)


engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
