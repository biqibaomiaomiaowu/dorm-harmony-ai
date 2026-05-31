<template>
  <main class="page scenario-training-page">
    <section class="scenario-placeholder pop-card pop-shadow card-border">
      <p class="eyebrow pill-label">
        <span class="material-symbol" aria-hidden="true">school</span>
        场景训练
      </p>
      <h1>AI 沟通演练</h1>
      <p>
        场景训练模块正在准备中。你可以先返回 AI 沟通演练首页选择模式，或进入自定义演练继续使用现有沟通沙盒。
      </p>
      <div class="scenario-actions">
        <RouterLink class="secondary-action pop-shadow" :to="{ name: 'rehearsal' }">
          返回演练首页
        </RouterLink>
        <RouterLink class="primary-action pop-shadow" :to="{ name: 'custom-rehearsal' }">
          进入自定义演练
          <span class="action-icon material-symbol" aria-hidden="true">arrow_forward</span>
        </RouterLink>
      </div>
    </section>
  </main>
</template>

<style scoped>
.scenario-training-page {
  display: grid;
  place-items: start stretch;
}

.scenario-placeholder {
  display: grid;
  gap: 18px;
  padding: 28px;
}

.scenario-placeholder h1,
.scenario-placeholder p {
  margin: 0;
}

.scenario-placeholder p:not(.eyebrow) {
  max-width: 720px;
  color: var(--ink-soft);
  font-size: var(--font-body-lg);
  line-height: 1.65;
}

.scenario-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

@media (max-width: 560px) {
  .scenario-placeholder {
    padding: 20px;
  }

  .scenario-actions {
    flex-direction: column;
  }
}
</style>
