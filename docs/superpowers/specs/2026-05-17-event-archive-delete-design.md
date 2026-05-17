# 事件档案删除功能设计

## 背景

“事件档案”页面目前只支持查看后端返回的事件贴纸墙。事件持久化由后端本地 JSON store 承担，`GET /api/events/analysis` 会基于当前档案即时重算总压力，`POST /api/events/insight` 会基于当前档案和总压力即时生成 AI 心晴见解。当前没有删除接口，也没有前端删除入口。

本次功能要让用户能从事件档案页删除单条档案。删除后，档案列表、事件数量、近 30 天数量、最近记录日期都应反映删除后的数据；压力分析和 AI 心晴不在删除接口里同步生成，而是在用户进入压力分析页时重新请求。

## 用户体验

事件贴纸卡左上角增加折角删除按钮。按钮视觉采用已确认的 B 方案：左上角折角样式，贴合当前贴纸墙、粗描边、硬阴影和高饱和配色。折角不能遮挡主要内容；日期区域在需要时向右让出空间。

删除使用二次确认：

1. 用户第一次点击折角按钮，按钮进入确认态，文案或可访问标签表达“确认删除”。
2. 用户第二次点击同一按钮，才发起删除请求。
3. 如果用户点击其他卡片的删除按钮，新的卡片进入确认态，旧卡片退出确认态。
4. 删除请求进行中，按钮禁用，卡片保持在原位置。
5. 删除失败时，卡片恢复可操作状态，并在档案页展示错误提示。

删除成功后，目标卡片播放“被风吹走”的离场动画：向右上方平移、旋转并淡出。动画结束后才从本地 `events` 列表移除。剩余卡片按当前 grid 顺序补齐空位，并保留列表移动过渡，形成“顺次补齐”的观感。移动端应降低位移距离，避免产生横向滚动。

## 后端设计

新增接口：

```http
DELETE /api/events/{event_id}
```

响应规则：

- 删除成功返回 `204 No Content`。
- 找不到对应事件返回 `404`，错误信息说明事件不存在。
- 接口不返回删除后的档案、总压力分析或 AI 心晴见解。

`InMemoryEventStore` 和 `JsonEventStore` 增加 `delete(event_id: str) -> bool`：

- `True` 表示删除了存在的事件。
- `False` 表示没有找到该事件。
- `JsonEventStore.delete()` 必须复用现有路径级锁，在锁内加载事件、过滤目标 id，并使用现有原子写入逻辑写回 JSON。
- 删除最后一条事件后，JSON 文件应保存为空数组，后续 `list()` 返回空列表。

FastAPI CORS 配置要把 `DELETE` 加入允许方法，保持本地 Vite 前端可直接调用。

## 前端设计

`frontend/src/data/eventArchive.ts` 增加：

```ts
export async function deleteEventRecord(id: string): Promise<void>
```

该函数调用 `DELETE /api/events/${encodeURIComponent(id)}`，复用现有 `assertOk()` 错误处理。返回 `204` 或其他 2xx 都视为成功；非 2xx 抛出“事件删除失败”类错误。

`frontend/src/views/EventArchiveView.vue` 增加以下状态：

- `confirmingDeleteId`：当前处于确认态的事件 id。
- `deletingEventIds`：正在调用删除接口的事件 id 集合。
- `removingEventIds`：删除成功、正在播放离场动画的事件 id 集合。
- `deleteError`：删除失败时展示的错误消息。

删除成功后不立即重新拉取整个档案，而是先让目标卡片进入 `removingEventIds`。动画结束后从 `events.value` 过滤目标 id，并校正 `currentPage`，避免删除当前页最后一条后停在空页。若用户删除最后一条事件，页面进入现有空档案状态。

删除成功后前端清理 AI 心晴缓存 key：

```text
dorm-harmony:archive-insight-cache:v1
```

压力分析页保留现有逻辑：进入页面时重新请求 `/api/events/analysis`；如果 `event_count > 0`，再获取当前档案并按新的签名请求或读取 `/api/events/insight`；如果 `event_count === 0`，展示空档案状态，不调用 AI。

## 业务一致性

删除事件会影响以下业务数据：

- 档案页已记录事件数。
- 档案页近 30 天事件数。
- 档案页最近记录日期。
- 压力分析页总压力值、风险等级、主要压力来源、情绪关键词、趋势提示和建议。
- AI 心晴见解。

后端删除只改变事件档案的事实数据。压力和 AI 的更新由“重新请求当前档案派生结果”完成，避免删除动作被 AI 服务配置或模型可用性阻塞。

删除后旧 AI 心晴缓存必须失效，避免用户在分析页短暂看到已删除事件参与生成的旧见解。现有分析页事件签名已经包含事件 id 和主要字段，删除后签名会变化；显式清理缓存是额外保护。

## 错误处理

后端：

- 不存在的事件 id 返回 `404`。
- 存储文件格式异常沿用现有异常行为，不在本次功能中新增恢复逻辑。

前端：

- 删除失败不移除卡片，不播放风吹走动画。
- 删除失败展示页面级错误，允许用户重试。
- 删除中禁用对应按钮，避免重复提交。
- 删除动画结束前，卡片仍保留在 DOM 中，防止动画被本地列表过滤打断。

## 测试计划

后端测试：

- `InMemoryEventStore.delete()` 删除存在事件返回 `True`，事件从 `list()` 消失。
- `InMemoryEventStore.delete()` 删除不存在事件返回 `False`。
- `JsonEventStore.delete()` 删除后持久化到 JSON 文件，重新实例化后仍不返回已删除事件。
- `JsonEventStore.delete()` 删除最后一条后 `list()` 为空。
- `DELETE /api/events/{id}` 成功返回 `204`。
- `DELETE /api/events/{id}` 对不存在 id 返回 `404`。
- 删除后 `GET /api/events` 不包含目标事件。
- 删除后 `GET /api/events/analysis` 用剩余事件重算；删除最后一条后总压力回到 `pressure_score=0`。
- 删除最后一条后 `POST /api/events/insight` 返回现有空档案 `400`。
- CORS preflight 允许 `DELETE`。

前端验证：

- `npm run build` 通过类型检查和生产构建。
- 如 lint 可用，运行 `npm run lint`。
- 浏览器验证：折角按钮位置、二次确认、删除中禁用、失败提示、风吹走动画、分页最后一张删除后页码回退、删除最后一条后空状态展示。

## 非目标

- 不引入用户账号、鉴权或多用户事件归属校验。
- 不新增批量删除。
- 不新增撤销删除。
- 不让删除接口同步返回总压力或 AI 心晴见解。
- 不重构事件档案的数据存储方式。
