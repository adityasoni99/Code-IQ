import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppLayout } from './components/layout/AppLayout'
import { HomePage } from './pages/HomePage'
import { JobStatusPage } from './pages/JobStatusPage'
import { ViewerPage } from './pages/ViewerPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 1000 },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<HomePage />} />
            <Route path="jobs/:id" element={<JobStatusPage />} />
            <Route path="jobs/:id/view" element={<ViewerPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
