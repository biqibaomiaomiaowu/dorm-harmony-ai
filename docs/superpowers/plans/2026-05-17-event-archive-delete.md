# Event Archive Deletion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent event archive deletion with a left-corner confirmation button, wind-away animation, and downstream pressure/AI refresh through existing analysis requests.

**Architecture:** Backend deletion is a small storage capability exposed through `DELETE /api/events/{event_id}` and protected by the existing JSON path lock. Frontend deletion is local-first after API success: keep the removed card in DOM for the exit animation, then filter it from the component list and clear the archive insight cache so the analysis page recomputes derived data on next load.

**Tech Stack:** FastAPI, Pydantic, pytest, Vue 3 `<script setup>`, Vite, TypeScript, CSS transitions/keyframes.

---

## File Structure

- Modify `backend/app/event_store.py`: add `delete(event_id: str) -> bool` to both stores.
- Modify `backend/app/main.py`: allow CORS `DELETE` and add `DELETE /api/events/{event_id}`.
- Modify `backend/tests/test_event_archive.py`: add store deletion tests.
- Modify `backend/tests/test_api.py`: add API deletion, analysis recomputation, insight empty-state, and CORS preflight tests.
- Modify `frontend/src/data/eventArchive.ts`: export `ARCHIVE_INSIGHT_CACHE_KEY`, add `deleteEventRecord()`.
- Modify `frontend/src/views/AnalysisView.vue`: import shared cache key instead of a local duplicate.
- Modify `frontend/src/views/EventArchiveView.vue`: add delete state, confirmation flow, API call, cache clearing, animation completion handling, page correction.
- Modify `frontend/src/styles/main.css`: style the folded delete corner, confirmation/deleting/removing states, transition group movement, and mobile-safe animation.

## Task 1: Backend Store Deletion

**Files:**
- Modify: `backend/tests/test_event_archive.py`
- Modify: `backend/app/event_store.py`

- [ ] **Step 1: Write failing store deletion tests**

Append these tests after `test_json_event_store_persists_models_sorted_and_cleans_temporary_files` in `backend/tests/test_event_archive.py`:

```python
def test_in_memory_event_store_deletes_existing_event():
    store = InMemoryEventStore()
    saved_event = store.add(EventRecordCreate(
        event_date="2026-05-15",
        event_type="noise",
        severity=4,
        frequency="weekly_multiple",
        emotion="anxious",
        has_communicated=False,
        has_conflict=True,
        description="舍友晚上打游戏声音很大，影响睡眠。",
    ))

    assert store.delete(saved_event.id) is True
    assert store.list() == []


def test_in_memory_event_store_returns_false_for_missing_event():
    store = InMemoryEventStore()

    assert store.delete("missing-event") is False


def test_json_event_store_deletes_event_and_persists_remaining_records(tmp_path):
    store_path = tmp_path / "events.json"
    store = JsonEventStore(store_path)
    first_event = store.add(EventRecordCreate(
        event_date="2026-05-15",
        event_type="noise",
        severity=4,
        frequency="weekly_multiple",
        emotion="anxious",
        has_communicated=False,
        has_conflict=True,
        description="舍友晚上打游戏声音很大，影响睡眠。",
    ))
    remaining_event = store.add(EventRecordCreate(
        event_date="2026-05-14",
        event_type="hygiene",
        severity=2,
        frequency="occasional",
        emotion="helpless",
        has_communicated=True,
        has_conflict=False,
        description="公共区域偶尔没人整理，但已经协商过一次。",
    ))

    assert store.delete(first_event.id) is True

    restored_events = JsonEventStore(store_path).list()
    assert [event.id for event in restored_events] == [remaining_event.id]
    assert not list(tmp_path.glob("*.tmp"))


def test_json_event_store_deletes_last_event_to_empty_archive(tmp_path):
    store_path = tmp_path / "events.json"
    store = JsonEventStore(store_path)
    saved_event = store.add(EventRecordCreate(
        event_date="2026-05-15",
        event_type="noise",
        severity=4,
        frequency="weekly_multiple",
        emotion="anxious",
        has_communicated=False,
        has_conflict=True,
        description="舍友晚上打游戏声音很大，影响睡眠。",
    ))

    assert store.delete(saved_event.id) is True
    assert JsonEventStore(store_path).list() == []


def test_json_event_store_returns_false_for_missing_event(tmp_path):
    store = JsonEventStore(tmp_path / "events.json")

    assert store.delete("missing-event") is False
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
(cd backend && pytest tests/test_event_archive.py -q)
```

Expected: FAIL with `AttributeError` because `InMemoryEventStore` and `JsonEventStore` do not have `delete`.

- [ ] **Step 3: Implement minimal store deletion**

In `backend/app/event_store.py`, add this method to `InMemoryEventStore` after `list()`:

```python
    def delete(self, event_id: str) -> bool:
        """删除指定 id 的内存事件记录，返回是否实际删除。"""
        original_count = len(self._events)
        self._events = [
            event for event in self._events if event.id != event_id
        ]
        return len(self._events) != original_count
```

Add this method to `JsonEventStore` after `list()`:

```python
    def delete(self, event_id: str) -> bool:
        """读取现有档案、删除指定事件，并原子写回 JSON 文件。"""
        with self._lock:
            events = self._load_events()
            remaining_events = [
                event for event in events if event.id != event_id
            ]
            if len(remaining_events) == len(events):
                return False

            self._write_events(remaining_events)
            return True
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
(cd backend && pytest tests/test_event_archive.py -q)
```

Expected: PASS.

## Task 2: Backend Delete API

**Files:**
- Modify: `backend/tests/test_api.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing API tests**

Append these tests after `test_event_analysis_endpoint_handles_empty_archive` in `backend/tests/test_api.py`:

```python
def test_delete_event_record_removes_event_from_archive():
    event_store = InMemoryEventStore()
    app.dependency_overrides[get_event_store] = lambda: event_store

    create_response = client.post(
        "/api/events",
        json={
            "event_date": date.today().isoformat(),
            "event_type": "noise",
            "severity": 4,
            "frequency": "weekly_multiple",
            "emotion": "anxious",
            "has_communicated": False,
            "has_conflict": True,
            "description": "舍友晚上打游戏声音很大，影响睡眠。",
        },
    )
    event_id = create_response.json()["id"]

    delete_response = client.delete(f"/api/events/{event_id}")
    list_response = client.get("/api/events")

    assert create_response.status_code == 200
    assert delete_response.status_code == 204
    assert list_response.status_code == 200
    assert list_response.json() == {"events": []}


def test_delete_event_record_returns_404_for_missing_event():
    event_store = InMemoryEventStore()
    app.dependency_overrides[get_event_store] = lambda: event_store

    response = client.delete("/api/events/missing-event")

    assert response.status_code == 404
    assert response.json()["detail"] == "事件档案不存在或已被删除。"


def test_event_analysis_recomputes_after_event_deletion():
    event_store = InMemoryEventStore()
    app.dependency_overrides[get_event_store] = lambda: event_store
    today = date.today().isoformat()

    first_response = client.post(
        "/api/events",
        json={
            "event_date": today,
            "event_type": "noise",
            "severity": 4,
            "frequency": "weekly_multiple",
            "emotion": "anxious",
            "has_communicated": False,
            "has_conflict": True,
            "description": "舍友晚上打游戏声音很大，影响睡眠。",
        },
    )
    second_response = client.post(
        "/api/events",
        json={
            "event_date": today,
            "event_type": "hygiene",
            "severity": 2,
            "frequency": "occasional",
            "emotion": "helpless",
            "has_communicated": True,
            "has_conflict": False,
            "description": "公共区域偶尔没人整理，但已经协商过一次。",
        },
    )

    delete_response = client.delete(f"/api/events/{first_response.json()['id']}")
    analysis_response = client.get("/api/events/analysis")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert delete_response.status_code == 204
    assert analysis_response.status_code == 200
    body = analysis_response.json()
    assert body["event_count"] == 1
    assert body["pressure_score"] == second_response.json()["single_analysis"]["pressure_score"]
    assert body["main_sources"] == ["卫生冲突"]


def test_deleting_last_event_resets_analysis_and_blocks_archive_insight():
    event_store = InMemoryEventStore()
    ai_service = CapturingArchiveInsightService()
    app.dependency_overrides[get_event_store] = lambda: event_store
    app.dependency_overrides[get_ai_service] = lambda: ai_service

    create_response = create_noise_event_for_archive()
    delete_response = client.delete(f"/api/events/{create_response.json()['id']}")
    analysis_response = client.get("/api/events/analysis")
    insight_response = client.post("/api/events/insight")

    assert create_response.status_code == 200
    assert delete_response.status_code == 204
    assert analysis_response.status_code == 200
    assert analysis_response.json()["pressure_score"] == 0
    assert analysis_response.json()["event_count"] == 0
    assert insight_response.status_code == 400
    assert ai_service.archive_insight_called is False


def test_cors_preflight_allows_delete_for_local_vite_frontend():
    response = client.options(
        "/api/events/some-event",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "DELETE",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
(cd backend && pytest tests/test_api.py -q)
```

Expected: FAIL with `405 Method Not Allowed` for `DELETE`, and CORS delete preflight not allowed.

- [ ] **Step 3: Implement minimal API**

In `backend/app/main.py`, change CORS methods:

```python
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
```

Add this route after `list_event_records()`:

```python
@app.delete("/api/events/{event_id}", status_code=204)
def delete_event_record(
    event_id: str,
    event_store: JsonEventStore = Depends(get_event_store),
) -> None:
    """删除一条事件档案；派生压力和 AI 见解由前端重新请求。"""
    if not event_store.delete(event_id):
        raise HTTPException(
            status_code=404,
            detail="事件档案不存在或已被删除。",
        )
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
(cd backend && pytest tests/test_event_archive.py tests/test_api.py -q)
```

Expected: PASS.

## Task 3: Frontend API and Cache Key

**Files:**
- Modify: `frontend/src/data/eventArchive.ts`
- Modify: `frontend/src/views/AnalysisView.vue`

- [ ] **Step 1: Add shared cache key and delete API helper**

In `frontend/src/data/eventArchive.ts`, add near the type exports:

```ts
export const ARCHIVE_INSIGHT_CACHE_KEY = 'dorm-harmony:archive-insight-cache:v1'
```

Add this function after `fetchEventArchive()`:

```ts
export async function deleteEventRecord(id: string): Promise<void> {
  const response = await fetch(`/api/events/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })

  await assertOk(response, '事件删除失败')
}
```

- [ ] **Step 2: Reuse the shared cache key in analysis**

In `frontend/src/views/AnalysisView.vue`, include `ARCHIVE_INSIGHT_CACHE_KEY` in the import from `@/data/eventArchive`:

```ts
  ARCHIVE_INSIGHT_CACHE_KEY,
```

Then remove the local line:

```ts
const ARCHIVE_INSIGHT_CACHE_KEY = 'dorm-harmony:archive-insight-cache:v1'
```

- [ ] **Step 3: Verify TypeScript**

Run:

```bash
(cd frontend && npm run type-check)
```

Expected: PASS.

## Task 4: Frontend Delete Interaction

**Files:**
- Modify: `frontend/src/views/EventArchiveView.vue`
- Modify: `frontend/src/styles/main.css`

- [ ] **Step 1: Import delete helper and cache key**

In `frontend/src/views/EventArchiveView.vue`, update the import from `@/data/eventArchive`:

```ts
  ARCHIVE_INSIGHT_CACHE_KEY,
  deleteEventRecord,
```

- [ ] **Step 2: Add component state and helpers**

Add after `const currentPage = ref(1)`:

```ts
const confirmingDeleteId = ref('')
const deletingEventIds = ref<Set<string>>(new Set())
const removingEventIds = ref<Set<string>>(new Set())
const deleteError = ref('')
```

Add helper functions after `stickerTone()`:

```ts
function isDeleting(eventId: string) {
  return deletingEventIds.value.has(eventId)
}

function isRemoving(eventId: string) {
  return removingEventIds.value.has(eventId)
}

function cloneIdSet(source: Set<string>, eventId: string, action: 'add' | 'delete') {
  const next = new Set(source)
  next[action](eventId)
  return next
}

function clearArchiveInsightCache() {
  try {
    localStorage.removeItem(ARCHIVE_INSIGHT_CACHE_KEY)
  } catch {
    // Restricted browser sessions may block localStorage; analysis still reloads live data.
  }
}

function removeEventAfterAnimation(eventId: string) {
  events.value = events.value.filter((event) => event.id !== eventId)
  removingEventIds.value = cloneIdSet(removingEventIds.value, eventId, 'delete')
  confirmingDeleteId.value = ''
  currentPage.value = Math.min(currentPage.value, pageCount.value)
}

async function requestDeleteEvent(event: EventRecord) {
  if (isDeleting(event.id) || isRemoving(event.id)) {
    return
  }

  if (confirmingDeleteId.value !== event.id) {
    confirmingDeleteId.value = event.id
    deleteError.value = ''
    return
  }

  deletingEventIds.value = cloneIdSet(deletingEventIds.value, event.id, 'add')
  deleteError.value = ''

  try {
    await deleteEventRecord(event.id)
    clearArchiveInsightCache()
    removingEventIds.value = cloneIdSet(removingEventIds.value, event.id, 'add')
  } catch (error) {
    deleteError.value = error instanceof Error ? error.message : '事件删除失败，请稍后重试'
  } finally {
    deletingEventIds.value = cloneIdSet(deletingEventIds.value, event.id, 'delete')
  }
}

function handleStickerAnimationEnd(event: AnimationEvent, eventId: string) {
  if (event.animationName === 'archive-sticker-wind-away') {
    removeEventAfterAnimation(eventId)
  }
}
```

- [ ] **Step 3: Add transition group and delete button markup**

Replace:

```vue
      <div v-else class="event-sticker-grid">
```

with:

```vue
      <TransitionGroup v-else name="archive-sticker" tag="div" class="event-sticker-grid">
```

Replace the closing `</div>` for that grid with `</TransitionGroup>`.

Inside each `<article>`, add `archive-event-card-removing` when needed and the animation end handler:

```vue
          :class="[
            'archive-event-card',
            'event-sticker-card',
            stickerTone(pageStartIndex + index),
            {
              'archive-event-card-confirming': confirmingDeleteId === event.id,
              'archive-event-card-deleting': isDeleting(event.id),
              'archive-event-card-removing': isRemoving(event.id),
            },
          ]"
          @animationend="handleStickerAnimationEnd($event, event.id)"
```

Add this button as the first child inside the article:

```vue
          <button
            class="archive-delete-corner pop-shadow"
            type="button"
            :disabled="isDeleting(event.id) || isRemoving(event.id)"
            :aria-label="confirmingDeleteId === event.id ? `确认删除 ${eventTitle(event)}` : `删除 ${eventTitle(event)}`"
            @click="requestDeleteEvent(event)"
          >
            <span class="material-symbol" aria-hidden="true">
              {{ isDeleting(event.id) ? 'hourglass_top' : confirmingDeleteId === event.id ? 'check' : 'close' }}
            </span>
            <span class="archive-delete-text">
              {{ confirmingDeleteId === event.id ? '确认' : '删除' }}
            </span>
          </button>
```

Show delete errors by changing:

```vue
      <p v-if="loadError" class="error-text archive-error">{{ loadError }}</p>
```

to:

```vue
      <p v-if="loadError || deleteError" class="error-text archive-error">
        {{ loadError || deleteError }}
      </p>
```

- [ ] **Step 4: Add CSS for folded corner and animation**

In `frontend/src/styles/main.css`, add after `.archive-event-card::after`:

```css
.archive-delete-corner {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 4;
  display: grid;
  width: 58px;
  height: 58px;
  place-items: start;
  border: 0;
  border-right: 2px solid var(--ink);
  border-bottom: 2px solid var(--ink);
  border-radius: 16px 0 16px 0;
  background: var(--error-soft);
  color: var(--error);
  padding: 8px 0 0 8px;
}

.archive-delete-corner .material-symbol {
  font-size: 1.1rem;
  font-weight: 700;
}

.archive-delete-text {
  position: absolute;
  left: 8px;
  bottom: 7px;
  font-size: 0.62rem;
  font-weight: 900;
  line-height: 1;
}

.archive-delete-corner:hover:not(:disabled),
.archive-event-card-confirming .archive-delete-corner {
  background: var(--tertiary);
  color: var(--ink);
  transform: translate(-1px, -1px) rotate(-3deg);
}

.archive-delete-corner:disabled {
  cursor: wait;
  opacity: 0.76;
}

.archive-event-card .sticker-date {
  margin-left: 40px;
}

.archive-event-card-removing {
  pointer-events: none;
  animation: archive-sticker-wind-away 680ms cubic-bezier(0.34, 0.02, 0.2, 1) both;
}

.archive-sticker-move {
  transition: transform 360ms ease;
}

@keyframes archive-sticker-wind-away {
  0% {
    opacity: 1;
    transform: rotate(var(--sticker-rotate, 0deg)) translate(0, 0);
  }
  45% {
    opacity: 0.92;
    transform: rotate(calc(var(--sticker-rotate, 0deg) + 7deg)) translate(28px, -18px);
  }
  100% {
    opacity: 0;
    transform: rotate(calc(var(--sticker-rotate, 0deg) + 20deg)) translate(220px, -82px);
  }
}
```

In the mobile media query where `.archive-event-card { min-height: auto; transform: none; }` already exists, add:

```css
  .archive-event-card .sticker-date {
    margin-left: 44px;
  }

  @keyframes archive-sticker-wind-away {
    0% {
      opacity: 1;
      transform: translate(0, 0);
    }
    100% {
      opacity: 0;
      transform: translate(96px, -42px) rotate(12deg);
    }
  }
```

- [ ] **Step 5: Verify frontend build**

Run:

```bash
(cd frontend && npm run build)
```

Expected: PASS.

## Task 5: Full Verification and Review

**Files:**
- No new production files unless fixing review findings.

- [ ] **Step 1: Run backend tests**

Run:

```bash
(cd backend && pytest -q)
```

Expected: PASS.

- [ ] **Step 2: Run frontend checks**

Run:

```bash
(cd frontend && npm run build)
(cd frontend && npm run lint)
```

Expected: PASS. If lint changes formatting, review and include only relevant edits.

- [ ] **Step 3: Start local dev services for browser verification**

Use two terminals or background sessions:

```bash
cd backend && uvicorn app.main:app --reload
cd frontend && npm run dev -- --host 0.0.0.0
```

Expected: backend on `http://127.0.0.1:8000`, frontend on Vite's printed URL, usually `http://localhost:5173`.

- [ ] **Step 4: Manual browser verification**

In the archive page:

1. Create at least two events if the archive is empty.
2. Click one card's folded corner once; expected: button enters confirm state, no deletion.
3. Click the same folded corner again; expected: request runs, card flies toward top-right, remaining cards fill the grid.
4. Delete the last card on a page; expected: `currentPage` corrects and no empty page appears.
5. Delete the final archive event; expected: empty archive state appears.
6. Open pressure analysis; expected: empty archive state when no events, or recomputed pressure and AI insight when events remain.

- [ ] **Step 5: Final review**

Inspect:

```bash
git diff -- backend/app/event_store.py backend/app/main.py backend/tests/test_event_archive.py backend/tests/test_api.py frontend/src/data/eventArchive.ts frontend/src/views/AnalysisView.vue frontend/src/views/EventArchiveView.vue frontend/src/styles/main.css
```

Check that:

- No unrelated files are modified.
- The delete endpoint returns no body.
- AI insight cache key is shared and cleared on successful deletion.
- Removing cards are not filtered before the wind-away animation ends.
- Page correction works after filtering the removed card.

- [ ] **Step 6: Commit implementation**

Use a Chinese subject:

```bash
git add backend/app/event_store.py backend/app/main.py backend/tests/test_event_archive.py backend/tests/test_api.py frontend/src/data/eventArchive.ts frontend/src/views/AnalysisView.vue frontend/src/views/EventArchiveView.vue frontend/src/styles/main.css
git commit -m "feat(archive): 新增事件档案删除功能"
```
