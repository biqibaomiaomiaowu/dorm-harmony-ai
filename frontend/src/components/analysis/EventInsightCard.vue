<script setup lang="ts">
import type { EventInsightSummary } from '@/data/eventArchive'

defineProps<{
  insight: EventInsightSummary | null
  rangeLabel: string
}>()
</script>

<template>
  <article class="analysis-event-insight-panel pop-card pop-shadow page-pop-in">
    <h2>
      <span class="material-symbol" aria-hidden="true">fact_check</span>
      情绪与事件洞察
    </h2>
    <template v-if="insight">
      <p class="analysis-event-summary">{{ insight.summary }}</p>
      <dl class="analysis-event-metrics">
        <div>
          <dt>统计周期</dt>
          <dd>{{ insight.period_days }} 天</dd>
        </div>
        <div>
          <dt>周期事件</dt>
          <dd>{{ insight.period_event_count }} 条</dd>
        </div>
        <div>
          <dt>已沟通</dt>
          <dd>{{ insight.communicated_count }} 条</dd>
        </div>
        <div>
          <dt>未沟通</dt>
          <dd>{{ insight.uncommunicated_count }} 条</dd>
        </div>
        <div>
          <dt>直接冲突</dt>
          <dd>{{ insight.conflict_count }} 条</dd>
        </div>
      </dl>
      <div class="analysis-insight-tags">
        <div>
          <span>主要情绪</span>
          <p v-if="insight.top_emotions.length > 0">
            {{ insight.top_emotions.join('、') }}
          </p>
          <p v-else>暂无明显集中项</p>
        </div>
        <div>
          <span>主要事件类型</span>
          <p v-if="insight.top_event_types.length > 0">
            {{ insight.top_event_types.join('、') }}
          </p>
          <p v-else>暂无明显集中项</p>
        </div>
      </div>
    </template>
    <p v-else class="analysis-neutral-empty">
      {{ rangeLabel }}暂无情绪与事件洞察。继续记录事件后，这里会展示客观统计摘要。
    </p>
  </article>
</template>

<style scoped>
.analysis-event-insight-panel {
  display: grid;
  align-content: start;
  gap: 16px;
  border: 2px solid var(--ink);
  border-radius: 12px;
  background: var(--surface);
  padding: 24px;
}

.analysis-event-insight-panel h2 {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  font-size: var(--font-headline-md);
}

.analysis-event-insight-panel h2 .material-symbol {
  display: inline-grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border: 2px solid var(--ink);
  border-radius: 10px;
  background: var(--primary-container);
  box-shadow: 2px 2px 0 0 var(--shadow-dark);
  color: #ffffff;
}

.analysis-event-summary,
.analysis-neutral-empty {
  margin: 0;
  color: var(--ink-soft);
  font-weight: 700;
  line-height: 1.6;
}

.analysis-event-summary {
  border: 2px solid var(--ink);
  border-radius: 12px;
  background: #ffffff;
  padding: 12px;
}

.analysis-event-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.analysis-event-metrics div {
  border: 2px solid var(--border);
  border-radius: 10px;
  background: var(--surface-container);
  padding: 10px;
}

.analysis-event-metrics dt {
  color: var(--ink-soft);
  font-size: 0.82rem;
  font-weight: 900;
}

.analysis-event-metrics dd {
  margin: 4px 0 0;
  color: var(--ink);
  font-weight: 900;
}

.analysis-insight-tags {
  display: grid;
  gap: 10px;
}

.analysis-insight-tags div {
  border-left: 6px solid var(--primary);
  background: #ffffff;
  padding: 10px 12px;
}

.analysis-insight-tags div:nth-child(2) {
  border-left-color: var(--secondary);
}

.analysis-insight-tags span {
  color: var(--ink-soft);
  font-size: 0.82rem;
  font-weight: 900;
}

.analysis-insight-tags p {
  margin: 4px 0 0;
}

@media (max-width: 768px) {
  .analysis-event-insight-panel,
  .analysis-event-metrics {
    grid-template-columns: 1fr;
  }

  .analysis-event-insight-panel {
    padding: 20px;
  }
}
</style>
