"""沟通复盘报告的 SQLite 历史存储。"""

from __future__ import annotations

from contextlib import contextmanager
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Iterator
from uuid import uuid4

from app.event_store import get_default_sqlite_path
from app.schemas import (
    DialogueMessage,
    ReviewReportDetail,
    ReviewReportSummary,
    ReviewRequest,
    ReviewResponse,
)


_PATH_LOCKS_GUARD = Lock()
_PATH_LOCKS: dict[Path, Lock] = {}


def _get_path_lock(path: Path) -> Lock:
    """按 SQLite 文件路径复用线程锁，避免同一路径并发写入。"""
    lock_key = path.expanduser().resolve()
    with _PATH_LOCKS_GUARD:
        if lock_key not in _PATH_LOCKS:
            _PATH_LOCKS[lock_key] = Lock()
        return _PATH_LOCKS[lock_key]


class SQLiteReviewHistoryStore:
    """基于 SQLite 的沟通复盘历史存储。"""

    def __init__(self, path: Path | None = None) -> None:
        """初始化 SQLite 文件路径并确保 review_reports 表存在。"""
        self._path = path or get_default_sqlite_path()
        self._lock = _get_path_lock(self._path)
        with self._lock:
            self._ensure_schema()

    def add(
        self,
        request: ReviewRequest,
        response: ReviewResponse,
        dialogue: list[DialogueMessage],
    ) -> ReviewReportDetail:
        """保存一次复盘报告，并返回完整详情。"""
        report_id = str(uuid4())
        created_at = datetime.now(timezone.utc)
        dialogue_snapshot = dialogue[-50:]

        with self._lock:
            with self._write_connection() as connection:
                connection.execute(
                    """
                    INSERT INTO review_reports (
                        id,
                        created_at,
                        conversation_id,
                        scenario,
                        request_json,
                        response_json,
                        dialogue_json,
                        summary,
                        score_clarity,
                        score_empathy,
                        score_resolution
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_id,
                        created_at.isoformat(),
                        request.conversation_id,
                        request.scenario,
                        json.dumps(
                            request.model_dump(mode="json"),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                        json.dumps(
                            response.model_dump(mode="json"),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                        json.dumps(
                            [
                                message.model_dump(mode="json")
                                for message in dialogue_snapshot
                            ],
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                        response.summary,
                        response.performance_scores.clarity,
                        response.performance_scores.empathy,
                        response.performance_scores.resolution,
                    ),
                )

        return ReviewReportDetail(
            id=report_id,
            created_at=created_at,
            conversation_id=request.conversation_id,
            scenario=request.scenario,
            summary=response.summary,
            score_clarity=response.performance_scores.clarity,
            score_empathy=response.performance_scores.empathy,
            score_resolution=response.performance_scores.resolution,
            request=request,
            response=response,
            dialogue=dialogue_snapshot,
        )

    def list(self, limit: int = 20) -> list[ReviewReportSummary]:
        """按创建时间倒序返回复盘报告摘要。"""
        normalized_limit = max(0, limit)
        with self._read_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    created_at,
                    conversation_id,
                    scenario,
                    summary,
                    score_clarity,
                    score_empathy,
                    score_resolution
                FROM review_reports
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (normalized_limit,),
            ).fetchall()

        return [self._row_to_summary(row) for row in rows]

    def get(self, review_id: str) -> ReviewReportDetail | None:
        """读取单条复盘报告详情，缺失时返回 None。"""
        with self._read_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM review_reports
                WHERE id = ?
                """,
                (review_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_detail(row)

    def delete(self, review_id: str) -> bool:
        """删除单条复盘报告，返回是否实际删除。"""
        with self._lock:
            with self._write_connection() as connection:
                cursor = connection.execute(
                    """
                    DELETE FROM review_reports
                    WHERE id = ?
                    """,
                    (review_id,),
                )
                deleted = cursor.rowcount > 0

        return deleted

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
        """创建复盘报告表。"""
        with self._write_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS review_reports (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    conversation_id TEXT,
                    scenario TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    dialogue_json TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    score_clarity INTEGER NOT NULL,
                    score_empathy INTEGER NOT NULL,
                    score_resolution INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_review_reports_created_at
                ON review_reports(created_at DESC)
                """
            )

    def _row_to_summary(self, row: sqlite3.Row) -> ReviewReportSummary:
        """把 SQLite 行转换为复盘摘要 schema。"""
        return ReviewReportSummary(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            conversation_id=row["conversation_id"],
            scenario=row["scenario"],
            summary=row["summary"],
            score_clarity=row["score_clarity"],
            score_empathy=row["score_empathy"],
            score_resolution=row["score_resolution"],
        )

    def _row_to_detail(self, row: sqlite3.Row) -> ReviewReportDetail:
        """把 SQLite 行转换为复盘详情 schema。"""
        return ReviewReportDetail(
            **self._row_to_summary(row).model_dump(),
            request=ReviewRequest.model_validate(json.loads(row["request_json"])),
            response=ReviewResponse.model_validate(json.loads(row["response_json"])),
            dialogue=[
                DialogueMessage.model_validate(message)
                for message in json.loads(row["dialogue_json"])
            ],
        )
