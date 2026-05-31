<script setup lang="ts">
import type { TrainingRecommendation } from '@/data/eventArchive'

defineProps<{
  recommendation: TrainingRecommendation | null
}>()

defineEmits<{
  start: []
}>()
</script>

<template>
  <article class="analysis-training-panel pop-card pop-shadow page-pop-in">
    <h2>
      <span class="material-symbol" aria-hidden="true">school</span>
      推荐场景训练
    </h2>
    <template v-if="recommendation">
      <div class="analysis-training-heading">
        <span>{{ recommendation.category_label }}</span>
        <h3>{{ recommendation.scenario_title }}</h3>
      </div>
      <dl class="analysis-training-meta">
        <div>
          <dt>训练目标</dt>
          <dd>{{ recommendation.target_label }}</dd>
        </div>
        <div>
          <dt>难度</dt>
          <dd>
            {{ recommendation.difficulty_label }}
            <small>{{ recommendation.difficulty_description }}</small>
          </dd>
        </div>
      </dl>
      <p>{{ recommendation.reason }}</p>
      <blockquote>
        {{ recommendation.opening_suggestion }}
      </blockquote>
      <p class="analysis-training-safety">
        {{ recommendation.safety_note }}
      </p>
      <button class="primary-action pop-shadow" type="button" @click="$emit('start')">
        开始推荐训练
        <span class="action-icon material-symbol" aria-hidden="true">arrow_forward</span>
      </button>
    </template>
    <div v-else class="analysis-training-empty">
      <p>当前周期暂未形成明确场景推荐。可以继续记录事件，或先选择通用演练。</p>
      <button class="secondary-action pop-shadow" type="button" @click="$emit('start')">
        选择通用演练
      </button>
    </div>
  </article>
</template>

<style scoped>
.analysis-training-panel {
  display: grid;
  align-content: start;
  gap: 16px;
  border: 2px solid var(--ink);
  border-radius: 12px;
  background: var(--surface);
  padding: 24px;
}

.analysis-training-panel h2 {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  font-size: var(--font-headline-md);
}

.analysis-training-panel h2 .material-symbol {
  display: inline-grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border: 2px solid var(--ink);
  border-radius: 10px;
  background: var(--tertiary);
  box-shadow: 2px 2px 0 0 var(--shadow-dark);
  color: var(--ink);
}

.analysis-training-panel p,
.analysis-training-empty p {
  margin: 0;
  color: var(--ink-soft);
  font-weight: 700;
  line-height: 1.6;
}

.analysis-training-meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.analysis-training-meta div {
  border: 2px solid var(--border);
  border-radius: 10px;
  background: var(--surface-container);
  padding: 10px;
}

.analysis-training-meta dt {
  color: var(--ink-soft);
  font-size: 0.82rem;
  font-weight: 900;
}

.analysis-training-meta dd {
  margin: 4px 0 0;
  color: var(--ink);
  font-weight: 900;
}

.analysis-training-meta small {
  display: block;
  margin-top: 4px;
  color: var(--ink-soft);
  font-size: 0.82rem;
  line-height: 1.45;
}

.analysis-training-heading span {
  color: var(--ink-soft);
  font-size: 0.82rem;
  font-weight: 900;
}

.analysis-training-heading h3 {
  margin: 4px 0 0;
  color: var(--ink);
  font-size: 1.35rem;
}

.analysis-training-panel blockquote {
  margin: 0;
  border-left: 6px solid var(--secondary);
  background: #ffffff;
  padding: 12px 14px;
  color: var(--ink);
  font-weight: 800;
  line-height: 1.6;
}

.analysis-training-safety {
  border: 2px dashed var(--ink);
  border-radius: 12px;
  background: var(--surface-container);
  padding: 12px;
}

.analysis-training-panel .primary-action,
.analysis-training-panel .secondary-action {
  width: 100%;
  justify-content: center;
}

.analysis-training-empty {
  display: grid;
  gap: 16px;
}

@media (max-width: 768px) {
  .analysis-training-meta {
    grid-template-columns: 1fr;
  }

  .analysis-training-panel {
    padding: 20px;
  }
}
</style>
