import { Link, Outlet } from 'react-router-dom'

export function AppLayout() {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <header className="border-b bg-white px-4 py-3 flex items-center gap-4">
        <Link to="/" className="font-semibold text-slate-800 hover:text-slate-600">
          Code-IQ
        </Link>
        <nav className="flex gap-4 text-sm">
          <Link to="/" className="text-slate-600 hover:text-slate-900">New Job</Link>
        </nav>
      </header>
      <main className="flex-1 p-4">
        <Outlet />
      </main>
    </div>
  )
}
