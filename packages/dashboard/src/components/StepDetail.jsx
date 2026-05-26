const PHASE_NAMES = {
  reasoning: '思考',
  acting: '行动',
  observing: '观察',
  evaluating: '评估',
}

export default function StepDetail({ step }) {
  if (!step) {
    return (
      <div className="h-full flex items-center justify-center text-gray-600 text-sm p-4">
        <p className="text-center">
          点击决策树中的节点<br />查看详情
        </p>
      </div>
    )
  }

  const phaseName = PHASE_NAMES[step.phase] || step.phase
  const d = step.decision
  const a = step.action

  return (
    <div className="p-4 text-sm">
      <h3 className="text-base font-bold text-gray-200 mb-3">
        [{step.sequence}] {phaseName}
      </h3>

      {/* 基本信息 */}
      <div className="grid grid-cols-2 gap-2 mb-4 text-xs">
        <div className="bg-gray-800 rounded p-2">
          <div className="text-gray-500">Token</div>
          <div className="text-white font-mono">{step.token_used}</div>
        </div>
        <div className="bg-gray-800 rounded p-2">
          <div className="text-gray-500">时间</div>
          <div className="text-white font-mono text-[11px]">
            {new Date(step.timestamp).toLocaleTimeString('zh-CN')}
          </div>
        </div>
      </div>

      {/* Reasoning 详情 */}
      {d && (
        <div className="mb-4">
          <Section label="思考内容">
            <TextBlock text={d.thought} />
          </Section>

          {d.chosen_tool && (
            <Section label="选择工具">
              <code className="text-green-400 bg-gray-800 px-1.5 py-0.5 rounded text-xs">
                {d.chosen_tool}
              </code>
            </Section>
          )}

          {d.tool_candidates?.length > 0 && (
            <Section label="候选工具">
              {d.tool_candidates.map((tc, i) => (
                <div key={i} className="flex justify-between text-xs mb-0.5">
                  <span className="text-gray-300">{tc.name}</span>
                  <span className="text-gray-500">评分: {tc.score}</span>
                </div>
              ))}
            </Section>
          )}

          {d.rejected_alternatives?.length > 0 && (
            <Section label="被否决方案">
              {d.rejected_alternatives.map((alt, i) => (
                <div key={i} className="text-red-400/70 text-xs">✕ {alt}</div>
              ))}
            </Section>
          )}

          {d.decision_rationale && (
            <Section label="决策理由">
              <TextBlock text={d.decision_rationale} />
            </Section>
          )}
        </div>
      )}

      {/* Acting 详情 */}
      {a && (
        <div className="mb-4">
          <Section label="工具调用">
            <code className="text-green-400 bg-gray-800 px-1.5 py-0.5 rounded text-xs">
              {a.tool_name}
            </code>
          </Section>

          <Section label="耗时">
            <span className="text-white font-mono">{a.latency_ms}ms</span>
          </Section>

          <Section label="参数">
            <pre className="text-xs text-gray-300 bg-gray-800 rounded p-2 overflow-x-auto">
              {JSON.stringify(a.params, null, 2)}
            </pre>
          </Section>

          {a.result_snippet && (
            <Section label="返回值">
              <TextBlock text={a.result_snippet} maxHeight="max-h-32" />
            </Section>
          )}

          {a.error && (
            <Section label="错误">
              <div className="text-red-400 text-xs bg-red-900/30 rounded p-2">{a.error}</div>
            </Section>
          )}
        </div>
      )}

      {/* Observing 详情 */}
      {step.observation && (
        <Section label="观察结果">
          <TextBlock text={step.observation} />
        </Section>
      )}

      {/* Evaluating 详情 */}
      {step.confidence != null && (
        <Section label="置信度">
          <div className="flex items-center gap-2">
            <div className="flex-1 bg-gray-800 rounded-full h-2">
              <div
                className="h-2 rounded-full transition-all"
                style={{
                  width: `${(step.confidence * 100).toFixed(0)}%`,
                  background: step.confidence > 0.8 ? '#22c55e' :
                              step.confidence > 0.5 ? '#eab308' : '#ef4444'
                }}
              />
            </div>
            <span className="text-white font-mono text-xs">
              {(step.confidence * 100).toFixed(0)}%
            </span>
          </div>
        </Section>
      )}
    </div>
  )
}

// ── 小组件 ──────────────────────────────────────────────

function Section({ label, children }) {
  return (
    <div className="mb-2">
      <div className="text-xs text-gray-500 mb-0.5">{label}</div>
      {children}
    </div>
  )
}

function TextBlock({ text, maxHeight = 'max-h-48' }) {
  if (!text) return null
  return (
    <div className={`text-xs text-gray-300 bg-gray-800 rounded p-2 overflow-y-auto ${maxHeight} whitespace-pre-wrap break-all`}>
      {text}
    </div>
  )
}
