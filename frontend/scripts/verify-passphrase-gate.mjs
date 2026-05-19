import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const failures = []

function read(relativePath) {
  const absolutePath = join(root, relativePath)

  if (!existsSync(absolutePath)) {
    failures.push(`Missing file: ${relativePath}`)
    return ''
  }

  return readFileSync(absolutePath, 'utf8')
}

function requireIncludes(relativePath, phrases) {
  const content = read(relativePath)

  for (const phrase of phrases) {
    if (!content.includes(phrase)) {
      failures.push(`${relativePath} is missing "${phrase}"`)
    }
  }
}

function requireExcludes(relativePath, phrases) {
  const content = read(relativePath)

  for (const phrase of phrases) {
    if (content.includes(phrase)) {
      failures.push(`${relativePath} should not include "${phrase}"`)
    }
  }
}

function requireMatches(relativePath, checks) {
  const content = read(relativePath)

  for (const { label, pattern } of checks) {
    if (!pattern.test(content)) {
      failures.push(`${relativePath} should match ${label}`)
    }
  }
}

requireIncludes('package.json', ['"verify:passphrase": "node scripts/verify-passphrase-gate.mjs"'])

requireIncludes('src/App.vue', [
  "const passphraseHash = 'f292574cd8753d8ad48a2fc40cfcfe4eb38bcbd611e4d430de733c7425b35b20'",
  "const passphraseStorageKey = 'dorm-harmony-passphrase-verified'",
  'const isPassphraseVerified = ref(false)',
  'const isPassphraseChecking = ref(false)',
  'const passphraseInputRef = ref<HTMLInputElement | null>(null)',
  'function readStoredPassphraseState',
  'function savePassphraseState',
  'localStorage.getItem(passphraseStorageKey)',
  'localStorage.setItem(passphraseStorageKey,',
  'async function hashPassphrase',
  'function submitPassphrase',
  'function clearPassphraseError',
  "crypto.subtle.digest('SHA-256'",
  'candidateHash !== passphraseHash',
  'passphraseInput.value.trim()',
  '请输入密语',
  '验证中',
  '密语不对',
  ':aria-describedby="passphraseError ? \'passphrase-error\' : undefined"',
  '<Transition name="passphrase-switch" mode="out-in">',
  '<Transition name="passphrase-error-fade">',
  '@submit.prevent="submitPassphrase"',
  '@input="clearPassphraseError"',
  'v-if="!isPassphraseVerified"',
  'v-else',
  'passphrase-gate',
])

requireExcludes('src/App.vue', ['请输入谜语', '无敌小猪爱吃草', 'const secretPhrase'])

requireMatches('src/App.vue', [
  {
    label: 'stored passphrase state reads are guarded',
    pattern:
      /function readStoredPassphraseState\(\) \{[\s\S]*?try \{[\s\S]*?localStorage\.getItem\(passphraseStorageKey\)[\s\S]*?\} catch \{[\s\S]*?return false[\s\S]*?\}/,
  },
  {
    label: 'stored passphrase state writes are guarded',
    pattern:
      /function savePassphraseState\(\) \{[\s\S]*?try \{[\s\S]*?localStorage\.setItem\(passphraseStorageKey,\s*'true'\)[\s\S]*?return true[\s\S]*?\} catch \{[\s\S]*?return false[\s\S]*?\}/,
  },
  {
    label: 'passphrase submit compares trimmed input hash to the configured hash',
    pattern:
      /const candidateHash = await hashPassphrase\(passphraseInput\.value\.trim\(\)\)[\s\S]*?if \(candidateHash !== passphraseHash\) \{[\s\S]*?passphraseError\.value = '密语不对/,
  },
  {
    label: 'successful passphrase stores verified state before showing the app when possible',
    pattern: /savePassphraseState\(\)[\s\S]*?isPassphraseVerified\.value = true/,
  },
])

requireIncludes('src/styles/main.css', [
  'passphrase-gate',
  'passphrase-panel',
  'passphrase-form',
  'passphrase-input',
  'passphrase-error',
  'passphrase-switch-enter-active',
  'passphrase-switch-leave-active',
  'passphrase-error-fade-enter-active',
  'passphrase-panel',
  'animation: gate-panel-pop',
  '@keyframes gate-panel-pop',
])

if (failures.length > 0) {
  console.error(`Passphrase gate verification failed with ${failures.length} issue(s):`)

  for (const failure of failures) {
    console.error(`- ${failure}`)
  }

  process.exit(1)
}

console.log('Passphrase gate verification passed.')
