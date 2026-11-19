/**
 * 出卷 hooks（TanStack Query）。
 *
 * 答题是「用户动作 → 后端判分」，用 mutation；错题集是只读列表，用 query。
 * 试卷详情不挂 query 自动刷新：答题过程中由 mutation 的响应直接更新本地状态，
 * 避免每题都多一次请求。
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  answerQuiz,
  clearQuizMistakes,
  createQuiz,
  fetchQuizMistakes,
  removeQuizMistake,
  type QuizCreatePayload,
} from './api'

export const quizMistakesKey = () => ['quiz', 'mistakes'] as const

export function useQuizMistakes() {
  return useQuery({
    queryKey: quizMistakesKey(),
    queryFn: ({ signal }) => fetchQuizMistakes(signal),
    staleTime: 30_000,
  })
}

export function useCreateQuiz() {
  return useMutation({ mutationFn: (payload: QuizCreatePayload) => createQuiz(payload) })
}

export function useAnswerQuiz() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({
      quizId,
      position,
      answer,
    }: {
      quizId: number
      position: number
      answer: string
    }) => answerQuiz(quizId, position, answer),
    onSuccess: () => {
      // 答错会让错题集变化；下次打开列表时拿最新数据
      void client.invalidateQueries({ queryKey: quizMistakesKey() })
    },
  })
}

export function useRemoveQuizMistake() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: removeQuizMistake,
    onSuccess: () => void client.invalidateQueries({ queryKey: quizMistakesKey() }),
  })
}

export function useClearQuizMistakes() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: clearQuizMistakes,
    onSuccess: () => void client.invalidateQueries({ queryKey: quizMistakesKey() }),
  })
}
