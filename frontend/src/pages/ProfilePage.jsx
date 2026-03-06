import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import AppShell from '../components/AppShell'
import GridToolbar from '../components/GridToolbar'
import PaginationBar from '../components/PaginationBar'
import ProfileHeader from '../components/ProfileHeader'
import ReelCard from '../components/ReelCard'
import ReelDetailModal from '../components/ReelDetailModal'
import { ErrorState, LoadingSkeleton, NoReelsState, PrivateState } from '../components/States'
import copy from '../copy'
import { useToast } from '../contexts/ToastContext'
import { apiFetch } from '../lib/api'
import { useWorkspace } from '../hooks/useWorkspace'

function replaceReel(list, reelPatch) {
  return list.map((reel) => (reel.id === reelPatch.id ? { ...reel, ...reelPatch } : reel))
}

export default function ProfilePage() {
  const { username } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const { toast } = useToast()

  const {
    user,
    history,
    pendingSearch,
    searching,
    searchProfile,
    reloadHistory,
    logoutUser,
  } = useWorkspace()

  const [profile, setProfile] = useState(null)
  const [reels, setReels] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)

  const [keywordInput, setKeywordInput] = useState('')
  const [keyword, setKeyword] = useState('')
  const [sortBy, setSortBy] = useState('newest')
  const [statusFilter, setStatusFilter] = useState('all')
  const [viewMode, setViewMode] = useState('grid')

  const [pagination, setPagination] = useState({ page: 1, page_size: 12, total: 0, total_pages: 1 })
  const [pageSize, setPageSize] = useState(12)

  const [modalOpen, setModalOpen] = useState(false)
  const [modalReelId, setModalReelId] = useState(null)
  const [modalTab, setModalTab] = useState('summary')

  const [busyReels, setBusyReels] = useState({})
  const [generateAllState, setGenerateAllState] = useState({ running: false, processed: 0, total: 0 })

  const pollingRefs = useRef(new Map())
  const jobPollingRef = useRef(null)

  const page = Math.max(1, Number(searchParams.get('page') || 1))
  const isPendingCurrentSearch = pendingSearch?.username === username

  const clearPolling = useCallback(() => {
    pollingRefs.current.forEach((timer) => window.clearInterval(timer))
    pollingRefs.current.clear()
    if (jobPollingRef.current) {
      window.clearInterval(jobPollingRef.current)
      jobPollingRef.current = null
    }
  }, [])

  useEffect(() => () => clearPolling(), [clearPolling])

  useEffect(() => {
    document.title = username ? copy.titles.profile({ username }) : copy.titles.default
  }, [username])

  useEffect(() => {
    const timer = window.setTimeout(() => setKeyword(keywordInput.trim().toLowerCase()), 300)
    return () => window.clearTimeout(timer)
  }, [keywordInput])

  useEffect(() => {
    apiFetch('/api/config')
      .then((data) => {
        const size = Number(data?.page_size || 12)
        setPageSize(Number.isNaN(size) ? 12 : Math.max(1, size))
      })
      .catch(() => {
        setPageSize(12)
      })
  }, [])

  const loadProfile = useCallback(async () => {
    if (!username) return
    if (isPendingCurrentSearch && searching) {
      setLoading(true)
      setError('')
      return
    }
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch(`/api/profiles/${username}?page=${page}&page_size=${pageSize}`)
      setProfile(data.profile)
      setReels(data.reels || [])
      setPagination(data.pagination || { page, page_size: pageSize, total: 0, total_pages: 1 })
      await reloadHistory()
    } catch (err) {
      setProfile(null)
      setReels([])
      if (err.status === 404) {
        setError('profile_not_found')
      } else {
        setError('fetch_failed')
      }
    } finally {
      setLoading(false)
    }
  }, [isPendingCurrentSearch, page, pageSize, reloadHistory, searching, username])

  useEffect(() => {
    loadProfile().catch(() => {})
  }, [loadProfile])

  const mergeReelStatus = useCallback((id, payload) => {
    setReels((prev) => replaceReel(prev, { id, ...payload }))
  }, [])

  const pollSingleReel = useCallback((reelId) => {
    if (pollingRefs.current.has(reelId)) return

    const timer = window.setInterval(async () => {
      try {
        const data = await apiFetch(`/api/reels/${reelId}/status`)
        const reel = data?.reel
        if (!reel) return

        mergeReelStatus(reelId, reel)

        if (['completed', 'failed', 'skipped'].includes(reel.processing_status)) {
          window.clearInterval(timer)
          pollingRefs.current.delete(reelId)
          setBusyReels((prev) => {
            const next = { ...prev }
            delete next[reelId]
            return next
          })
          if (reel.processing_status === 'completed') {
            toast(copy.toasts.singleDone, 'success')
          } else if (reel.processing_status === 'failed') {
            toast(reel.error_reason || copy.toasts.singleFailed, 'error')
          }
        }
      } catch {
        // keep polling; transient network failure
      }
    }, 3000)

    pollingRefs.current.set(reelId, timer)
  }, [mergeReelStatus, toast])

  const fetchReelStatusOnce = useCallback(async (reelId) => {
    try {
      const data = await apiFetch(`/api/reels/${reelId}/status`)
      if (data?.reel) {
        mergeReelStatus(reelId, data.reel)
      }
    } catch {
      // ignore
    }
  }, [mergeReelStatus])

  const handleGenerate = useCallback(async (reelId, regenerate = false) => {
    setBusyReels((prev) => ({ ...prev, [reelId]: true }))
    mergeReelStatus(reelId, { processing_status: 'processing', error_reason: '' })

    try {
      await apiFetch(`/api/reels/${reelId}/generate`, {
        method: 'POST',
        body: JSON.stringify({ regenerate }),
      })
      toast(copy.toasts.singleStarted, 'info')
      pollSingleReel(reelId)
    } catch (err) {
      setBusyReels((prev) => {
        const next = { ...prev }
        delete next[reelId]
        return next
      })
      mergeReelStatus(reelId, { processing_status: 'failed', error_reason: err.message || copy.toasts.singleFailed })
      toast(err.message || copy.toasts.singleFailed, 'error')
    }
  }, [mergeReelStatus, pollSingleReel, toast])

  const pollJob = useCallback((jobId) => {
    if (jobPollingRef.current) {
      window.clearInterval(jobPollingRef.current)
      jobPollingRef.current = null
    }

    jobPollingRef.current = window.setInterval(async () => {
      try {
        const data = await apiFetch(`/api/jobs/${jobId}/status`)
        const job = data?.job
        if (!job) return

        setGenerateAllState({
          running: ['queued', 'running'].includes(job.status),
          processed: job.processed_count || 0,
          total: job.total_count || 0,
        })

        const statuses = data?.reels || []
        const statusMap = new Map(statuses.map((item) => [item.id, item]))

        setReels((prev) =>
          prev.map((item) => {
            const next = statusMap.get(item.id)
            if (!next) return item
            return {
              ...item,
              processing_status: next.processing_status || item.processing_status,
              processed: next.processed,
            }
          }),
        )

        statuses.forEach((item) => {
          if (['completed', 'failed', 'skipped'].includes(item.processing_status)) {
            fetchReelStatusOnce(item.id)
          }
        })

        if (['completed', 'failed', 'partial_failed'].includes(job.status)) {
          window.clearInterval(jobPollingRef.current)
          jobPollingRef.current = null
          setGenerateAllState({ running: false, processed: job.processed_count || 0, total: job.total_count || 0 })
          if (job.status === 'completed') {
            toast(copy.toasts.batchComplete({ n: job.total_count || 0 }), 'success')
          } else {
            toast(copy.toasts.batchPartial({
              success: job.success_count || 0,
              total: job.total_count || 0,
              failed: job.failed_count || 0,
            }), 'warning')
          }
        }
      } catch {
        // ignore transient errors and keep polling
      }
    }, 3000)
  }, [fetchReelStatusOnce, toast])

  const handleGenerateAll = useCallback(async (regenerate = false) => {
    if (!profile?.id) return

    setGenerateAllState({ running: true, processed: 0, total: 0 })

    try {
      const data = await apiFetch(`/api/profiles/${profile.id}/generate-all`, {
        method: 'POST',
        body: JSON.stringify({ regenerate }),
      })

      const reelIds = data?.reel_ids || []
      setGenerateAllState({
        running: data?.status !== 'completed',
        processed: data?.status === 'completed' ? data.total_targeted || 0 : 0,
        total: data?.total_targeted || 0,
      })

      if (data?.status === 'completed') {
        toast(
          data?.total_targeted
            ? copy.toasts.batchComplete({ n: data.total_targeted || 0 })
            : copy.profile.generateAllDone,
          'info',
        )
        reelIds.forEach((id) => fetchReelStatusOnce(id))
        return
      }

      toast(copy.toasts.batchStarted({ n: data?.total_targeted || 0 }), 'info')
      pollJob(data.job_id)
      reelIds.forEach((id) => mergeReelStatus(id, { processing_status: 'processing', error_reason: '' }))
    } catch (err) {
      setGenerateAllState({ running: false, processed: 0, total: 0 })
      toast(err.message || copy.errors.genericServer, 'error')
    }
  }, [fetchReelStatusOnce, mergeReelStatus, pollJob, profile?.id, toast])

  const handleRefresh = useCallback(async () => {
    if (!profile?.username) return
    setRefreshing(true)
    try {
      await searchProfile(profile.username, { source: 'refresh' })
      await loadProfile()
    } catch {
      // toast already handled by hook
    } finally {
      setRefreshing(false)
    }
  }, [loadProfile, profile?.username, searchProfile])

  const handleExport = useCallback((format) => {
    if (!profile?.id) return
    toast(copy.loading.exportPreparing, 'info')
    window.location.href = `/export/profile/${profile.id}?format=${format}`
  }, [profile?.id, toast])

  const onPageChange = useCallback((nextPage) => {
    const safePage = Math.max(1, Math.min(nextPage, pagination.total_pages || 1))
    const next = new URLSearchParams(searchParams)
    next.set('page', String(safePage))
    setSearchParams(next)
    window.requestAnimationFrame(() => {
      window.scrollTo({ top: 0, behavior: 'smooth' })
    })
  }, [pagination.total_pages, searchParams, setSearchParams])

  const filteredSortedReels = useMemo(() => {
    let items = [...reels]

    if (statusFilter === 'processed') {
      items = items.filter((item) => item.processing_status === 'completed' || item.processed)
    } else if (statusFilter === 'pending') {
      items = items.filter((item) => ['pending', 'processing'].includes(item.processing_status || 'pending'))
    } else if (statusFilter === 'failed') {
      items = items.filter((item) => item.processing_status === 'failed')
    }

    if (keyword) {
      items = items.filter((item) => {
        const text = [item.ai_title, item.ai_summary, item.summary_detail, item.transcript, item.caption]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
        return text.includes(keyword)
      })
    }

    items.sort((a, b) => {
      if (sortBy === 'oldest') {
        return new Date(a.posted_at || 0).getTime() - new Date(b.posted_at || 0).getTime()
      }
      if (sortBy === 'likes') {
        return Number(b.like_count || 0) - Number(a.like_count || 0)
      }
      if (sortBy === 'views') {
        return Number(b.view_count || 0) - Number(a.view_count || 0)
      }
      if (sortBy === 'processed') {
        const aScore = a.processing_status === 'completed' ? 1 : 0
        const bScore = b.processing_status === 'completed' ? 1 : 0
        if (aScore !== bScore) return bScore - aScore
        return new Date(b.posted_at || 0).getTime() - new Date(a.posted_at || 0).getTime()
      }
      return new Date(b.posted_at || 0).getTime() - new Date(a.posted_at || 0).getTime()
    })

    return items
  }, [keyword, reels, sortBy, statusFilter])

  const modalIndex = useMemo(() => filteredSortedReels.findIndex((item) => item.id === modalReelId), [filteredSortedReels, modalReelId])

  const openModal = useCallback((reel, tab = 'summary') => {
    setModalReelId(reel.id)
    setModalTab(tab === 'audio' ? 'summary' : tab)
    setModalOpen(true)
  }, [])

  const closeModal = useCallback(() => {
    setModalOpen(false)
  }, [])

  const goPrevModal = useCallback(() => {
    if (!filteredSortedReels.length) return
    const idx = modalIndex < 0 ? 0 : modalIndex
    const next = (idx - 1 + filteredSortedReels.length) % filteredSortedReels.length
    setModalReelId(filteredSortedReels[next].id)
  }, [filteredSortedReels, modalIndex])

  const goNextModal = useCallback(() => {
    if (!filteredSortedReels.length) return
    const idx = modalIndex < 0 ? 0 : modalIndex
    const next = (idx + 1) % filteredSortedReels.length
    setModalReelId(filteredSortedReels[next].id)
  }, [filteredSortedReels, modalIndex])

  useEffect(() => {
    if (!reels.length || generateAllState.running) return

    const processing = reels.filter((item) => item.processing_status === 'processing').map((item) => item.id)
    processing.forEach((id) => pollSingleReel(id))
  }, [generateAllState.running, pollSingleReel, reels])

  const unprocessedCount = useMemo(
    () => reels.filter((item) => item.processing_status !== 'completed').length,
    [reels],
  )

  const renderContent = () => {
    if (loading) return <LoadingSkeleton />
    if (error) {
      const isNotFound = error === 'profile_not_found'
      return (
        <ErrorState
          title={isNotFound ? copy.states.profileNotFoundTitle : copy.states.fetchFailedTitle}
          message={isNotFound ? copy.states.profileNotFoundSubtitle : copy.states.fetchFailedSubtitle}
          onRetry={isNotFound ? () => navigate('/dashboard') : loadProfile}
        />
      )
    }
    if (!profile) {
      return (
        <ErrorState
          title={copy.states.profileNotFoundTitle}
          message={copy.states.profileNotFoundSubtitle}
          onRetry={() => navigate('/dashboard')}
        />
      )
    }
    if (profile.is_private_last_seen) return <PrivateState />

    return (
      <>
        <ProfileHeader
          profile={profile}
          refreshing={refreshing || searching}
          onRefresh={handleRefresh}
          onExport={handleExport}
          unprocessedCount={unprocessedCount}
          onGenerateAll={handleGenerateAll}
          generateAllState={generateAllState}
        />

        <GridToolbar
          keyword={keywordInput}
          onKeywordChange={setKeywordInput}
          viewMode={viewMode}
          onViewModeChange={setViewMode}
          sortBy={sortBy}
          onSortByChange={setSortBy}
          statusFilter={statusFilter}
          onStatusFilterChange={setStatusFilter}
        />

        {filteredSortedReels.length === 0 ? (
          <NoReelsState keyword={keywordInput.trim()} statusFilter={statusFilter} />
        ) : (
          <div className={`reel-grid page-fade-grid ${viewMode === 'list' ? 'list' : 'grid'}`}>
            {filteredSortedReels.map((reel) => (
              <ReelCard
                key={reel.id}
                reel={reel}
                onOpen={openModal}
                onGenerate={(id) => handleGenerate(id, false)}
                onRegenerate={(id) => handleGenerate(id, true)}
                viewMode={viewMode}
                isBusy={Boolean(busyReels[reel.id])}
              />
            ))}
          </div>
        )}

        <PaginationBar
          page={pagination.page || page}
          totalPages={pagination.total_pages || 1}
          onPageChange={onPageChange}
        />
      </>
    )
  }

  return (
    <AppShell
      history={history}
      activeUsername={username || ''}
      currentUser={user}
      onSearch={searchProfile}
      searching={searching}
      onLogout={logoutUser}
    >
      <div className="page-panel">
        {renderContent()}
      </div>

      <ReelDetailModal
        reels={filteredSortedReels}
        index={modalIndex}
        open={modalOpen}
        onClose={closeModal}
        onPrev={goPrevModal}
        onNext={goNextModal}
        initialTab={modalTab}
      />
    </AppShell>
  )
}

