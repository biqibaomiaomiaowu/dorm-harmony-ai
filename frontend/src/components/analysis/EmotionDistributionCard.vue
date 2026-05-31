<script setup lang="ts">
interface EmotionDistributionViewItem {
  emotion: string
  label: string
  count: number
  percent: number
  tone: string
}

defineProps<{
  emotions: EmotionDistributionViewItem[]
  rangeLabel: string
}>()
</script>

<template>
  <article class="analysis-emotion-panel analysis-signals-panel pop-card pop-shadow page-pop-in">
    <h2>
      <span class="material-symbol" aria-hidden="true">bar_chart</span>
      情绪分布
    </h2>
    <div v-if="emotions.length > 0" class="analysis-emotion-bars">
      <div v-for="emotion in emotions" :key="emotion.emotion" class="analysis-emotion-item">
        <div class="analysis-emotion-row">
          <span>{{ emotion.label }}</span>
          <strong>{{ emotion.count }} 次 · {{ emotion.percent }}%</strong>
        </div>
        <div class="analysis-emotion-track card-border">
          <i
            :class="['analysis-emotion-fill', `analysis-emotion-fill-${emotion.tone}`]"
            :style="{ width: `${emotion.percent}%` }"
          ></i>
        </div>
      </div>
    </div>
    <p v-else class="analysis-source-empty">
      {{ rangeLabel }}暂无可汇总的情绪分布。
    </p>
  </article>
</template>

<style scoped>
.analysis-emotion-bars {
  display: grid;
  gap: 14px;
}

.analysis-emotion-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
  color: var(--ink);
  font-size: var(--font-label-bold);
  font-weight: 900;
}

.analysis-emotion-track {
  position: relative;
  overflow: hidden;
  height: 22px;
  border-radius: 999px;
  background: var(--surface-container);
}

.analysis-emotion-fill {
  position: absolute;
  inset: 0 auto 0 0;
  border-right: 2px solid var(--ink);
}

.analysis-emotion-fill-fresh {
  background: var(--primary);
}

.analysis-emotion-fill-warning {
  background: var(--tertiary);
}

.analysis-emotion-fill-danger {
  background: var(--secondary);
}

.analysis-source-empty {
  margin: 0;
  color: var(--ink-soft);
  font-size: var(--font-label-bold);
  font-weight: 800;
}
</style>
