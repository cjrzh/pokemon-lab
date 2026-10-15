import { Route, Routes } from 'react-router-dom'

import { AppShell } from './layout/AppShell'
import { CollectionPage } from '@/pages/CollectionPage'
import { DexPage } from '@/pages/DexPage'
import { ExamPage } from '@/pages/ExamPage'
import { HomePage } from '@/pages/HomePage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { NotesPage } from '@/pages/NotesPage'
import { TypeCalcPage } from '@/pages/TypeCalcPage'

export function AppRouter() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="dex" element={<DexPage />} />
        <Route path="type-calc" element={<TypeCalcPage />} />
        <Route path="collection" element={<CollectionPage />} />
        <Route path="notes" element={<NotesPage />} />
        <Route path="exam" element={<ExamPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}