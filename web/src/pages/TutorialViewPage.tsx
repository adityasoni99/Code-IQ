import { useParams, Link } from 'react-router-dom'
import { getTutorialFile } from '../api/client'
import { TutorialViewer } from '../components/viewer/TutorialViewer'

export function TutorialViewPage() {
  const { slug } = useParams<{ slug: string }>()
  if (!slug) {
    return (
      <div>
        <p className="text-red-600">Missing tutorial slug.</p>
        <Link to="/tutorials">Back to tutorials</Link>
      </div>
    )
  }
  const getFile = (path: string) => getTutorialFile(path)
  return (
    <TutorialViewer
      projectName={slug}
      basePath={slug}
      getFile={getFile}
    />
  )
}
