"""Application-owned database resources and explicit operation boundaries."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Concatenate

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from zzerp.config import Settings


class Base(DeclarativeBase):
    pass


@dataclass(frozen=True, slots=True)
class Database:
    engine: Engine
    sessions: sessionmaker[Session]

    @classmethod
    def create(cls, settings: Settings) -> "Database":
        engine = create_engine(settings.database_url, pool_pre_ping=True, pool_recycle=300)
        return cls(engine, sessionmaker(bind=engine, autoflush=False, expire_on_commit=False))

    def query[**P, T](
        self,
        operation: Callable[Concatenate[Session, P], T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        with self.sessions() as session:
            return operation(session, *args, **kwargs)

    def command[**P, T](
        self,
        operation: Callable[Concatenate[Session, P], T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        with self.sessions.begin() as session:
            result = operation(session, *args, **kwargs)
        return result

    def is_ready(self) -> bool:
        with self.engine.connect() as connection:
            return bool(connection.scalar(text("SELECT to_regclass('public.users') IS NOT NULL")))

    def close(self) -> None:
        self.engine.dispose()
