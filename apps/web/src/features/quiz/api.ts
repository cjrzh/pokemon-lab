/**
 * 出卷（图鉴识别自测）API。
 *
 * 后端契约见 services/api/app/schemas/quiz.py。
 * 题目在作答前不返回名称 —— 评分只由后端判，前端不自己比对答案。
 */

import { apiRequest } from '@/lib/apiClient'

export interface QuizScope {
  generation: number | null
  dex_from: number | null
  dex_to: number | null
  count: number
  mode: 'random' | 'all'
  available: number
}

export interface QuizQuestion {
  position: number
  dex_number: number
  artwork_url: string | null
  artwork_fallback_url: string | null
  sprite_url: string | null
  /** 已作答 / 结果页才会出现（答题中为 null）。 */
  name_zh: string | null
  name_en: string | null
  answer: string | null
  is_correct: boolean | null
  expected_zh: string | null
  expected_en: string | null
}

export interface QuizSession {
  id: number
  total: number
  answered: number
  correct: number
  score: number
  finished: boolean
  scope: QuizScope
  created_at: string | null
  finished_at: string | null
  questions: QuizQuestion[]
}

export interface QuizCreatePayload {
  generation?: number | null
  dex_from?: number | null
  dex_to?: number | null
  count?: number | null
  mode?: 'random' | 'all'
}

export interface QuizAnswerResult {
  correct: boolean
  expected_zh: string | null
  expected_en: string
  session: QuizSession
}

export interface QuizMistake {
  dex_number: number
  name_zh: string | null
  name_en: string
  sprite_url: string | null
  artwork_url: string | null
  wrong_count: number
  last_answer: string | null
  first_wrong_at: string | null
  last_wrong_at: string | null
}

export interface QuizMistakeList {
  items: QuizMistake[]
  total: number
}

export function createQuiz(payload: QuizCreatePayload): Promise<{ session: QuizSession }> {
  return apiRequest<{ session: QuizSession }>('/quiz', { method: 'POST', body: payload })
}

export function fetchQuiz(quizId: number, signal?: AbortSignal): Promise<QuizSession> {
  return apiRequest<QuizSession>(`/quiz/${quizId}`, { signal })
}

export function answerQuiz(
  quizId: number,
  position: number,
  answer: string,
): Promise<QuizAnswerResult> {
  return apiRequest<QuizAnswerResult>(`/quiz/${quizId}/answer`, {
    method: 'POST',
    body: { position, answer },
  })
}

export function fetchQuizMistakes(signal?: AbortSignal): Promise<QuizMistakeList> {
  return apiRequest<QuizMistakeList>('/quiz/mistakes', { signal })
}

export function removeQuizMistake(dexNumber: number): Promise<void> {
  return apiRequest<void>(`/quiz/mistakes/${dexNumber}`, { method: 'DELETE' })
}

export function clearQuizMistakes(): Promise<{ deleted: number }> {
  return apiRequest<{ deleted: number }>('/quiz/mistakes', { method: 'DELETE' })
}
