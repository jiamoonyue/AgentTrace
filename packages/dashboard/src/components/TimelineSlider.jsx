/** 时间线回放滑块 —— 拖拽回放任一时刻的 Agent 决策。 */

const PHASE_COLORS = {
  reasoning:  '#3b82f6',
  acting:     '#22c55e',
  observing:  '#eab308',
  evaluating: '#a855f7',
}

const PHASE_LABELS = {
  reasoning: '思', acting: '行', observing: '观', evaluating: '评',
}

export default function TimelineSlider({ steps, currentStep, onStepChange }) {
  if (!steps?.length) return null

  const max = steps.length - 1
  const pct = max > 0 ? (currentStep / max) * 100 : 0

  return (
    <div className="border-t border-gray-800 bg-gray-900 px-4 py-2">
      {/* 步骤指示器 */}
      <div className="flex justify-between mb-1">
        {steps.map((step, i) => (
          <button
            key={step.id}
            onClick={() => onStepChange(i)}
            className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px]
              font-bold transition-all cursor-pointer border-2
              ${i <= currentStep ? 'border-current' : 'border-gray-700 opacity-40'}
            `}
            style={{
              background: i <= currentStep ? PHASE_COLORS[step.phase] + '33' : 'transparent',
              color: PHASE_COLORS[step.phase] || '#666',
            }}
            title={`[${step.sequence}] ${step.phase}`}
          >
            {PHASE_LABELS[step.phase] || '?'}
          </button>
        ))}
      </div>

      {/* 滑块 */}
      <div className="relative">
        <input
          type="range"
          min={0}
          max={max}
          value={currentStep}
          onChange={(e) => onStepChange(Number(e.target.value))}
          className="w-full h-2 rounded-full appearance-none cursor-pointer
                     bg-gray-800 accent-blue-500"
        />
        {/* 进度指示 */}
        <div className="flex justify-between text-[10px] text-gray-600 mt-0.5">
          <span>开始</span>
          <span>步骤 {currentStep + 1}/{steps.length}</span>
          <span>结束</span>
        </div>
      </div>
    </div>
  )
}
