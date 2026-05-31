import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const failures = []
const moduleUrlCache = new Map()

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

async function moduleDataUrl(relativePath) {
  if (moduleUrlCache.has(relativePath)) {
    return moduleUrlCache.get(relativePath)
  }

  const source = read(relativePath)
  let output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText

  const aliasImports = [...output.matchAll(/from\s+(['"])(@\/data\/([^'"]+))\1/g)]
  for (const [, quote, specifier, dataPath] of aliasImports) {
    const dependencyUrl = await moduleDataUrl(`src/data/${dataPath}.ts`)
    output = output.replaceAll(`${quote}${specifier}${quote}`, `${quote}${dependencyUrl}${quote}`)
  }

  const encoded = Buffer.from(output).toString('base64')
  const url = `data:text/javascript;base64,${encoded}`
  moduleUrlCache.set(relativePath, url)

  return url
}

async function importTypeScriptModule(relativePath) {
  const url = await moduleDataUrl(relativePath)

  return import(url)
}

function verifyPolicyShape(policy) {
  const expectedCounts = {
    beginner: 1,
    intermediate: 2,
    advanced: 4,
    challenge: 5,
  }

  for (const [difficultyId, expectedCount] of Object.entries(expectedCounts)) {
    const roommates = policy.buildScenarioTrainingRoommates(difficultyId)
    assert.equal(
      roommates.length,
      expectedCount,
      `${difficultyId} should create ${expectedCount} roommate(s)`,
    )
  }

  const challengeRoommates = policy.buildScenarioTrainingRoommates('challenge')
  assert.notDeepEqual(
    challengeRoommates.map((roommate) => roommate.id),
    ['roommate_a', 'roommate_b', 'roommate_c'],
    'challenge should not reuse the default A/B/C three-roommate set',
  )
  assert.ok(
    !challengeRoommates.some((roommate) =>
      ['调停缓和型', '现实补充型'].includes(roommate.personality_tag),
    ),
    'challenge should not include mediating or pragmatic easing roles',
  )
  assert.ok(
    challengeRoommates.some((roommate) => roommate.personality_tag.includes('强势反驳')) &&
      challengeRoommates.some((roommate) => roommate.personality_tag.includes('阴阳怪气')) &&
      challengeRoommates.some((roommate) => roommate.personality_tag.includes('回避')) &&
      challengeRoommates.some((roommate) => roommate.personality_tag.includes('拉群站队')) &&
      challengeRoommates.some((roommate) => roommate.personality_tag.includes('责任转移')),
    'challenge should include harder resistance roles without easing roles',
  )

  assert.equal(
    typeof policy.summarizeScenarioRoommates,
    'function',
    'summarizeScenarioRoommates helper should exist',
  )
  assert.equal(
    typeof policy.getScenarioDifficultyPressureProfile,
    'function',
    'getScenarioDifficultyPressureProfile helper should exist',
  )

  const challengeContext = policy.buildScenarioDifficultyContext('challenge')
  for (const phrase of ['多人反问', '站队', '推诿', '冷处理', '转移责任']) {
    assert.ok(challengeContext.includes(phrase), `challenge context should include ${phrase}`)
  }
  for (const phrase of ['辱骂', '威胁', '羞辱', '歧视', '操控', '人格评价']) {
    assert.ok(challengeContext.includes(phrase), `challenge context should ban ${phrase}`)
  }
}

function verifyReplyPolicy(policy) {
  const expectedRanges = {
    beginner: { min: 1, max: 2 },
    intermediate: { min: 2, max: 4 },
    advanced: { min: 4, max: 7 },
    challenge: { min: 6, max: 10 },
  }
  const replyPolicies = Object.keys(expectedRanges).map((difficultyId) => [
    difficultyId,
    policy.getScenarioReplyPolicy(difficultyId),
  ])

  for (const [difficultyId, replyPolicy] of replyPolicies) {
    assert.equal(typeof replyPolicy.min, 'number', `${difficultyId} reply min should exist`)
    assert.equal(typeof replyPolicy.max, 'number', `${difficultyId} reply max should exist`)
    assert.ok(replyPolicy.min <= replyPolicy.max, `${difficultyId} reply range should be valid`)
    assert.deepEqual(replyPolicy, expectedRanges[difficultyId], `${difficultyId} reply range`)
  }

  const uniqueRanges = new Set(
    replyPolicies.map(([, replyPolicy]) => `${replyPolicy.min}-${replyPolicy.max}`),
  )
  assert.equal(uniqueRanges.size, 4, 'reply ranges should differ across all four difficulties')
}

function verifySourceMeta(catalog) {
  const sourceMeta = catalog.buildScenarioTrainingSourceMeta({
    category_id: 'noise',
    scenario_id: 'noise_game_night',
    target_id: 'respond_objection',
    difficulty_id: 'challenge',
  })

  assert.ok(sourceMeta, 'scenario source_meta should build for a valid selection')
  assert.equal(typeof sourceMeta.difficulty_description, 'string')
  assert.equal(typeof sourceMeta.roommate_summary, 'string')
  assert.deepEqual(sourceMeta.reply_chain_range, { min: 6, max: 10 })
  assert.equal(typeof sourceMeta.difficulty_pressure_profile, 'string')
  assert.ok(
    sourceMeta.difficulty_pressure_profile.includes('多人反问'),
    'challenge pressure profile should describe multi-person resistance',
  )
}

function verifyScenarioUiMeta(catalog, uiMeta) {
  assert.equal(
    typeof uiMeta.getTrainingScenarioUiMeta,
    'function',
    'getTrainingScenarioUiMeta helper should exist',
  )

  for (const scenario of catalog.trainingScenarios) {
    const meta = uiMeta.getTrainingScenarioUiMeta(scenario.id)
    assert.ok(meta, `${scenario.id} should have UI metadata`)
    assert.equal(meta.scenario_id, scenario.id, `${scenario.id} scenario id`)
    assert.equal(typeof meta.headline, 'string', `${scenario.id} headline`)
    assert.equal(typeof meta.resistance, 'string', `${scenario.id} resistance`)
    assert.equal(typeof meta.focus, 'string', `${scenario.id} focus`)
    assert.ok(Array.isArray(meta.suggested_target_ids), `${scenario.id} target suggestions`)
    assert.ok(Array.isArray(meta.suggested_difficulty_ids), `${scenario.id} difficulty suggestions`)
    assert.ok(Number.isInteger(meta.complexity), `${scenario.id} complexity should be integer`)
    assert.ok(meta.complexity >= 1 && meta.complexity <= 5, `${scenario.id} complexity`)
    assert.ok(Array.isArray(meta.tags) && meta.tags.length > 0, `${scenario.id} tags`)
  }
}

async function main() {
  const policy = await importTypeScriptModule('src/data/scenarioDifficultyPolicy.ts')
  const catalog = await importTypeScriptModule('src/data/trainingCatalog.ts')
  const uiMeta = await importTypeScriptModule('src/data/trainingScenarioMeta.ts')
  verifyPolicyShape(policy)
  verifyReplyPolicy(policy)
  verifySourceMeta(catalog)
  verifyScenarioUiMeta(catalog, uiMeta)

  requireIncludes('src/composables/useSimulationSession.ts', [
    'simulationContextMaxLength = 500',
    'compactSimulationContext',
    'buildBoundedSingleReplyContext',
    'context.length <= simulationContextMaxLength',
    'simulationContextMaxLength - requiredHints.length - contextSeparator.length',
    'return truncatePreservingEdges(context, simulationContextMaxLength)',
    'return buildBoundedSingleReplyContext(baseContext, isContinuation, replyCount)',
  ])
}

try {
  await main()
} catch (error) {
  failures.push(error instanceof Error ? error.message : String(error))
}

if (failures.length > 0) {
  console.error('Scenario training V4 verification failed:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('Scenario training V4 verification passed.')
