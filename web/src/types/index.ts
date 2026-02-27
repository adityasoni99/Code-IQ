export interface Job {
  job_id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  created_at: number
  updated_at: number
  result?: { final_output_dir?: string; summary?: string } | null
  error?: string | null
  progress?: { completed: number; total: number; current_folder: string } | null
  mode: 'single' | 'recursive'
}

export interface TreeNode {
  name: string
  slug: string
  path?: string
  children?: TreeNode[]
  mermaid?: string
  summary?: string
}

export interface TutorialPage {
  slug: string
  title: string
  content?: string
}
