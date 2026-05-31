<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import CustomCursor from './components/CustomCursor.vue'
import { useGsapMotion } from './composables/useGsapMotion'

const passphraseHash = 'f292574cd8753d8ad48a2fc40cfcfe4eb38bcbd611e4d430de733c7425b35b20'
const passphraseStorageKey = 'dorm-harmony-passphrase-verified'
const isPassphraseVerified = ref(false)
const isPassphraseChecking = ref(false)
const passphraseInput = ref('')
const passphraseError = ref('')
const passphraseInputRef = ref<HTMLInputElement | null>(null)
const sha256InitialHashValues = [
  0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab,
  0x5be0cd19,
]
const sha256RoundConstants = [
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
  0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
  0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
  0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
  0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
  0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
  0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
  0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
  0xc67178f2,
]

const navItems = [
  { name: 'home', label: '首页', icon: 'dashboard', mobileIcon: 'dashboard' },
  { name: 'record', label: '事件记录', icon: 'edit_note', mobileIcon: 'edit_note' },
  { name: 'archive', label: '事件档案', icon: 'history', mobileIcon: 'history' },
  { name: 'analysis', label: '压力分析', icon: 'analytics', mobileIcon: 'analytics' },
  { name: 'rehearsal', label: 'AI 沟通演练', icon: 'forum', mobileIcon: 'forum' },
  { name: 'review', label: '沟通复盘', icon: 'assignment', mobileIcon: 'assignment' },
]

const brandAvatarSrc =
  'https://lh3.googleusercontent.com/aida-public/AB6AXuDoIeE3fuGST0i8AH2TVFnjVGh_ghmeHMgRw6uUv0F6XHs-tGfTxBIOxOxQ9caVd2NzLnFXtlExYdqzmzWd5bDU1m65ZFQH1vroL-ebUGb6tEbeJ4yl3p6alHBVf0b4XtMOtvzRdRPCQAlFENmTXT0sOQQ_bDMWNAO2d13Qkg81Bnv4wY6WsSXjTKLxhv5act4Ak_2Q0Sj7xQ1lkpf4Bu7GCRJrqmQ1UAJr6F_hmuC0ZPir2-Z1lCASlOr_EmvP01FgTRlACAuJzXo'

const appShellRef = ref<HTMLElement | null>(null)
const { withContext, animatePageIn } = useGsapMotion(() => appShellRef.value)
let hasAnimatedAppShell = false

onMounted(() => {
  isPassphraseVerified.value = readStoredPassphraseState()

  if (!isPassphraseVerified.value) {
    void nextTick(() => passphraseInputRef.value?.focus())
  }
})

watch(
  isPassphraseVerified,
  (verified) => {
    if (verified) {
      void animateUnlockedShell()
    }
  },
  { flush: 'post' },
)

async function animateUnlockedShell() {
  if (!isPassphraseVerified.value || hasAnimatedAppShell) {
    return
  }

  await nextTick()

  const shell = appShellRef.value
  if (!shell) {
    return
  }

  hasAnimatedAppShell = true
  withContext(() => {
    animatePageIn(
      shell.querySelectorAll<HTMLElement>(
        '.brand-lockup, .nav-pill, .sidebar-cta, .mobile-header, .mobile-nav',
      ),
    )
  })
}

function handlePassphraseSwitchAfterEnter() {
  if (isPassphraseVerified.value) {
    void animateUnlockedShell()
  }
}

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

function rightRotate(value: number, bits: number) {
  return (value >>> bits) | (value << (32 - bits))
}

function sha256Hex(value: string) {
  const bytes = Array.from(new TextEncoder().encode(value))
  const bitLength = bytes.length * 8
  bytes.push(0x80)

  while (bytes.length % 64 !== 56) {
    bytes.push(0)
  }

  const highBits = Math.floor(bitLength / 0x100000000)
  const lowBits = bitLength >>> 0
  bytes.push(
    (highBits >>> 24) & 0xff,
    (highBits >>> 16) & 0xff,
    (highBits >>> 8) & 0xff,
    highBits & 0xff,
    (lowBits >>> 24) & 0xff,
    (lowBits >>> 16) & 0xff,
    (lowBits >>> 8) & 0xff,
    lowBits & 0xff,
  )

  const hashValues = [...sha256InitialHashValues]
  const words = Array.from({ length: 64 }, () => 0)

  for (let chunkStart = 0; chunkStart < bytes.length; chunkStart += 64) {
    for (let index = 0; index < 16; index += 1) {
      const offset = chunkStart + index * 4
      words[index] =
        ((bytes[offset] ?? 0) << 24) |
        ((bytes[offset + 1] ?? 0) << 16) |
        ((bytes[offset + 2] ?? 0) << 8) |
        (bytes[offset + 3] ?? 0)
    }

    for (let index = 16; index < 64; index += 1) {
      const s0 =
        rightRotate(words[index - 15] ?? 0, 7) ^
        rightRotate(words[index - 15] ?? 0, 18) ^
        ((words[index - 15] ?? 0) >>> 3)
      const s1 =
        rightRotate(words[index - 2] ?? 0, 17) ^
        rightRotate(words[index - 2] ?? 0, 19) ^
        ((words[index - 2] ?? 0) >>> 10)
      words[index] =
        ((words[index - 16] ?? 0) + s0 + (words[index - 7] ?? 0) + s1) >>> 0
    }

    let [a, b, c, d, e, f, g, h] = hashValues

    for (let index = 0; index < 64; index += 1) {
      const s1 = rightRotate(e ?? 0, 6) ^ rightRotate(e ?? 0, 11) ^ rightRotate(e ?? 0, 25)
      const choice = ((e ?? 0) & (f ?? 0)) ^ (~(e ?? 0) & (g ?? 0))
      const temp1 =
        ((h ?? 0) + s1 + choice + (sha256RoundConstants[index] ?? 0) + (words[index] ?? 0)) >>>
        0
      const s0 = rightRotate(a ?? 0, 2) ^ rightRotate(a ?? 0, 13) ^ rightRotate(a ?? 0, 22)
      const majority = ((a ?? 0) & (b ?? 0)) ^ ((a ?? 0) & (c ?? 0)) ^ ((b ?? 0) & (c ?? 0))
      const temp2 = (s0 + majority) >>> 0

      h = g
      g = f
      f = e
      e = ((d ?? 0) + temp1) >>> 0
      d = c
      c = b
      b = a
      a = (temp1 + temp2) >>> 0
    }

    hashValues[0] = ((hashValues[0] ?? 0) + (a ?? 0)) >>> 0
    hashValues[1] = ((hashValues[1] ?? 0) + (b ?? 0)) >>> 0
    hashValues[2] = ((hashValues[2] ?? 0) + (c ?? 0)) >>> 0
    hashValues[3] = ((hashValues[3] ?? 0) + (d ?? 0)) >>> 0
    hashValues[4] = ((hashValues[4] ?? 0) + (e ?? 0)) >>> 0
    hashValues[5] = ((hashValues[5] ?? 0) + (f ?? 0)) >>> 0
    hashValues[6] = ((hashValues[6] ?? 0) + (g ?? 0)) >>> 0
    hashValues[7] = ((hashValues[7] ?? 0) + (h ?? 0)) >>> 0
  }

  return hashValues
    .map((word) => word.toString(16).padStart(8, '0'))
    .join('')
}

function hashPassphrase(value: string) {
  return sha256Hex(value)
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
    const candidateHash = hashPassphrase(passphraseInput.value.trim())

    if (candidateHash !== passphraseHash) {
      passphraseError.value = '密语不对，请再试一次'
      return
    }

    savePassphraseState()
    isPassphraseVerified.value = true
    passphraseInput.value = ''
  } catch {
    passphraseError.value = '验证失败，请刷新后再试'
  } finally {
    isPassphraseChecking.value = false
  }
}
</script>

<template>
  <Transition name="passphrase-switch" mode="out-in" @after-enter="handlePassphraseSwitchAfterEnter">
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

    <div v-else ref="appShellRef" key="app" class="app-layout dot-grid">
      <CustomCursor />

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

        <RouterView v-slot="{ Component, route }">
          <Transition name="route-page" mode="out-in">
            <component :is="Component" :key="route.fullPath" />
          </Transition>
        </RouterView>
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
