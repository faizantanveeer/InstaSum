import { useWorkspaceContext } from '../contexts/WorkspaceContext'

export function useWorkspace() {
  return useWorkspaceContext()
}
