"""Unit of Work — opt-in transaction scope for multi-service operations.

Most service methods commit on their own (legacy). When you need *several*
service calls to land atomically (booking + payment + notification), wrap
them in a UnitOfWork. Inside the ``async with`` block, services should call
``uow.flush()`` rather than ``uow.commit()`` — the commit happens at the end
of the block on success, or rolls back on error.

Example:

    async def book_and_pay(uow: UnitOfWork, ...):
        async with uow:
            booking = await bookings.create(...)
            await payments.initiate(...)

NOTE: existing services have their own commits. Rewriting all of them is in
the Repository/Service refactor (#14) — until then, pass the UoW's session
into service constructors and call services that follow the new flush-only
contract.
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from types import TracebackType

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db


class UnitOfWork(AbstractAsyncContextManager["UnitOfWork"]):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._depth = 0
        self._failed = False

    async def __aenter__(self) -> "UnitOfWork":
        self._depth += 1
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._depth -= 1
        if exc is not None:
            self._failed = True
        if self._depth > 0:
            return
        try:
            if self._failed:
                await self.session.rollback()
            else:
                await self.session.commit()
        finally:
            self._failed = False

    async def flush(self) -> None:
        await self.session.flush()


def get_unit_of_work(
    session: AsyncSession = Depends(get_db),
) -> UnitOfWork:
    return UnitOfWork(session)
