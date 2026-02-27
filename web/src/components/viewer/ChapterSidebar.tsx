import type { ChapterItem } from './MarkdownRenderer'

interface ChapterSidebarProps {
  projectName: string
  chapterList: ChapterItem[]
  selectedFilename: string | null
  onSelect: (filename: string | null) => void
}

export function ChapterSidebar({ projectName, chapterList, selectedFilename, onSelect }: ChapterSidebarProps) {
  return (
    <aside className="w-64 shrink-0 border-r border-slate-200 bg-white overflow-y-auto">
      <div className="p-3 border-b border-slate-200">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Chapters</h2>
        <p className="mt-1 text-sm font-medium text-slate-800 truncate" title={projectName}>
          {projectName}
        </p>
      </div>
      <nav className="py-2">
        <button
          type="button"
          onClick={() => onSelect(null)}
          className={`w-full px-3 py-2 text-left text-sm rounded-r ${selectedFilename === null ? 'bg-slate-200 font-medium text-slate-900' : 'text-slate-600 hover:bg-slate-100'}`}
        >
          Overview
        </button>
        {chapterList.map((ch) => (
          <button
            key={ch.filename}
            type="button"
            onClick={() => onSelect(ch.filename)}
            className={`w-full px-3 py-2 text-left text-sm rounded-r truncate ${selectedFilename === ch.filename ? 'bg-slate-200 font-medium text-slate-900' : 'text-slate-600 hover:bg-slate-100'}`}
            title={ch.title}
          >
            {ch.title}
          </button>
        ))}
      </nav>
    </aside>
  )
}
