<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  LAST_EVENT_STORAGE_KEY,
  ANALYSIS_RESULT_STORAGE_KEY,
  emotionOptions,
  eventTypeOptions,
  frequencyOptions,
  sampleAnalyzeRequest,
  normalizeAnalyzeResponse,
} from '@/data/week1'
import {
  buildEventRecordCreate,
  createEventRecord,
  formatLocalDate,
  type EventRecordForm,
} from '@/data/eventArchive'

const router = useRouter()
const descriptionPlaceholder = `例：${sampleAnalyzeRequest.description}`

// v2 replaces the former submitAnalyzeRequest record flow with createEventRecord.
const form = reactive<EventRecordForm>({
  event_date: formatLocalDate(),
  ...sampleAnalyzeRequest,
  emotions: [sampleAnalyzeRequest.emotion],
  primary_emotion: sampleAnalyzeRequest.emotion,
  description: '',
})
const isSubmitting = ref(false)
const submitError = ref('')

function syncEmotionSelection() {
  const optionValues = emotionOptions.map((option) => option.value)
  const selected = optionValues.filter((value) => form.emotions.includes(value))
  form.emotions = selected

  if (selected.length === 0) {
    form.primary_emotion = ''
    form.emotion = ''
    return
  }

  if (!selected.includes(form.primary_emotion)) {
    form.primary_emotion = selected[0] ?? ''
  }

  form.emotion = form.primary_emotion
}

function setPrimaryEmotion(emotion: string) {
  if (!form.emotions.includes(emotion)) {
    form.emotions = [...form.emotions, emotion]
  }

  form.primary_emotion = emotion
  form.emotion = emotion
  syncEmotionSelection()
}

function isPrimaryEmotion(emotion: string) {
  return form.primary_emotion === emotion
}

async function submitRecord() {
  submitError.value = ''
  const description = form.description.trim()

  if (!description) {
    submitError.value = '请先填写简要描述，便于生成更准确的分析'
    return
  }

  syncEmotionSelection()
  if (!form.primary_emotion || form.emotions.length === 0) {
    submitError.value = '请至少选择一种当前情绪，并设置主要情绪'
    return
  }

  form.description = description
  isSubmitting.value = true

  try {
    const savedEvent = await createEventRecord(buildEventRecordCreate(form))
    const result = normalizeAnalyzeResponse(savedEvent.single_analysis)

    try {
      localStorage.setItem(LAST_EVENT_STORAGE_KEY, JSON.stringify(form))
      localStorage.setItem(ANALYSIS_RESULT_STORAGE_KEY, JSON.stringify(result))
    } catch (storageError) {
      console.warn('Unable to persist analysis result', storageError)
    }

    await router.push({ name: 'archive' })
  } catch (error) {
    console.error(error)
    submitError.value =
      error instanceof Error ? error.message : '事件保存失败，请稍后再试'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <main class="page narrow-page record-page">
    <span class="record-decoration record-decoration-squiggle" aria-hidden="true"></span>

    <section class="page-heading page-pop-in">
      <h1>
        记录心晴时刻
        <span class="heading-highlight" aria-hidden="true"></span>
      </h1>
      <p class="record-quote pop-shadow card-border">“每一次记录都是一次自我梳理”</p>
    </section>

    <form class="form-panel pop-card pop-shadow page-pop-in" @submit.prevent="submitRecord">
      <fieldset class="field-box date-field">
        <legend class="date-label">
          <span class="field-icon field-icon-soft material-symbol" aria-hidden="true">event</span>
          事件日期
        </legend>
        <input
          v-model="form.event_date"
          class="date-input"
          type="date"
          required
          aria-label="事件日期"
        />
      </fieldset>

      <fieldset>
        <legend>
          <span class="field-icon material-symbol" aria-hidden="true">category</span>
          事件类型
        </legend>
        <div class="option-grid event-type-grid">
          <label v-for="option in eventTypeOptions" :key="option.value" class="record-option">
            <input v-model="form.event_type" type="radio" name="event_type" :value="option.value" />
            <span class="record-option-body">
              <span class="material-symbol" aria-hidden="true">{{ option.icon }}</span>
              <span>{{ option.label }}</span>
            </span>
          </label>
        </div>
      </fieldset>

      <div class="form-grid">
        <fieldset class="field-box">
          <legend>
            <span class="field-icon field-icon-green material-symbol" aria-hidden="true">
              trending_up
            </span>
            严重程度
          </legend>
          <div class="range-field">
            <input v-model.number="form.severity" type="range" min="1" max="5" />
            <div class="range-labels range-tick-list" aria-label="严重程度刻度">
              <span>1 (轻微)</span>
              <span>2</span>
              <span>3</span>
              <span>4</span>
              <span>5 (严重)</span>
            </div>
            <strong class="range-current">当前：{{ form.severity }} 分</strong>
          </div>
        </fieldset>

        <fieldset class="field-box">
          <legend>
            <span class="field-icon field-icon-yellow material-symbol" aria-hidden="true">update</span>
            发生频率
          </legend>
          <div class="pill-row">
            <label v-for="option in frequencyOptions" :key="option.value" class="record-option">
              <input v-model="form.frequency" type="radio" name="frequency" :value="option.value" />
              <span class="record-option-body pill-option frequency-option">
                <span class="material-symbol" aria-hidden="true">{{ option.icon }}</span>
                <span>{{ option.label }}</span>
              </span>
            </label>
          </div>
        </fieldset>
      </div>

      <fieldset>
        <legend>
          <span class="field-icon field-icon-pink material-symbol" aria-hidden="true">
            sentiment_satisfied
          </span>
          当前情绪
        </legend>
        <div class="emotion-row">
          <div v-for="option in emotionOptions" :key="option.value" class="emotion-choice">
            <label class="record-option">
              <input
                v-model="form.emotions"
                type="checkbox"
                name="emotions"
                :value="option.value"
                @change="syncEmotionSelection"
              />
              <span class="record-option-body pill-option emotion-option">
                <span class="material-symbol" aria-hidden="true">{{ option.icon }}</span>
                <span>{{ option.label }}</span>
              </span>
            </label>
            <button
              class="primary-emotion-btn"
              :class="{ active: isPrimaryEmotion(option.value) }"
              type="button"
              :disabled="!form.emotions.includes(option.value)"
              @click="setPrimaryEmotion(option.value)"
            >
              主要
            </button>
          </div>
        </div>
      </fieldset>

      <div class="form-grid">
        <fieldset class="field-box">
          <legend>
            <span class="field-icon field-icon-green material-symbol" aria-hidden="true">forum</span>
            是否已经沟通
          </legend>
          <div class="pill-row">
            <label class="record-option">
              <input v-model="form.has_communicated" type="radio" name="has_communicated" :value="true" />
              <span class="record-option-body pill-option communication-yes">是</span>
            </label>
            <label class="record-option">
              <input v-model="form.has_communicated" type="radio" name="has_communicated" :value="false" />
              <span class="record-option-body pill-option communication-no">否</span>
            </label>
          </div>
        </fieldset>

        <fieldset class="field-box">
          <legend>
            <span class="field-icon field-icon-red material-symbol" aria-hidden="true">warning</span>
            是否出现争吵或冷战
          </legend>
          <div class="pill-row">
            <label class="record-option">
              <input v-model="form.has_conflict" type="radio" name="has_conflict" :value="true" />
              <span class="record-option-body pill-option conflict-yes">是</span>
            </label>
            <label class="record-option">
              <input v-model="form.has_conflict" type="radio" name="has_conflict" :value="false" />
              <span class="record-option-body pill-option conflict-no">否</span>
            </label>
          </div>
        </fieldset>
      </div>

      <label class="full-field">
        <span>
          <span class="field-icon field-icon-soft material-symbol" aria-hidden="true">notes</span>
          简要描述
        </span>
        <textarea
          v-model="form.description"
          rows="4"
          :placeholder="descriptionPlaceholder"
        />
      </label>

      <div class="form-submit">
        <button class="primary-action pop-shadow" type="submit" :disabled="isSubmitting">
          <span
            v-if="isSubmitting"
            class="action-spinner material-symbol"
            aria-hidden="true"
          >
            progress_activity
          </span>
          <span>{{ isSubmitting ? '提交中...' : '保存并查看档案' }}</span>
          <span v-if="!isSubmitting" class="action-icon material-symbol" aria-hidden="true">
            arrow_forward
          </span>
        </button>
        <p v-if="submitError" class="error-text">{{ submitError }}</p>
      </div>
    </form>
  </main>
</template>
