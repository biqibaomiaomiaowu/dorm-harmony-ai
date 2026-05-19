<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { RouterLink, RouterView } from 'vue-router'

const passphraseHash = 'f292574cd8753d8ad48a2fc40cfcfe4eb38bcbd611e4d430de733c7425b35b20'
const passphraseStorageKey = 'dorm-harmony-passphrase-verified'
const isPassphraseVerified = ref(false)
const isPassphraseChecking = ref(false)
const passphraseInput = ref('')
const passphraseError = ref('')
const passphraseInputRef = ref<HTMLInputElement | null>(null)

const navItems = [
  { name: 'home', label: '首页', icon: 'dashboard', mobileIcon: 'dashboard' },
  { name: 'record', label: '事件记录', icon: 'edit_note', mobileIcon: 'edit_note' },
  { name: 'archive', label: '事件档案', icon: 'history', mobileIcon: 'history' },
  { name: 'analysis', label: '压力分析', icon: 'analytics', mobileIcon: 'analytics' },
  { name: 'simulate', label: '沟通模拟', icon: 'forum', mobileIcon: 'forum' },
  { name: 'review', label: '沟通复盘', icon: 'assignment', mobileIcon: 'assignment' },
]

const brandAvatarSrc =
  'https://lh3.googleusercontent.com/aida-public/AB6AXuDoIeE3fuGST0i8AH2TVFnjVGh_ghmeHMgRw6uUv0F6XHs-tGfTxBIOxOxQ9caVd2NzLnFXtlExYdqzmzWd5bDU1m65ZFQH1vroL-ebUGb6tEbeJ4yl3p6alHBVf0b4XtMOtvzRdRPCQAlFENmTXT0sOQQ_bDMWNAO2d13Qkg81Bnv4wY6WsSXjTKLxhv5act4Ak_2Q0Sj7xQ1lkpf4Bu7GCRJrqmQ1UAJr6F_hmuC0ZPir2-Z1lCASlOr_EmvP01FgTRlACAuJzXo'

onMounted(() => {
  isPassphraseVerified.value = readStoredPassphraseState()

  if (!isPassphraseVerified.value) {
    void nextTick(() => passphraseInputRef.value?.focus())
  }
})

function readStoredPassphraseState() {
  try {
    return localStorage.getItem(passphraseStorageKey) === 'true'
  } catch {
    return false
  }
}

function savePassphraseState() {
  try {
    localStorage.setItem(passphraseStorageKey, 'true')
    return true
  } catch {
    return false
  }
}

async function hashPassphrase(value: string) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value))

  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')
}

function clearPassphraseError() {
  passphraseError.value = ''
}

async function submitPassphrase() {
  if (isPassphraseChecking.value) {
    return
  }

  passphraseError.value = ''
  isPassphraseChecking.value = true

  try {
    const candidateHash = await hashPassphrase(passphraseInput.value.trim())

    if (candidateHash !== passphraseHash) {
      passphraseError.value = '密语不对，请再试一次'
      return
    }

    savePassphraseState()
    isPassphraseVerified.value = true
    passphraseInput.value = ''
  } catch {
    passphraseError.value = '当前浏览器不支持安全验证，请使用 HTTPS 或最新版浏览器'
  } finally {
    isPassphraseChecking.value = false
  }
}
</script>

<template>
  <Transition name="passphrase-switch" mode="out-in">
    <section
      v-if="!isPassphraseVerified"
      key="gate"
      class="passphrase-gate dot-grid"
      aria-labelledby="gate-title"
    >
      <form class="passphrase-panel card-border pop-shadow" @submit.prevent="submitPassphrase">
        <div class="passphrase-brand">
          <img :src="brandAvatarSrc" class="brand-mascot" alt="" aria-hidden="true" />
          <span>
            <strong>舍友心晴</strong>
            <small>Harmony Hub</small>
          </span>
        </div>

        <div class="passphrase-copy">
          <h1 id="gate-title">请输入密语</h1>
        </div>

        <div class="passphrase-form">
          <input
            id="passphrase-input"
            ref="passphraseInputRef"
            v-model="passphraseInput"
            class="passphrase-input"
            type="password"
            autocomplete="off"
            placeholder="输入密语"
            aria-label="密语"
            :aria-describedby="passphraseError ? 'passphrase-error' : undefined"
            :disabled="isPassphraseChecking"
            @input="clearPassphraseError"
          />
          <button
            class="passphrase-submit pop-shadow"
            type="submit"
            :disabled="isPassphraseChecking"
          >
            {{ isPassphraseChecking ? '验证中' : '进入' }}
          </button>
        </div>

        <Transition name="passphrase-error-fade">
          <p
            v-if="passphraseError"
            id="passphrase-error"
            class="passphrase-error"
            role="alert"
            aria-live="polite"
          >
            {{ passphraseError }}
          </p>
        </Transition>
      </form>
    </section>

    <div v-else key="app" class="app-layout dot-grid">
      <aside class="sidebar card-border pop-shadow" aria-label="桌面主导航">
        <RouterLink class="brand-lockup" :to="{ name: 'home' }" aria-label="回到舍友心晴首页">
          <img :src="brandAvatarSrc" class="brand-mascot" alt="" aria-hidden="true" />
          <span>
            <strong>舍友心晴</strong>
            <small>Harmony Hub</small>
          </span>
        </RouterLink>

        <nav class="sidebar-links">
          <RouterLink
            v-for="item in navItems"
            :key="item.name"
            class="nav-pill"
            :to="{ name: item.name }"
          >
            <span class="material-symbol" aria-hidden="true">{{ item.icon }}</span>
            <span>{{ item.label }}</span>
          </RouterLink>
        </nav>

        <RouterLink class="sidebar-cta" :to="{ name: 'record' }">
          <span class="material-symbol" aria-hidden="true">add</span>
          记录事件
        </RouterLink>
      </aside>

      <div class="content-shell">
        <header class="mobile-header card-border" aria-label="移动端页头">
          <RouterLink class="mobile-title" :to="{ name: 'home' }">舍友心晴</RouterLink>
          <div class="mobile-actions" aria-label="移动端快捷入口">
            <button class="mobile-badge material-symbol" type="button" aria-label="通知">
              notifications
            </button>
            <button class="mobile-badge material-symbol" type="button" aria-label="设置">
              settings
            </button>
            <img class="mobile-avatar" :src="brandAvatarSrc" alt="" aria-hidden="true" />
          </div>
        </header>

        <RouterView />
      </div>

      <nav class="mobile-nav card-border" aria-label="移动端主导航">
        <RouterLink v-for="item in navItems" :key="item.name" :to="{ name: item.name }">
          <span class="material-symbol" aria-hidden="true">{{ item.mobileIcon }}</span>
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
    </div>
  </Transition>
</template>
