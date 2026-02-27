import { Link } from 'react-router-dom'

export interface BreadcrumbItem {
  slug: string
  name: string
}

interface BreadcrumbProps {
  items: BreadcrumbItem[]
  jobId: string
}

export function Breadcrumb({ items, jobId }: BreadcrumbProps) {
  return (
    <nav className="flex items-center gap-2 text-sm text-slate-600 mb-4">
      <Link to={`/jobs/${jobId}/view`} className="hover:text-slate-900">
        Home
      </Link>
      {items.map((item, i) => (
        <span key={item.slug}>
          <span className="mx-1">/</span>
          {i === items.length - 1 ? (
            <span className="text-slate-900 font-medium">{item.name}</span>
          ) : (
            <Link to={`/jobs/${jobId}/view#${item.slug}`} className="hover:text-slate-900">
              {item.name}
            </Link>
          )}
        </span>
      ))}
    </nav>
  )
}
