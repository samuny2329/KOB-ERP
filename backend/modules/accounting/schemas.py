"""Pydantic schemas for the accounting module."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AccountCreate(_Base):
    code: str
    name: str
    account_type: str
    parent_id: int | None = None
    currency: str = "THB"
    reconcilable: bool = False
    notes: str | None = None


class AccountRead(_Base):
    id: int
    code: str
    name: str
    account_type: str
    parent_id: int | None
    currency: str
    active: bool
    reconcilable: bool


class JournalCreate(_Base):
    code: str
    name: str
    journal_type: str
    default_debit_account_id: int | None = None
    default_credit_account_id: int | None = None


class JournalRead(_Base):
    id: int
    code: str
    name: str
    journal_type: str
    active: bool


class JeLineCreate(_Base):
    account_id: int
    debit: float = 0
    credit: float = 0
    currency: str = "THB"
    memo: str | None = None


class JeLineRead(_Base):
    id: int
    account_id: int
    debit: float
    credit: float
    currency: str
    memo: str | None
    reconciled: bool


class JournalEntryCreate(_Base):
    number: str
    journal_id: int
    entry_date: date
    reference: str | None = None
    memo: str | None = None
    lines: list[JeLineCreate] = []


class JournalEntryRead(_Base):
    id: int
    number: str
    journal_id: int
    state: str
    entry_date: date
    reference: str | None
    memo: str | None
    posted_at: datetime | None
    lines: list[JeLineRead] = []


class TaxRateCreate(_Base):
    code: str
    name: str
    rate_pct: float
    tax_type: str = "vat"
    account_id: int | None = None


class TaxRateRead(_Base):
    id: int
    code: str
    name: str
    rate_pct: float
    tax_type: str
    active: bool
