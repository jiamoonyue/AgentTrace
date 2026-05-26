import { useState, useMemo, useCallback } from 'react'
import {
  ReactFlow,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import TimelineSlider from './TimelineSlider'

// ── 阶段对应的颜色 ──────────────────────────────────────

const PHASE_COLORS = {
  reasoning:  { bg: '#1e3a5f', border: '#3b82f6', label: 'R', name: '思考' },
  acting:     { bg: '#14532d', border: '#22c55e', label: 'A', name: '行动' },
  observing:  { bg: '#713f12', border: '#eab308', label: 'O', name: '观察' },
  evaluating: { bg: '#3b0764', border: '#a855f7', label: 'E', name: '评估' },
}

// ── 自定义节点 ──────────────────────────────────────────

function StepNode({ data, selected }) {
  const colors = PHASE_COLORS[data.phase] || PHASE_COLORS.reasoning

  return (
    <div
      className={`
        px-3 py-2 rounded-lg border-2 min-w-[140px] max-w-[200px]
        transition-all cursor-pointer
        ${selected ? 'ring-2 ring-white scale-105' : ''}
      `}
      style={{
        background: colors.bg,
        borderColor: colors.border,
        boxShadow: `0 0 12px ${colors.border}22`,
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: colors.border }} />
      <div className="flex items-center gap-2">
        <span
          className="inline-flex items-center justify-center w-5 h-5 rounded text-xs font-bold"
          style={{ background: colors.border, color: '#fff' }}
        >
          {colors.label}
        </span>
        <span className="text-xs text-gray-300">{colors.name}</span>
      </div>
      {data.toolName && (
        <div className="text-xs text-gray-400 mt-1 font-mono truncate">
          {data.toolName}
        </div>
      )}
      {data.tokenUsed > 0 && (
        <div className="text-xs text-gray-500 mt-0.5">
          {data.tokenUsed} tokens
        </div>
      )}
      <Handle type="source" position={Position.Right} style={{ background: colors.border }} />
    </div>
  )
}

const nodeTypes = { stepNode: StepNode }

// ── 将 Trace 转为 ReactFlow 数据 ────────────────────────

function buildFlow(trace) {
  if (!trace?.steps?.length) return { nodes: [], edges: [] }

  const H_SPACING = 200  // 节点水平间距
  const V_WRAP = 4       // 每行 4 个节点后换行

  const nodes = trace.steps.map((step, i) => {
    const colors = PHASE_COLORS[step.phase] || PHASE_COLORS.reasoning
    const row = Math.floor(i / V_WRAP)
    const col = i % V_WRAP

    return {
      id: step.id,
      type: 'stepNode',
      position: { x: col * H_SPACING, y: row * 120 },
      data: {
        phase: step.phase,
        sequence: step.sequence,
        toolName: step.action?.tool_name || step.decision?.chosen_tool || null,
        tokenUsed: step.token_used,
        label: `${colors.label}${step.sequence}`,
      },
    }
  })

  const edges = []
  for (let i = 1; i < nodes.length; i++) {
    edges.push({
      id: `e_${nodes[i - 1].id}_${nodes[i].id}`,
      source: nodes[i - 1].id,
      target: nodes[i].id,
      animated: true,
      style: { stroke: '#475569', strokeWidth: 2 },
    })
  }

  return { nodes, edges }
}

// ── 组件 ────────────────────────────────────────────────

export default function DecisionTree({ trace, onStepClick, selectedStepId, onDiagnose, diagnosis, diagnosing }) {
  const initialFlow = useMemo(() => buildFlow(trace), [trace])
  const [nodes, setNodes, onNodesChange] = useNodesState(initialFlow.nodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialFlow.edges)
  const [timelineIndex, setTimelineIndex] = useState(trace.steps.length - 1)

  // 当 trace 变化时更新
  useMemo(() => {
    setNodes(initialFlow.nodes)
    setEdges(initialFlow.edges)
    setTimelineIndex(trace.steps.length - 1)
  }, [trace.id])

  const onNodeClick = useCallback((_, node) => {
    const step = trace.steps.find(s => s.id === node.id)
    if (step) onStepClick(step)
  }, [trace, onStepClick])

  const onTimelineChange = useCallback((index) => {
    setTimelineIndex(index)
    // 自动选中当前回放的步骤
    const step = trace.steps[index]
    if (step) onStepClick(step)
  }, [trace, onStepClick])

  // 高亮选中的节点, 灰度未来的节点
  const styledNodes = nodes.map((n, i) => ({
    ...n,
    data: { ...n.data, selected: n.id === selectedStepId },
    style: {
      ...n.style,
      opacity: i <= timelineIndex ? 1 : 0.25,
      transition: 'opacity 0.3s',
    },
  }))

  const futureEdges = edges.map((e, i) => ({
    ...e,
    style: {
      ...e.style,
      opacity: i < timelineIndex ? 1 : 0.15,
      transition: 'opacity 0.3s',
    },
    animated: i < timelineIndex,
  }))

  return (
    <div className="h-full w-full">
      {/* 顶部信息条 + 诊断按钮 */}
      <div className="px-4 py-2 border-b border-gray-800 flex items-center gap-3 text-xs text-gray-400 flex-wrap">
        <span>Agent: <b className="text-blue-400">{trace.agent_name}</b></span>
        <span>Model: <b className="text-gray-200">{trace.model}</b></span>
        <span>路径: <b className="text-green-400 font-mono">{trace.decision_path || '无数据'}</b></span>
        <span>工具: <b className="text-yellow-400">{trace.tools_called?.join(', ') || '无'}</b></span>
        <span>Token: <b className="text-white">{trace.total_tokens}</b></span>
        <div className="flex-1" />
        <button
          onClick={onDiagnose}
          disabled={diagnosing}
          className="px-3 py-1 rounded bg-purple-700 hover:bg-purple-600 disabled:opacity-50
                     text-white text-xs font-medium transition-colors"
        >
          {diagnosing ? '诊断中...' : 'AI 诊断'}
        </button>
        {diagnosis && !diagnosis.error && (
          <span className={`px-2 py-0.5 rounded font-bold ${
            diagnosis.analysis?.summary?.health === 'healthy' ? 'bg-green-900 text-green-400' :
            diagnosis.analysis?.summary?.health === 'warning' ? 'bg-yellow-900 text-yellow-400' :
            'bg-red-900 text-red-400'
          }`}>
            {diagnosis.analysis?.summary?.health?.toUpperCase()}
            {diagnosis.llm_report?.score != null && ` ${diagnosis.llm_report.score}/100`}
          </span>
        )}
        {diagnosis?.error && (
          <span className="text-red-400">诊断失败: {diagnosis.error}</span>
        )}
      </div>

      {/* 诊断结果面板 */}
      {diagnosis && !diagnosis.error && diagnosis.analysis?.issues?.length > 0 && (
        <div className="px-4 py-2 border-b border-gray-800 bg-gray-900/50 max-h-32 overflow-y-auto">
          <div className="text-xs text-gray-500 mb-1">
            {diagnosis.llm_report?.diagnosis || `发现 ${diagnosis.analysis.summary.issue_count} 个问题`}
          </div>
          <div className="flex gap-2 flex-wrap">
            {diagnosis.analysis.issues.map((issue, i) => (
              <span key={i} className={`px-2 py-0.5 rounded text-xs ${
                issue.severity === 'critical' || issue.severity === 'high'
                  ? 'bg-red-900/50 text-red-300' :
                issue.severity === 'medium'
                  ? 'bg-yellow-900/50 text-yellow-300' :
                  'bg-gray-800 text-gray-400'
              }`}>
                {issue.type}: {issue.description.slice(0, 50)}...
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 决策树 */}
      <div className="h-[calc(100%-41px)]">
        <ReactFlow
          nodes={styledNodes}
          edges={futureEdges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.3 }}
          attributionPosition="bottom-right"
        >
          {/* 图例 */}
          <div className="absolute top-3 right-3 bg-gray-900/90 rounded-lg p-2 border border-gray-700 text-xs z-10">
            <div className="text-gray-400 mb-1">图例</div>
            {Object.entries(PHASE_COLORS).map(([key, c]) => (
              <div key={key} className="flex items-center gap-1.5 mb-0.5">
                <span className="w-3 h-3 rounded" style={{ background: c.border }} />
                <span className="text-gray-300">{c.label} = {c.name}</span>
              </div>
            ))}
          </div>
        </ReactFlow>
      </div>

      {/* 时间线回放 */}
      <TimelineSlider
        steps={trace.steps}
        currentStep={timelineIndex}
        onStepChange={onTimelineChange}
      />
    </div>
  )
}
