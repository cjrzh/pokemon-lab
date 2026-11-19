import { Route, Routes } from 'react-router-dom'

import { AdminShell } from './layout/AdminShell'
import { AppShell } from './layout/AppShell'
import { AbilitiesPage } from '@/pages/AbilitiesPage'
import { AdminPokemonPage } from '@/pages/admin/AdminPokemonPage'
import { AdminSyncPage } from '@/pages/admin/AdminSyncPage'
import { DexPage } from '@/pages/DexPage'
import { HomePage } from '@/pages/HomePage'
import { ItemsPage } from '@/pages/ItemsPage'
import { MoveDetailPage } from '@/pages/MoveDetailPage'
import { MovesPage } from '@/pages/MovesPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { PokemonDetailPage } from '@/pages/PokemonDetailPage'
import { QuizPage } from '@/pages/QuizPage'
import { TypeCalcPage } from '@/pages/TypeCalcPage'
import { TeamShowdownPage } from '@/pages/TeamShowdownPage'
import { TournamentDetailPage } from '@/pages/TournamentDetailPage'
import { TournamentsPage } from '@/pages/TournamentsPage'
import { TeamsPage } from '@/pages/TeamsPage'
import { UsageHistoryPage } from '@/pages/UsageHistoryPage'
import { UsageRankingPage } from '@/pages/UsageRankingPage'

export function AppRouter() {
  return (
    <Routes>
      {/* 公开浏览区（只读） */}
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="dex" element={<DexPage />} />
        <Route path="dex/:dexNumber" element={<PokemonDetailPage />} />
        <Route path="abilities" element={<AbilitiesPage />} />
        <Route path="moves" element={<MovesPage />} />
        <Route path="moves/:moveName" element={<MoveDetailPage />} />
        <Route path="items" element={<ItemsPage />} />
        <Route path="usage" element={<UsageRankingPage />} />
        <Route path="usage/history" element={<UsageHistoryPage />} />
        <Route path="tournaments" element={<TournamentsPage />} />
        <Route path="tournaments/:tournamentId" element={<TournamentDetailPage />} />
        <Route path="teams" element={<TeamsPage />} />
        <Route path="quiz" element={<QuizPage />} />
        <Route path="teams/:teamId/showdown" element={<TeamShowdownPage />} />
        <Route path="type-calc" element={<TypeCalcPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>

      {/* 后台管理区（编辑与同步；本地个人使用，MVP 无认证 —— 见 ARCHITECTURE.md） */}
      <Route path="admin" element={<AdminShell />}>
        <Route index element={<AdminSyncPage />} />
        <Route path="sync" element={<AdminSyncPage />} />
        <Route path="pokemon" element={<AdminPokemonPage />} />
      </Route>
    </Routes>
  )
}