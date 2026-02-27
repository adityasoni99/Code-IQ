import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { MermaidDiagram } from './MermaidDiagram'

export interface ChapterItem {
  num: string
  title: string
  filename: string
}

interface MarkdownRendererProps {
  content: string
  basePath?: string
  jobId?: string
  onChapterClick?: (filename: string) => void
  chapterList?: ChapterItem[]
}

export function MarkdownRenderer({ content, basePath, jobId, onChapterClick, chapterList }: MarkdownRendererProps) {
  const components: import('react-markdown').Components = {
    code: ({ node, className, children, ...props }) => {
      const isMermaid = /language-mermaid/.exec(className || '')
      if (isMermaid) {
        return (
          <MermaidDiagram
            source={String(children).trim()}
            jobId={jobId}
            basePath={basePath}
            onNodeClick={onChapterClick && chapterList?.length ? (label) => {
              const normalized = (s: string) => s.replace(/\s+/g, ' ').trim().toLowerCase()
              const key = normalized(label)
              const ch = chapterList.find((c) => normalized(c.title).includes(key) || key.includes(normalized(c.title)))
              if (ch) onChapterClick(ch.filename)
            } : undefined}
          />
        )
      }
      return (
        <code className={className} {...props}>
          {children}
        </code>
      )
    },
  }

  return (
    <div className="prose prose-slate max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  )
}
