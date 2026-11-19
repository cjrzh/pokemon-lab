/**
 * 出卷页测试：设置 → 答题 → 结果三段流程、判分反馈、错题集。
 *
 * 用可控的 hooks mock 模拟后端：建卷返回固定 2 题，作答按题目名称比对。
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { QuizSession } from '@/features/quiz/api'

const NAMES: Record<number, { zh: string; en: string }> = {
  1: { zh: '妙蛙种子', en: 'bulbasaur' },
  4: { zh: '小火龙', en: 'charmander' },
}

function makeSession(overrides: Partial<QuizSession> = {}): QuizSession {
  return {
    id: 1,
    total: 2,
    answered: 0,
    correct: 0,
    score: 0,
    finished: false,
    scope: {
      generation: null,
      dex_from: null,
      dex_to: null,
      count: 2,
      mode: 'random',
      available: 2,
    },
    created_at: null,
    finished_at: null,
    questions: [
      {
        position: 0,
        dex_number: 1,
        artwork_url: '/media/artwork/1.png',
        artwork_fallback_url: null,
        sprite_url: '/media/sprites/1.png',
        name_zh: null,
        name_en: null,
        answer: null,
        is_correct: null,
        expected_zh: null,
        expected_en: null,
      },
      {
        position: 1,
        dex_number: 4,
        artwork_url: '/media/artwork/4.png',
        artwork_fallback_url: null,
        sprite_url: '/media/sprites/4.png',
        name_zh: null,
        name_en: null,
        answer: null,
        is_correct: null,
        expected_zh: null,
        expected_en: null,
      },
    ],
    ...overrides,
  }
}

const state = vi.hoisted(() => ({
  created: [] as unknown[],
  answers: [] as { position: number; answer: string }[],
  session: null as unknown,
  mistakes: { items: [] as unknown[], total: 0 },
}))

/** 模拟后端判分与进度推进。 */
function judgeAndAdvance(position: number, answer: string): QuizSession {
  const session = state.session as QuizSession
  const question = session.questions.find((q) => q.position === position)!
  const name = NAMES[question.dex_number]
  const correct = answer.trim().toLowerCase() === name.en || answer.trim() === name.zh
  const questions = session.questions.map((q) =>
    q.position === position
      ? {
          ...q,
          answer,
          is_correct: correct,
          name_zh: name.zh,
          name_en: name.en,
          expected_zh: name.zh,
          expected_en: name.en,
        }
      : q,
  )
  const answered = session.answered + 1
  const correctCount = session.correct + (correct ? 1 : 0)
  return {
    ...session,
    questions,
    answered,
    correct: correctCount,
    score: Math.round((correctCount * 100) / answered),
    finished: answered >= session.total,
  }
}

vi.mock('@/features/quiz/hooks', () => ({
  useCreateQuiz: () => ({
    mutateAsync: async (payload: unknown) => {
      state.created.push(payload)
      state.session = makeSession()
      return { session: state.session }
    },
    isPending: false,
  }),
  useAnswerQuiz: () => ({
    mutateAsync: async ({
      position,
      answer,
    }: {
      quizId: number
      position: number
      answer: string
    }) => {
      state.answers.push({ position, answer })
      const session = judgeAndAdvance(position, answer)
      state.session = session
      const question = session.questions.find((q) => q.position === position)!
      return {
        correct: question.is_correct,
        expected_zh: question.expected_zh,
        expected_en: question.expected_en,
        session,
      }
    },
    isPending: false,
  }),
  useQuizMistakes: () => ({
    isPending: false,
    isError: false,
    data: state.mistakes,
  }),
  useRemoveQuizMistake: () => ({ mutate: vi.fn(), isPending: false }),
  useClearQuizMistakes: () => ({ mutate: vi.fn(), isPending: false }),
}))

const { QuizPage } = await import('@/pages/QuizPage')

function renderPage() {
  return render(
    <MemoryRouter>
      <QuizPage />
    </MemoryRouter>,
  )
}

async function startQuiz() {
  await userEvent.click(screen.getByRole('button', { name: /开始出卷/ }))
}

beforeEach(() => {
  state.created = []
  state.answers = []
  state.session = null
  state.mistakes = { items: [], total: 0 }
})

describe('QuizPage 出卷流程', () => {
  it('默认随机 20 题，开始出卷后进入答题', async () => {
    renderPage()
    expect(screen.getByText('出卷设置')).toBeInTheDocument()

    await startQuiz()

    expect(state.created[0]).toMatchObject({ mode: 'random', count: 20 })
    expect(screen.getByText('第 1 / 2 题')).toBeInTheDocument()
  })

  it('可选全量出卷（不传 count）', async () => {
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: '全量' }))
    await startQuiz()

    expect(state.created[0]).toMatchObject({ mode: 'all', count: null })
  })

  it('世代与编号区间会传给出卷接口', async () => {
    renderPage()
    await userEvent.selectOptions(screen.getByLabelText('世代范围'), '2')
    await userEvent.type(screen.getByLabelText('编号下限'), '152')
    await userEvent.type(screen.getByLabelText('编号上限'), '251')
    await startQuiz()

    expect(state.created[0]).toMatchObject({
      generation: 2,
      dex_from: 152,
      dex_to: 251,
    })
  })

  it('答对显示「正确」与标准答案，可进入下一题', async () => {
    renderPage()
    await startQuiz()

    await userEvent.type(screen.getByLabelText('宝可梦名称'), '妙蛙种子')
    await userEvent.click(screen.getByRole('button', { name: '提交' }))

    expect(await screen.findByText('正确')).toBeInTheDocument()
    expect(screen.getByText('bulbasaur')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /下一题/ }))
    expect(screen.getByText('第 2 / 2 题')).toBeInTheDocument()
  })

  it('答错显示正确答案', async () => {
    renderPage()
    await startQuiz()

    await userEvent.type(screen.getByLabelText('宝可梦名称'), '皮卡丘')
    await userEvent.click(screen.getByRole('button', { name: '提交' }))

    expect(await screen.findByText('答错了')).toBeInTheDocument()
    expect(screen.getByText('你的答案：皮卡丘')).toBeInTheDocument()
    expect(screen.getByText('妙蛙种子')).toBeInTheDocument()
  })

  it('答完全部题目后可查看结果（正确率与逐题回看）', async () => {
    renderPage()
    await startQuiz()

    // 第一题答对
    await userEvent.type(screen.getByLabelText('宝可梦名称'), 'bulbasaur')
    await userEvent.click(screen.getByRole('button', { name: '提交' }))
    await userEvent.click(await screen.findByRole('button', { name: /下一题/ }))

    // 第二题答错
    await userEvent.type(screen.getByLabelText('宝可梦名称'), '错')
    await userEvent.click(screen.getByRole('button', { name: '提交' }))
    await userEvent.click(await screen.findByRole('button', { name: /下一题/ }))

    expect(await screen.findByText('本轮结果')).toBeInTheDocument()
    expect(screen.getByText('50')).toBeInTheDocument()
    expect(screen.getByText('逐题回看')).toBeInTheDocument()
    // 逐题回看里有两只宝可梦与作答
    expect(screen.getByText(/你答：错/)).toBeInTheDocument()
  })

  it('可以中途结束并直接看结果', async () => {
    renderPage()
    await startQuiz()
    await userEvent.click(screen.getByRole('button', { name: '结束并看结果' }))

    expect(screen.getByText('本轮结果')).toBeInTheDocument()
    expect(screen.getByText(/未答 2/)).toBeInTheDocument()
  })
})

describe('QuizPage 错题集', () => {
  it('显示错题，并可跳转图鉴', () => {
    state.mistakes = {
      total: 1,
      items: [
        {
          dex_number: 4,
          name_zh: '小火龙',
          name_en: 'charmander',
          sprite_url: '/media/sprites/4.png',
          artwork_url: null,
          wrong_count: 2,
          last_answer: '之类',
          first_wrong_at: '2026-11-09T00:00:00',
          last_wrong_at: '2026-11-09T00:00:00',
        },
      ],
    }
    renderPage()

    expect(screen.getByRole('link', { name: /小火龙/ })).toHaveAttribute('href', '/dex/4')
    expect(screen.getByText('错 2')).toBeInTheDocument()
  })

  it('没有错题时给出空状态', () => {
    renderPage()
    expect(screen.getByText(/还没有错题/)).toBeInTheDocument()
  })
})
