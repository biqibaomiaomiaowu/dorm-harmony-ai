"""事件档案的内存与本地 JSON 存储。"""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import Iterator
from uuid import uuid4

from app.schemas import EventRecord, EventRecordCreate
from app.scoring import analyze_pressure

if os.name == "posix":
    import fcntl
else:
    fcntl = None


_PATH_LOCKS_GUARD = Lock()
_PATH_LOCKS: dict[Path, object] = {}


def get_default_event_store_path() -> Path:
    """返回事件档案 JSON 的默认路径，允许环境变量覆盖。"""
    configured_path = os.getenv("DORM_HARMONY_EVENT_STORE_PATH")
    if configured_path:
        return Path(configured_path)

    return Path(__file__).resolve().parents[1] / ".runtime" / "events.json"


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


def _sort_events(events: list[EventRecord]) -> list[EventRecord]:
    """按事件日期和创建时间倒序排列档案记录。"""
    return sorted(
        events,
        key=lambda event: (event.event_date, event.created_at),
        reverse=True,
    )
