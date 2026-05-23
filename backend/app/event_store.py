"""事件档案的内存、本地 JSON 与 SQLite 存储。"""

from __future__ import annotations

from contextlib import contextmanager
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import Iterator, Protocol
from uuid import uuid4

from pydantic import ValidationError

from app.schemas import EventRecord, EventRecordCreate
from app.scoring import analyze_pressure

if os.name == "posix":
    import fcntl
else:
    fcntl = None


_PATH_LOCKS_GUARD = Lock()
_PATH_LOCKS: dict[Path, object] = {}
logger = logging.getLogger(__name__)


class EventStore(Protocol):
    """事件档案存储需要提供的最小接口。"""

    def add(self, payload: EventRecordCreate) -> EventRecord:
        """保存事件记录并返回持久化模型。"""
        ...

    def list(self) -> list[EventRecord]:
        """按展示顺序返回事件记录。"""
        ...

    def delete(self, event_id: str) -> bool:
        """删除指定事件记录，返回是否实际删除。"""
        ...


def get_default_event_store_path() -> Path:
    """返回事件档案 JSON 的默认路径，允许环境变量覆盖。"""
    configured_path = os.getenv("DORM_HARMONY_EVENT_STORE_PATH")
    if configured_path:
        return Path(configured_path)

    return Path(__file__).resolve().parents[1] / ".runtime" / "events.json"


def get_default_sqlite_path() -> Path:
    """返回运行时 SQLite 的默认路径，允许环境变量覆盖。"""
    configured_path = os.getenv("DORM_HARMONY_SQLITE_PATH")
    if configured_path:
        return Path(configured_path)

    return Path(__file__).resolve().parents[1] / ".runtime" / "dorm_harmony.sqlite3"


def _get_path_lock(path: Path) -> object:
    """按存储文件路径复用线程锁，避免同一文件并发写入。"""
    lock_key = path.expanduser().resolve()
    with _PATH_LOCKS_GUARD:
        if lock_key not in _PATH_LOCKS:
            _PATH_LOCKS[lock_key] = Lock()
        return _PATH_LOCKS[lock_key]


@contextmanager
def _exclusive_file_lock(path: Path) -> Iterator[None]:
    """用文件锁保护跨进程读改写；非 POSIX 环境退回到线程锁保护。"""
    if fcntl is None:
        yield
        return

    lock_path = path.with_name(f"{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


class InMemoryEventStore:
    """测试和临时运行使用的内存事件档案存储。"""

    def __init__(self) -> None:
        """初始化空事件列表。"""
        self._events: list[EventRecord] = []

    def add(self, payload: EventRecordCreate) -> EventRecord:
        """创建带唯一 id 和单条压力分析的事件记录。"""
        event = EventRecord(
            **payload.model_dump(),
            id=str(uuid4()),
            created_at=datetime.now(timezone.utc),
            single_analysis=analyze_pressure(payload),
        )
        self._events.append(event)
        return event

    def list(self) -> list[EventRecord]:
        """按事件日期和创建时间倒序返回内存中的事件记录。"""
        return _sort_events(self._events)

    def delete(self, event_id: str) -> bool:
        """删除指定 id 的内存事件记录，返回是否实际删除。"""
        original_count = len(self._events)
        self._events = [
            event for event in self._events if event.id != event_id
        ]
        return len(self._events) != original_count


class JsonEventStore:
    """基于本地 JSON 文件的事件档案存储。"""

    def __init__(self, path: Path | None = None) -> None:
        """初始化存储文件路径和对应的路径级线程锁。"""
        self._path = path or get_default_event_store_path()
        self._lock = _get_path_lock(self._path)

    def add(self, payload: EventRecordCreate) -> EventRecord:
        """读取现有档案、追加新事件，并原子写回 JSON 文件。"""
        with self._lock:
            with _exclusive_file_lock(self._path):
                events = self._load_events()
                event = EventRecord(
                    **payload.model_dump(),
                    id=str(uuid4()),
                    created_at=datetime.now(timezone.utc),
                    single_analysis=analyze_pressure(payload),
                )
                events.append(event)
                self._write_events(events)
                return event

    def list(self) -> list[EventRecord]:
        """从 JSON 文件读取并按展示顺序返回事件档案。"""
        return _sort_events(self._load_events())

    def delete(self, event_id: str) -> bool:
        """读取现有档案、删除指定事件，并原子写回 JSON 文件。"""
        with self._lock:
            with _exclusive_file_lock(self._path):
                events = self._load_events()
                remaining_events = [
                    event for event in events if event.id != event_id
                ]
                if len(remaining_events) == len(events):
                    return False

                self._write_events(remaining_events)
                return True

    def _load_events(self) -> list[EventRecord]:
        """从 JSON 文件加载事件记录，并用 Pydantic 恢复模型。"""
        if not self._path.exists():
            return []

        with self._path.open("r", encoding="utf-8") as file:
            raw_events = json.load(file)

        if not isinstance(raw_events, list):
            raise ValueError("event store JSON must contain a list")

        return [EventRecord.model_validate(event) for event in raw_events]

    def _write_events(self, events: list[EventRecord]) -> None:
        """把事件记录写入临时文件后原子替换目标 JSON 文件。"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        serialized_events = [
            event.model_dump(mode="json")
            for event in _sort_events(events)
        ]

        temporary_path: str | None = None
        try:
            with NamedTemporaryFile(
                "w",
                encoding="utf-8",
                delete=False,
                dir=self._path.parent,
                prefix=f".{self._path.name}.",
                suffix=".tmp",
            ) as temporary_file:
                temporary_path = temporary_file.name
                json.dump(
                    serialized_events,
                    temporary_file,
                    ensure_ascii=False,
                    indent=2,
                )
                temporary_file.write("\n")

            os.replace(temporary_path, self._path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                Path(temporary_path).unlink(missing_ok=True)


class SQLiteEventStore:
    """基于 SQLite 的事件档案存储。"""

    _MIGRATION_IMPORTED = "json_events_imported"
    _MIGRATION_FAILED = "json_events_import_failed"

    def __init__(
        self,
        path: Path | None = None,
        *,
        legacy_json_path: Path | None = None,
    ) -> None:
        """初始化 SQLite 文件路径、schema，并按需导入旧 JSON 档案。"""
        self._path = path or get_default_sqlite_path()
        self._legacy_json_path = legacy_json_path or get_default_event_store_path()
        self._lock = _get_path_lock(self._path)
        with self._lock:
            self._ensure_schema()
            self._import_legacy_json_if_needed()

    def add(self, payload: EventRecordCreate) -> EventRecord:
        """创建带唯一 id 和单条压力分析的事件记录并写入 SQLite。"""
        event = EventRecord(
            **payload.model_dump(),
            id=str(uuid4()),
            created_at=datetime.now(timezone.utc),
            single_analysis=analyze_pressure(payload),
        )
        with self._lock:
            with self._write_connection() as connection:
                self._insert_event(connection, event)
        return event

    def list(self) -> list[EventRecord]:
        """按事件日期和创建时间倒序读取 SQLite 中的事件档案。"""
        with self._read_connection() as connection:
            rows = connection.execute(
                """
                SELECT payload
                FROM events
                ORDER BY event_date DESC, created_at DESC
                """
            ).fetchall()

        return [
            EventRecord.model_validate(json.loads(row["payload"]))
            for row in rows
        ]

    def delete(self, event_id: str) -> bool:
        """删除指定 id 的 SQLite 事件记录，返回是否实际删除。"""
        with self._lock:
            with self._write_connection() as connection:
                cursor = connection.execute(
                    "DELETE FROM events WHERE id = ?",
                    (event_id,),
                )
                return cursor.rowcount > 0

    def _connect(self) -> sqlite3.Connection:
        """创建 SQLite 连接并启用 Row 映射。"""
        connection = sqlite3.connect(self._path, detect_types=0, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _connect_for_write(self) -> sqlite3.Connection:
        """创建写连接，并设置 busy timeout 与 WAL 日志模式。"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = self._connect()
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def _read_connection(self) -> Iterator[sqlite3.Connection]:
        """返回会在使用后显式关闭的读连接。"""
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _write_connection(self) -> Iterator[sqlite3.Connection]:
        """返回会提交或回滚并显式关闭的写连接。"""
        connection = self._connect_for_write()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _ensure_schema(self) -> None:
        """创建事件和运行时迁移记录表。"""
        with self._write_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    event_date TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity INTEGER NOT NULL,
                    frequency TEXT NOT NULL,
                    emotion TEXT NOT NULL,
                    emotions_json TEXT NOT NULL,
                    primary_emotion TEXT NOT NULL,
                    has_communicated INTEGER NOT NULL,
                    has_conflict INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    single_analysis_json TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_migrations (
                    name TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                )
                """
            )

    def _import_legacy_json_if_needed(self) -> None:
        """首次使用 SQLite 且无事件时，将旧 JSON 档案导入一次。"""
        if not self._legacy_json_path.exists():
            return

        with self._read_connection() as connection:
            event_count = connection.execute(
                "SELECT COUNT(*) FROM events"
            ).fetchone()[0]
            migration_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM runtime_migrations
                WHERE name IN (?, ?)
                """,
                (self._MIGRATION_IMPORTED, self._MIGRATION_FAILED),
            ).fetchone()[0]

        if event_count > 0 or migration_count > 0:
            return

        try:
            legacy_events = self._load_legacy_json_events()
        except (json.JSONDecodeError, ValueError, ValidationError):
            logger.exception(
                "Failed to import legacy event archive JSON from %s",
                self._legacy_json_path,
            )
            try:
                with self._write_connection() as connection:
                    self._record_migration(connection, self._MIGRATION_FAILED)
            except Exception:
                logger.exception(
                    "Failed to record legacy event archive import failure"
                )
            return

        with self._write_connection() as connection:
            for event in legacy_events:
                self._insert_event(connection, event)
            self._record_migration(connection, self._MIGRATION_IMPORTED)

    def _load_legacy_json_events(self) -> list[EventRecord]:
        """从旧 JSON 文件加载事件记录。"""
        with self._legacy_json_path.open("r", encoding="utf-8") as file:
            raw_events = json.load(file)

        if not isinstance(raw_events, list):
            raise ValueError("event store JSON must contain a list")

        return [
            EventRecord.model_validate(event)
            for event in raw_events
        ]

    def _insert_event(
        self,
        connection: sqlite3.Connection,
        event: EventRecord,
    ) -> None:
        """把完整事件模型序列化为 JSON 并写入 events 表。"""
        serialized_event = event.model_dump(mode="json")
        connection.execute(
            """
            INSERT INTO events (
                id,
                event_date,
                created_at,
                event_type,
                severity,
                frequency,
                emotion,
                emotions_json,
                primary_emotion,
                has_communicated,
                has_conflict,
                description,
                single_analysis_json,
                payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                serialized_event["id"],
                serialized_event["event_date"],
                serialized_event["created_at"],
                serialized_event["event_type"],
                serialized_event["severity"],
                serialized_event["frequency"],
                serialized_event["emotion"],
                json.dumps(serialized_event["emotions"], ensure_ascii=False),
                serialized_event["primary_emotion"],
                int(serialized_event["has_communicated"]),
                int(serialized_event["has_conflict"]),
                serialized_event["description"],
                json.dumps(serialized_event["single_analysis"], ensure_ascii=False),
                json.dumps(serialized_event, ensure_ascii=False),
            ),
        )

    def _record_migration(
        self,
        connection: sqlite3.Connection,
        migration_name: str,
    ) -> None:
        """记录一次运行时迁移，重复记录时保持幂等。"""
        connection.execute(
            """
            INSERT OR IGNORE INTO runtime_migrations (name, created_at)
            VALUES (?, ?)
            """,
            (migration_name, datetime.now(timezone.utc).isoformat()),
        )


def _sort_events(events: list[EventRecord]) -> list[EventRecord]:
    """按事件日期和创建时间倒序排列档案记录。"""
    return sorted(
        events,
        key=lambda event: (event.event_date, event.created_at),
        reverse=True,
    )
