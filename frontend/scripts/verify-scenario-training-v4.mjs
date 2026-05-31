import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

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

async function importTypeScriptModule(relativePath) {
  const source = read(relativePath)
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText
  const encoded = Buffer.from(output).toString('base64')

  return import(`data:text/javascript;base64,${encoded}`)
}

function verifyPolicyShape(policy) {
  const expectedCounts = {
    beginner: 1,
    intermediate: 2,
    advanced: 3,
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
  assert.ok(
    challengeRoommates.length >= 4 && challengeRoommates.length <= 5,
    'challenge should create 4-5 roommates',
  )
  assert.notDeepEqual(
    challengeRoommates.map((roommate) => roommate.id),
    ['roommate_a', 'roommate_b', 'roommate_c'],
    'challenge should not reuse the default A/B/C three-roommate set',
  )
  assert.ok(
    challengeRoommates.some((roommate) => roommate.personality_tag.includes('质疑')) &&
      challengeRoommates.some((roommate) => roommate.personality_tag.includes('回避')) &&
      challengeRoommates.some((roommate) => roommate.personality_tag.includes('推卸')) &&
      challengeRoommates.some((roommate) => roommate.personality_tag.includes('调停')),
    'challenge should include questioning, avoidant, deflecting, and mediating roles',
  )
}

function verifyReplyPolicy(policy) {
  const replyPolicies = ['beginner', 'intermediate', 'advanced', 'challenge'].map(
    (difficultyId) => [difficultyId, policy.getScenarioReplyPolicy(difficultyId)],
  )

  for (const [difficultyId, replyPolicy] of replyPolicies) {
    assert.equal(typeof replyPolicy.min, 'number', `${difficultyId} reply min should exist`)
    assert.equal(typeof replyPolicy.max, 'number', `${difficultyId} reply max should exist`)
    assert.ok(replyPolicy.min <= replyPolicy.max, `${difficultyId} reply range should be valid`)
  }

  const uniqueRanges = new Set(
    replyPolicies.map(([, replyPolicy]) => `${replyPolicy.min}-${replyPolicy.max}`),
  )
  assert.equal(uniqueRanges.size, 4, 'reply ranges should differ across all four difficulties')
}

async function main() {
  const policy = await importTypeScriptModule('src/data/scenarioDifficultyPolicy.ts')
  verifyPolicyShape(policy)
  verifyReplyPolicy(policy)

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
