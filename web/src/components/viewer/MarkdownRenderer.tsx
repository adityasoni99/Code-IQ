import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import oneLight from 'react-syntax-highlighter/dist/esm/styles/prism/one-light'
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
    a: ({ href, children, ...props }) => {
      if (href?.endsWith('.md') && onChapterClick) {
        return (
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault()
              onChapterClick(href)
            }}
            className="text-sky-600 hover:underline cursor-pointer"
            {...props}
          >
            {children}
          </a>
        )
      }
      return (
        <a href={href} {...props}>
          {children}
        </a>
      )
    },
    code: ({ node, className, children, ...props }) => {
      const raw = Array.isArray(children)
        ? (children as string[]).join('\n')
        : String(children ?? '')
      const isMermaid = /language-mermaid/.exec(className || '')
      if (isMermaid) {
        return (
          <MermaidDiagram
            source={raw.trim()}
            jobId={jobId}
            onNodeClick={onChapterClick && chapterList?.length ? (label) => {
              const normalized = (s: string) => s.replace(/\s+/g, ' ').trim().toLowerCase()
              const key = normalized(label)
              const ch = chapterList.find((c) => normalized(c.title).includes(key) || key.includes(normalized(c.title)))
              if (ch) onChapterClick(ch.filename)
            } : undefined}
          />
        )
      }
      const langMatch = /language-(\w+)/.exec(className || '')
      if (langMatch) {
        return (
          <SyntaxHighlighter
            language={langMatch[1]}
            style={oneLight}
            PreTag="div"
            customStyle={{ margin: '0.5rem 0', borderRadius: '0.375rem', fontSize: '0.875rem' }}
            codeTagProps={{ className: '' }}
          >
            {raw.trimEnd()}
          </SyntaxHighlighter>
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
