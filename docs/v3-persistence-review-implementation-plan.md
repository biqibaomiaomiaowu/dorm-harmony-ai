# 舍友心晴 V3 持久化与复盘产品化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 V2 演示链路升级为 SQLite 持久化、stream 模拟、趋势分析和复盘产品化的 V3 本地产品闭环。

**Architecture:** 后端使用统一 SQLite 运行时文件承载事件档案、LangGraph checkpoint 会话记忆和复盘历史；前端把模拟会话逻辑抽为 composable，并让页面通过 stream、历史、导出和“再练一次”形成闭环。新增 UI 必须沿用现有 pop-card、粗边框、Material Symbols、弹性入场、Transition/TransitionGroup 和 scoped CSS 风格。

**Tech Stack:** FastAPI, Pydantic v2, sqlite3, LangGraph, `langgraph-checkpoint-sqlite`, Vue 3, TypeScript, Vite, ECharts, localStorage.

---

## Agent Execution Rules

- Do not close, terminate, or interrupt any subagent that is still running normally.
- Only handle termination or re-dispatch when a subagent has completed, explicitly reports `BLOCKED` / `NEEDS_CONTEXT`, the user explicitly asks to stop it, or it shows abnormal unsafe behavior.
- Review subagents are read-only unless their prompt explicitly grants a write scope.
- No task may stage or commit `.superpowers/` or `docs/superpowers/`.

## File Structure

- Modify `backend/requirements.txt`: add `langgraph-checkpoint-sqlite`.
- Modify `backend/app/event_store.py`: introduce runtime SQLite path helper and `SQLiteEventStore`; keep `InMemoryEventStore` for tests.
- Modify `backend/app/ai_service.py`: replace default `InMemorySaver` use with SQLite-backed `ConversationMemory`, backed by `conversation_meta`.
- Modify `backend/app/schemas.py`: add review history schemas and `communication_plan`.
- Create `backend/app/review_store.py`: SQLite review history persistence.
- Modify `backend/app/main.py`: default event store to SQLite, wire review history store, add `GET /api/reviews`, `GET /api/reviews/{review_id}`.
- Modify `backend/tests/test_event_archive.py`: cover `SQLiteEventStore`.
- Modify `backend/tests/test_ai_service.py`: cover SQLite conversation persistence after rebuilding memory.
- Modify `backend/tests/test_api.py`: cover review history endpoints and stream compatibility.
- Modify `frontend/src/data/week1.ts`: add communication plan fields, improve stream error metadata.
- Modify `frontend/src/data/eventArchive.ts`: expose event archive data for trend chart generation.
- Create `frontend/src/data/reviewHistory.ts`: review history API helpers and validators.
- Create `frontend/src/composables/useSimulationSession.ts`: stream-based simulation state machine.
- Modify `frontend/src/views/SimulationView.vue`: consume composable, add fixed expired-session UI, support `practice` query prefill.
- Modify `frontend/src/views/AnalysisView.vue`: add ECharts trend chart with responsive lifecycle and animated reveal.
- Modify `frontend/src/views/ReviewView.vue`: add history, export Markdown/image, communication plan, emphasized rewrite comparison, dialogue entry card/modal, practice-again action.
- Modify `frontend/src/router/index.ts`: keep route names stable; no new route required.
- Modify `frontend/src/styles/main.css` only if shared utility styles are needed; otherwise keep styles scoped in changed views.
- Modify `README.md`, `docs/backend-api-contract.md`, `docs/v2-features.md`, `docs/phase3-status.md`: document V3 behavior.

## Task 0: Working Branch And Baseline

**Files:**
- No code files.

- [ ] **Step 1: Create an implementation branch**

Run:

```bash
git switch -c codex/v3-persistence-review
```

Expected: branch switches from `main` to `codex/v3-persistence-review`.

- [ ] **Step 2: Check clean status before implementation**

Run:

```bash
git status --short
```

Expected: only `docs/v3-persistence-review-design.md` and `docs/v3-persistence-review-implementation-plan.md` appear in git status before the first docs commit; no `.superpowers/` files appear. `AGENTS.md` is repository-local instruction state and is ignored by git.

- [ ] **Step 3: Commit approved design and plan**

Run:

```bash
git add docs/v3-persistence-review-design.md docs/v3-persistence-review-implementation-plan.md
git commit -m "docs: 记录 V3 持久化与复盘产品化方案"
```

Expected: commit succeeds and contains no `.superpowers/` path.

## Task 1: SQLite Event Store

**Files:**
- Modify `backend/requirements.txt`
- Modify `backend/app/event_store.py`
- Modify `backend/app/main.py`
- Modify `backend/tests/test_event_archive.py`
- Modify `backend/tests/test_api.py`

- [ ] **Step 1: Add failing SQLite event store tests**

Add tests that assert:

```python
def test_sqlite_event_store_persists_and_lists_events(tmp_path):
    store_path = tmp_path / "dorm_harmony.sqlite3"
    store = SQLiteEventStore(store_path)
    saved = store.add(EventRecordCreate(...))

    restored = SQLiteEventStore(store_path).list()

    assert [event.id for event in restored] == [saved.id]
    assert restored[0].single_analysis.pressure_score == saved.single_analysis.pressure_score
```

Also add:

```python
def test_sqlite_event_store_deletes_event(tmp_path):
    store = SQLiteEventStore(tmp_path / "dorm_harmony.sqlite3")
    saved = store.add(EventRecordCreate(...))

    assert store.delete(saved.id) is True
    assert store.list() == []
    assert store.delete("missing") is False
```

Add migration coverage:

```python
def test_sqlite_event_store_imports_legacy_json_once(tmp_path):
    sqlite_path = tmp_path / "dorm_harmony.sqlite3"
    json_path = tmp_path / "events.json"
    legacy_event = InMemoryEventStore().add(EventRecordCreate(...))
    json_path.write_text(
        json.dumps([legacy_event.model_dump(mode="json")], ensure_ascii=False),
        encoding="utf-8",
    )

    first = SQLiteEventStore(sqlite_path, legacy_json_path=json_path).list()
    second = SQLiteEventStore(sqlite_path, legacy_json_path=json_path).list()

    assert [event.id for event in first] == [legacy_event.id]
    assert [event.id for event in second] == [legacy_event.id]
```

Run:

```bash
cd backend && pytest tests/test_event_archive.py -q
```

Expected: FAIL because `SQLiteEventStore` does not exist.

- [ ] **Step 2: Implement runtime path and SQLiteEventStore**

In `backend/app/event_store.py`, add `get_default_sqlite_path()` using `DORM_HARMONY_SQLITE_PATH` or `backend/.runtime/dorm_harmony.sqlite3`.

Implement `SQLiteEventStore` with:

- `_connect()` using `sqlite3.connect(self._path, detect_types=0, timeout=5)` and `row_factory = sqlite3.Row`.
- `_ensure_schema()` creating `events` and `runtime_migrations`.
- `PRAGMA busy_timeout = 5000` and `PRAGMA journal_mode = WAL` on connections used for writes.
- `add()`, `list()`, `delete()` matching `JsonEventStore` behavior.
- JSON serialization through `EventRecord.model_dump(mode="json")` and `AnalyzeResponse` validation through `EventRecord.model_validate(...)`.
- `_import_legacy_json_if_needed()` that imports `backend/.runtime/events.json` only when `events` is empty and `runtime_migrations` contains neither `json_events_imported` nor `json_events_import_failed`.
- If legacy JSON validation fails, log the error and write `json_events_import_failed` so the same corrupt file does not produce repeated startup noise.

In `backend/app/main.py`, import `SQLiteEventStore` and return it from `get_event_store()`.

- [ ] **Step 3: Add dependency**

In `backend/requirements.txt`, add:

```text
langgraph-checkpoint-sqlite>=3.0.3,<4
```

This is needed for Task 2 but belongs in the same backend persistence dependency pass. The version range uses the current stable `SqliteSaver` package line and avoids depending on pre-release builds.

- [ ] **Step 4: Run event and API tests**

Run:

```bash
cd backend && pytest tests/test_event_archive.py tests/test_api.py -q
```

Expected: PASS or only failures directly caused by later unimplemented review-history assertions.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/requirements.txt backend/app/event_store.py backend/app/main.py backend/tests/test_event_archive.py backend/tests/test_api.py
git commit -m "feat(backend): 使用 SQLite 持久化事件档案"
```

## Task 2: SQLite Conversation Memory

**Files:**
- Modify `backend/app/ai_service.py`
- Modify `backend/tests/test_ai_service.py`
- Modify `backend/tests/test_api.py`

- [ ] **Step 1: Add failing conversation persistence test**

Add a test that constructs two `ConversationMemory` instances against the same temporary SQLite path:

```python
def test_conversation_memory_persists_with_sqlite_checkpointer(tmp_path):
    db_path = tmp_path / "memory.sqlite3"
    first_memory = ai_service.ConversationMemory.sqlite(db_path)
    service = DormHarmonyAIService(runner=FakeRunner(), memory=first_memory)
    first = service.simulate(SimulateRequest(scenario="噪音冲突", user_message="晚上能不能小声一点？"))

    second_memory = ai_service.ConversationMemory.sqlite(db_path)
    second_service = DormHarmonyAIService(runner=FakeRunner(), memory=second_memory)
    dialogue = second_service.resolve_review_dialogue(
        ReviewRequest(conversation_id=first.conversation_id, scenario="噪音冲突")
    )

    assert any(line.speaker == "user" and "小声" in line.message for line in dialogue)
```

Run:

```bash
cd backend && pytest tests/test_ai_service.py::test_conversation_memory_persists_with_sqlite_checkpointer -q
```

Expected: FAIL because `ConversationMemory.sqlite()` does not exist.

- [ ] **Step 2: Implement SQLite-backed ConversationMemory**

In `backend/app/ai_service.py`:

- Add `sqlite3`, `Path`, `datetime`, `timezone`, `RLock` or `Lock` imports as needed.
- Add `ConversationMemory.sqlite(path: Path) -> ConversationMemory`.
- Set `os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")` before importing or constructing the SQLite checkpointer.
- Use a long-lived connection and checkpointer:

```python
from langgraph.checkpoint.sqlite import SqliteSaver

connection = sqlite3.connect(path, check_same_thread=False, timeout=5)
connection.execute("PRAGMA busy_timeout = 5000")
connection.execute("PRAGMA journal_mode = WAL")
checkpointer = SqliteSaver(connection)
checkpointer.setup()
```

- Do not store `SqliteSaver.from_conn_string(str(path))` directly as the checkpointer because that API returns a context manager. If using it in tests, enter the context explicitly and keep it alive for the whole memory lifetime.
- Create and maintain `conversation_meta`.
- Replace `_conversation_ids` and `_latest_turn_ids` default runtime dependence with metadata table reads/writes.
- Keep in-memory behavior working when caller passes an `InMemorySaver`.
- Store `self._sqlite_connection` on SQLite-backed memory so the connection is not garbage-collected while FastAPI is running.
- Use a small lock around graph update/get and metadata writes if a shared SQLite memory object can be accessed by concurrent FastAPI requests.

Public behavior:

- `start_conversation(None)` creates new id and metadata.
- `start_conversation(existing)` registers metadata if missing only for newly created local flows.
- `_resolve_conversation_id()` still raises `ConversationMemoryNotFoundError` when request passes a missing id.
- `mark_latest_turn()` persists latest turn id.
- `is_latest_turn()` reads latest turn id from SQLite metadata.

- [ ] **Step 3: Wire default memory**

In `backend/app/main.py`, create `_SHARED_CONVERSATION_MEMORY = ConversationMemory.sqlite(get_default_sqlite_path())` or equivalent helper import.

- [ ] **Step 4: Run AI and stream tests**

Run:

```bash
cd backend && pytest tests/test_ai_service.py tests/test_api.py -q
```

Expected: PASS for existing simulate, review, and stream tests.

- [ ] **Step 5: Commit**

Run:

```bash
git add backend/app/ai_service.py backend/app/main.py backend/tests/test_ai_service.py backend/tests/test_api.py
git commit -m "feat(ai): 使用 SQLite 持久化模拟会话记忆"
```

## Task 3: Review History API And Communication Plan

**Files:**
- Modify `backend/app/schemas.py`
- Create `backend/app/review_store.py`
- Modify `backend/app/ai_service.py`
- Modify `backend/app/main.py`
- Modify `backend/tests/test_ai_service.py`
- Modify `backend/tests/test_api.py`

- [ ] **Step 1: Add failing schema and API tests**

Add tests for:

```python
def test_review_response_includes_fallback_communication_plan():
    response = DormHarmonyAIService(runner=DraftRunnerWithoutPlan(), memory=ConversationMemory()).review(...)
    assert response.communication_plan.opening
    assert response.communication_plan.specific_request
    assert response.communication_plan.fallback_plan
```

Add a service-layer dialogue source test:

```python
def test_review_with_dialogue_result_exposes_actual_dialogue():
    service = DormHarmonyAIService(runner=FakeRunner(), memory=ConversationMemory())
    result = service.review_with_dialogue(
        ReviewRequest(
            scenario="噪音冲突",
            dialogue=[DialogueMessage(speaker="user", message="晚上能不能小声一点？")],
        )
    )

    assert result.response.summary
    assert result.dialogue[0].speaker == "user"
```

Add API tests:

```python
def test_review_endpoint_persists_report_history(tmp_path):
    app.dependency_overrides[get_ai_service] = lambda: FakeAIService()
    app.dependency_overrides[get_review_history_store] = lambda: SQLiteReviewHistoryStore(tmp_path / "reviews.sqlite3")

    create = client.post("/api/review", json={...})
    listing = client.get("/api/reviews")
    detail = client.get(f"/api/reviews/{listing.json()['reports'][0]['id']}")

    assert create.status_code == 200
    assert listing.status_code == 200
    assert detail.status_code == 200
```

Run:

```bash
cd backend && pytest tests/test_ai_service.py tests/test_api.py -q
```

Expected: FAIL because schemas/store/routes do not exist.

- [ ] **Step 2: Implement schemas**

In `backend/app/schemas.py`, add:

- `CommunicationPlan`
- `ReviewWithDialogueResult` if implemented as a schema, or keep it as a dataclass in `ai_service.py` when it is only service-internal.
- `ReviewReportSummary`
- `ReviewReportDetail`
- `ReviewHistoryResponse`

Add optional or defaulted `communication_plan: CommunicationPlan` to `ReviewResponse`.

- [ ] **Step 3: Implement ReviewHistoryStore**

Create `backend/app/review_store.py` with:

- `SQLiteReviewHistoryStore`
- `add(request, response, dialogue) -> ReviewReportDetail`
- `list(limit=20) -> list[ReviewReportSummary]`
- `get(review_id) -> ReviewReportDetail | None`

Use the same SQLite path helper from `event_store.py`.

- [ ] **Step 4: Persist reports from POST /api/review**

In `backend/app/main.py`:

- Add dependency `get_review_history_store()`.
- Replace the route call with `ai_service.review_with_dialogue(request)` or call a public `ai_service.resolve_review_dialogue(request)` before/after `review(request)`.
- Do not call private service methods from route code.
- Persist exactly the `dialogue` used by the AI review. If an injected fake service only exposes `review(request)`, fall back to `request.dialogue[-50:]`.
- Store non-demo review result.
- Add `GET /api/reviews` and `GET /api/reviews/{review_id}`.
- `GET /api/reviews` accepts optional `limit` with default 20 and maximum 50.
- `GET /api/reviews/{review_id}` returns 404 when missing.

- [ ] **Step 5: Run backend tests**

Run:

```bash
cd backend && pytest -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add backend/app/schemas.py backend/app/review_store.py backend/app/ai_service.py backend/app/main.py backend/tests/test_ai_service.py backend/tests/test_api.py
git commit -m "feat(backend): 保存沟通复盘历史"
```

## Task 4: Stream Simulation Composable

**Files:**
- Create `frontend/src/composables/useSimulationSession.ts`
- Modify `frontend/src/data/week1.ts`
- Modify `frontend/src/views/SimulationView.vue`

- [ ] **Step 1: Refactor data helper errors**

In `frontend/src/data/week1.ts`, extend `SimulationStreamRequestError`:

```ts
export class SimulationStreamRequestError extends Error {
  recoverable: boolean
  status: number | null
  detail: string
}
```

Set `status` and `detail` when `/api/simulate/stream` returns non-OK. Keep existing callers compatible by giving constructor defaults.

Also change `submitSimulationStreamRequest` signature to accept an abort signal:

```ts
export async function submitSimulationStreamRequest(
  payload: SimulationRequest,
  handlers: SimulationStreamHandlers = {},
  signal?: AbortSignal,
): Promise<SimulationResponse>
```

Pass `signal` into `fetch`. If abort occurs while reading the stream, call `reader.cancel()` in `finally` when possible and rethrow the browser `AbortError`.

- [ ] **Step 2: Create composable**

Create `useSimulationSession.ts` with:

- State refs currently owned by `SimulationView.vue` for AI session only.
- `sendMessage(message)` using `submitSimulationStreamRequest`.
- `onStart` sets `conversationId`.
- `onReply` appends roommate messages immediately.
- `final` updates meta and persists `SIMULATION_RESULT_STORAGE_KEY`.
- 400 missing-memory error maps to `sessionErrorState = 'expired'`.
- `resetConversation(options?)` clears cache and aborts active request.
- A `runId` or monotonically increasing token prevents stale stream events from mutating state after reset or a newer send.
- Active `AbortController` is stored in the composable; reset and expired-session retry abort the current stream before clearing state.

Keep non-session inputs injected through callbacks/options:

```ts
useSimulationSession({
  getScenario,
  getRoommates,
  getRiskLevel,
  getContext,
  getUseEventArchive,
})
```

- [ ] **Step 3: Rewrite SimulationView to consume composable**

Move request loop, queueing, continuation and cache persistence out of the view. Keep:

- roommate editing
- custom scenario management
- archive switch
- visual template
- fixed expired-session panel
- query `practice` prefill

Add UI:

```vue
<section v-if="sessionErrorState === 'expired'" class="simulation-session-error pop-card pop-shadow">
  <span class="material-symbol">sync_problem</span>
  <h2>会话已失效</h2>
  <p>当前会话无法继续，请一键重新开始后再发送。</p>
  <button class="primary-action pop-shadow" @click="retryFromExpiredSession(userMessage)">重新开始</button>
</section>
```

Use `<Transition name="chat-state">` and existing pop-card style.

- [ ] **Step 4: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add frontend/src/data/week1.ts frontend/src/composables/useSimulationSession.ts frontend/src/views/SimulationView.vue
git commit -m "feat(frontend): 接入流式沟通模拟"
```

## Task 5: Analysis Trend Chart

**Files:**
- Modify `frontend/src/views/AnalysisView.vue`

- [ ] **Step 1: Add trend data loading**

In `AnalysisView.vue`, fetch `fetchEventArchive()` during analysis load and build date buckets:

```ts
interface TrendPoint {
  date: string
  score: number
  count: number
}
```

Sort by date ascending, group same-day scores by average, use latest 14 points.

- [ ] **Step 2: Add ECharts lifecycle**

Import ECharts:

```ts
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
```

Register modules, create `trendChartRef`, initialize after `nextTick`, resize on window resize, dispose on unmount.

- [ ] **Step 3: Add styled chart panel**

Add a panel matching existing analysis cards:

```vue
<article class="analysis-trend-panel pop-card pop-shadow page-pop-in">
  <h2><span class="material-symbol">show_chart</span>压力趋势图</h2>
  <div ref="trendChartRef" class="analysis-trend-chart"></div>
</article>
```

Use scoped CSS with 2px border, rounded card style consistent with current page, and a fade/slide transition when chart becomes ready.

- [ ] **Step 4: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add frontend/src/views/AnalysisView.vue
git commit -m "feat(frontend): 增加压力趋势图"
```

## Task 6: Review Productization

**Files:**
- Create `frontend/src/data/reviewHistory.ts`
- Modify `frontend/src/data/week1.ts`
- Modify `frontend/src/views/ReviewView.vue`
- Modify `frontend/src/views/SimulationView.vue`

- [ ] **Step 1: Add review history API helper**

Create `reviewHistory.ts` with:

- `fetchReviewHistory()`
- `fetchReviewReport(id)`
- validators for `ReviewHistoryResponse`, `ReviewReportSummary`, `ReviewReportDetail`

- [ ] **Step 2: Extend ReviewResponse type**

In `week1.ts`, add:

```ts
export interface CommunicationPlan {
  opening: string
  specific_request: string
  fallback_plan: string
}
```

Add `communication_plan: CommunicationPlan` to `ReviewResponse`, normalization fallback in demo and API parsing.

- [ ] **Step 3: Add history and report selection**

In `ReviewView.vue`, load history after current review loads. Add a compact history rail/list using existing card style:

- current report active state
- click history item loads detail
- transition between report bodies

- [ ] **Step 4: Replace inline dialogue list with entry card and modal**

In `ReviewView.vue`, remove the always-visible full dialogue section from the main report body. Add a compact entry card near the context/summary area:

```vue
<article class="review-dialogue-entry-card pop-card pop-shadow">
  <span class="material-symbol" aria-hidden="true">forum</span>
  <div>
    <h2>完整对话记录</h2>
    <p>{{ dialogueStats.userTurns }} 轮用户表达 · {{ dialogueStats.roommateReplies }} 条舍友反馈</p>
  </div>
  <button class="secondary-action pop-shadow" type="button" @click="openDialogueModal">
    查看完整对话
  </button>
</article>
```

Add a modal with:

- `showDialogueModal` state.
- Esc key close.
- overlay click close.
- focus returns to the entry button after close.
- full `reviewDialogue` list rendered inside the modal, not in the main page.
- `<Transition name="review-dialogue-modal">` for fade/scale entry.

Keep visual style aligned with current safety modal and roommate locked modal patterns.

- [ ] **Step 5: Add export Markdown**

Implement `exportReviewMarkdown()` using Blob download. Include:

- scenario
- score cards
- summary
- strengths/risks
- original vs suggested messages
- communication plan
- next steps
- safety note

- [ ] **Step 6: Add export image**

Add `ref="reviewExportRef"` on the report body. Implement `exportReviewImage()` using SVG `foreignObject` serialization into a canvas. On failure, set `reviewExportError = '图片导出失败，请改用 Markdown 导出。'`.

- [ ] **Step 7: Add communication plan and practice again**

Render communication plan in a new card:

```vue
<article class="review-plan-card pop-card pop-shadow">
  <h2>沟通计划卡片</h2>
  <p><strong>开场白</strong>{{ reviewResponse.communication_plan.opening }}</p>
  <p><strong>具体请求</strong>{{ reviewResponse.communication_plan.specific_request }}</p>
  <p><strong>兜底方案</strong>{{ reviewResponse.communication_plan.fallback_plan }}</p>
</article>
```

Update “再次演练” to:

```ts
router.push({ name: 'simulate', query: { scenario: reviewRequest.scenario, practice: practiceMessage.value } })
```

- [ ] **Step 8: Ensure visual and motion fit**

Use current visual language:

- `pop-card`, `pop-shadow`, `card-border`
- Material Symbols for export/history/refresh
- `Transition` for state panels and dialogue modal
- `TransitionGroup` for history and suggestions
- no nested cards inside cards
- no new one-note palette
- complete dialogue records are not always visible in the main report; they live behind the entry card modal

- [ ] **Step 9: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 10: Commit**

Run:

```bash
git add frontend/src/data/reviewHistory.ts frontend/src/data/week1.ts frontend/src/views/ReviewView.vue frontend/src/views/SimulationView.vue
git commit -m "feat(frontend): 产品化沟通复盘报告"
```

## Task 7: Documentation And Verification

**Files:**
- Modify `README.md`
- Modify `docs/backend-api-contract.md`
- Modify `docs/v2-features.md`
- Modify `docs/phase3-status.md`

- [ ] **Step 1: Update docs**

Document:

- `DORM_HARMONY_SQLITE_PATH`
- `backend/.runtime/dorm_harmony.sqlite3`
- event archive SQLite
- LangGraph SQLite conversation memory
- review history endpoints
- stream frontend integration
- review export/history/dialogue-modal/practice-again features
- local Demo limitations

- [ ] **Step 2: Run full backend verification**

Run:

```bash
cd backend && pytest -q
```

Expected: PASS.

- [ ] **Step 3: Run full frontend verification**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS.

- [ ] **Step 4: Run focused frontend static verifiers**

Run:

```bash
cd frontend && npm run verify:v2
```

Expected: PASS or update the script if it contains assertions that contradict implemented V3 behavior.

- [ ] **Step 5: Add or update focused static verification**

Ensure at least one verifier checks:

- `SimulationView.vue` no longer imports `submitSimulationRequest`.
- `SimulationView.vue` or `useSimulationSession.ts` calls `submitSimulationStreamRequest`.
- `ReviewView.vue` contains the dialogue entry card/modal controls and no always-visible `完整对话摘要` section.

Run the relevant verifier after updating it.

- [ ] **Step 6: Confirm no Superpowers files are staged**

Run:

```bash
git status --short
```

Expected: no `.superpowers/` and no `docs/superpowers/` entries.

- [ ] **Step 7: Commit docs**

Run:

```bash
git add README.md docs/backend-api-contract.md docs/v2-features.md docs/phase3-status.md
git commit -m "docs: 更新 V3 持久化与复盘说明"
```

## Final Review Gate

- [ ] Dispatch final spec-compliance review against `docs/v3-persistence-review-design.md`.
- [ ] Dispatch final code-quality review over the full branch.
- [ ] Fix all findings and rerun relevant tests.
- [ ] Run:

```bash
git status --short
```

Expected: clean or only intentionally untracked local runtime files ignored by git.
