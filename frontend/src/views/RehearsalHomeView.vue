<script setup lang="ts">
const rehearsalModes = [
  {
    title: '场景训练',
    icon: 'school',
    text: '从宿舍常见冲突切入，按固定场景练习表达、倾听和提出可执行请求。',
    action: '开始场景训练',
    routeName: 'scenario-training',
  },
  {
    title: '自定义演练',
    icon: 'tune',
    text: '沿用多角色沟通沙盒，自选场景、舍友设定和表达内容，先在安全环境里试说一遍。',
    action: '进入自定义演练',
    routeName: 'custom-rehearsal',
  },
]
</script>

<template>
  <main class="page rehearsal-page">
    <section class="rehearsal-hero pop-card pop-shadow card-border">
      <p class="eyebrow pill-label">
        <span class="material-symbol" aria-hidden="true">forum</span>
        AI practice
      </p>
      <h1>AI 沟通演练</h1>
      <p class="rehearsal-intro">
        先选择训练方式：用场景训练熟悉常见宿舍沟通情境，或进入自定义演练，把你正在准备的开场白提前练习一遍。
      </p>
    </section>

    <section class="rehearsal-mode-grid" aria-label="演练模式">
      <article
        v-for="mode in rehearsalModes"
        :key="mode.title"
        class="rehearsal-mode-card pop-card pop-shadow card-border"
      >
        <span class="material-symbol rehearsal-mode-icon" aria-hidden="true">
          {{ mode.icon }}
        </span>
        <div>
          <h2>{{ mode.title }}</h2>
          <p>{{ mode.text }}</p>
        </div>
        <RouterLink class="primary-action pop-shadow" :to="{ name: mode.routeName }">
          {{ mode.action }}
          <span class="action-icon material-symbol" aria-hidden="true">arrow_forward</span>
        </RouterLink>
      </article>
    </section>

    <aside class="rehearsal-safety card-border pop-card">
      <span class="material-symbol" aria-hidden="true">verified_user</span>
      <p>
        演练不代表真实舍友想法，也不能替代辅导员、宿管、心理老师等现实支持。若出现严重冲突、暴力风险或持续心理压力，请优先联系可信任的现实支持资源。
      </p>
    </aside>
  </main>
</template>

<style scoped>
.rehearsal-page {
  display: grid;
  gap: 24px;
}

.rehearsal-hero {
  padding: 28px;
}

.rehearsal-hero h1 {
  margin-bottom: 12px;
}

.rehearsal-intro,
.rehearsal-mode-card p,
.rehearsal-safety p {
  color: var(--ink-soft);
  font-size: var(--font-body-lg);
  line-height: 1.65;
}

.rehearsal-mode-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.rehearsal-mode-card {
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: 20px;
  min-height: 320px;
  padding: 24px;
}

.rehearsal-mode-icon {
  display: inline-grid;
  place-items: center;
  width: 58px;
  height: 58px;
  border: 2px solid var(--ink);
  border-radius: 18px;
  background: var(--secondary-soft);
  box-shadow: 3px 3px 0 0 var(--shadow-dark);
  color: #85145a;
  font-size: 32px;
}

.rehearsal-mode-card:nth-child(2) .rehearsal-mode-icon {
  background: #fff2c2;
  color: #7d3d00;
}

.rehearsal-mode-card .primary-action {
  width: 100%;
  justify-content: center;
}

.rehearsal-safety {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 14px;
  align-items: start;
  padding: 20px;
}

.rehearsal-safety > .material-symbol {
  color: var(--primary);
  font-size: 28px;
}

.rehearsal-safety p {
  margin: 0;
}

@media (max-width: 760px) {
  .rehearsal-hero,
  .rehearsal-mode-card,
  .rehearsal-safety {
    padding: 20px;
  }

  .rehearsal-mode-grid {
    grid-template-columns: 1fr;
  }

  .rehearsal-mode-card {
    min-height: 0;
  }
}
</style>
