import { useState, useEffect, useCallback } from 'react'
import { fetchTraces, fetchTrace, fetchStats, fetchDiagnosis } from './api'
import TraceList from './components/TraceList'
import DecisionTree from './components/DecisionTree'
import StepDetail from './components/StepDetail'

export default function App() {
  const [traces, setTraces] = useState({ items: [], total: 0 })
  const [selectedTrace, setSelectedTrace] = useState(null)  // 完整 Trace
  const [selectedStep, setSelectedStep] = useState(null)    // 当前查看的 Step
  const [diagnosis, setDiagnosis] = useState(null)          // 诊断结果
  const [diagnosing, setDiagnosing] = useState(false)       // 诊断中
  const [stats, setStats] = useState(null)
  const [filter, setFilter] = useState({ agentName: '', offset: 0, limit: 50 })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // 加载 Trace 列表
  const loadTraces = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchTraces(filter)
      setTraces(data)
    } catch (e) {
      setError('无法连接 Engine 服务，请确认已启动: python -m agenttrace_engine.api.server')
    } finally {
      setLoading(false)
    }
  }, [filter])

  // 加载统计数据
  const loadStats = useCallback(async () => {
    try {
      const data = await fetchStats()
      setStats(data)
    } catch { /* Engine 未启动时静默 */ }
  }, [])

  useEffect(() => { loadTraces(); loadStats() }, [loadTraces, loadStats])

  // 选中一条 Trace，加载完整数据
  const selectTrace = async (traceId) => {
    try {
      const trace = await fetchTrace(traceId)
      setSelectedTrace(trace)
      setSelectedStep(null)
      setDiagnosis(null)
    } catch (e) {
      console.error('加载 Trace 失败:', e)
    }
  }

  const runDiagnosis = async () => {
    if (!selectedTrace) return
    setDiagnosing(true)
    setDiagnosis(null)
    try {
      const result = await fetchDiagnosis(selectedTrace.id)
      setDiagnosis(result)
    } catch (e) {
      setDiagnosis({ error: String(e) })
    } finally {
      setDiagnosing(false)
    }
  }

  return (
    <div className="h-screen flex flex-col bg-gray-950 text-gray-100">
      {/* 顶栏 */}
      <header className="flex items-center justify-between px-4 py-2 border-b border-gray-800 bg-gray-900">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-blue-400">AgentTrace</h1>
          <span className="text-xs text-gray-500">Agent 决策调试器</span>
        </div>
        {stats && (
          <div className="flex gap-4 text-xs text-gray-400">
            <span>Traces: <b className="text-white">{stats.total_traces}</b></span>
            <span>Tokens: <b className="text-white">{stats.total_tokens?.toLocaleString()}</b></span>
            <span>Agents: <b className="text-white">{Object.keys(stats.agents || {}).length}</b></span>
          </div>
        )}
        {error && <div className="text-red-400 text-xs">{error}</div>}
      </header>

      {/* 主体三栏 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左栏: Trace 列表 */}
        <aside className="w-72 border-r border-gray-800 flex flex-col bg-gray-900">
          <TraceList
            traces={traces}
            filter={filter}
            onFilterChange={setFilter}
            onSelect={selectTrace}
            selectedId={selectedTrace?.id}
            loading={loading}
          />
        </aside>

        {/* 中栏: 决策树 */}
        <main className="flex-1 bg-gray-950">
          {selectedTrace ? (
            <DecisionTree
              trace={selectedTrace}
              onStepClick={setSelectedStep}
              selectedStepId={selectedStep?.id}
              onDiagnose={runDiagnosis}
              diagnosis={diagnosis}
              diagnosing={diagnosing}
            />
          ) : (
            <div className="h-full flex items-center justify-center text-gray-600">
              <div className="text-center">
                <div className="text-4xl mb-3">◈</div>
                <p>选择左侧一条 Trace 查看决策树</p>
                <p className="text-sm mt-1">或运行示例 Agent 产生新的 Trace</p>
              </div>
            </div>
          )}
        </main>

        {/* 右栏: 步骤详情 */}
        <aside className="w-80 border-l border-gray-800 bg-gray-900 overflow-y-auto">
          <StepDetail step={selectedStep} />
        </aside>
      </div>
    </div>
  )
}
