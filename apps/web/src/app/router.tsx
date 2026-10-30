import { Route, Routes } from 'react-router-dom'

import { AdminShell } from './layout/AdminShell'
import { AppShell } from './layout/AppShell'
import { AbilitiesPage } from '@/pages/AbilitiesPage'
import { AdminPokemonPage } from '@/pages/admin/AdminPokemonPage'
import { AdminSyncPage } from '@/pages/admin/AdminSyncPage'
import { CollectionPage } from '@/pages/CollectionPage'
import { DexPage } from '@/pages/DexPage'
import { ExamPage } from '@/pages/ExamPage'
import { HomePage } from '@/pages/HomePage'
import { MoveDetailPage } from '@/pages/MoveDetailPage'
import { MovesPage } from '@/pages/MovesPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { NotesPage } from '@/pages/NotesPage'
import { PokemonDetailPage } from '@/pages/PokemonDetailPage'
import { TypeCalcPage } from '@/pages/TypeCalcPage'
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
        <Route path="usage" element={<UsageRankingPage />} />
        <Route path="type-calc" element={<TypeCalcPage />} />
        <Route path="collection" element={<CollectionPage />} />
        <Route path="notes" element={<NotesPage />} />
        <Route path="exam" element={<ExamPage />} />
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