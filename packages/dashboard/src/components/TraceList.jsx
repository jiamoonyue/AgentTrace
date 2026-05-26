export default function TraceList({ traces, filter, onFilterChange, onSelect, selectedId, loading }) {
  const { items, total } = traces
  const { agentName, offset, limit } = filter

  const pages = Math.ceil(total / limit)
  const currentPage = Math.floor(offset / limit) + 1

  return (
    <>
      {/* 筛选 */}
      <div className="p-3 border-b border-gray-800">
        <input
          type="text"
          placeholder="筛选 Agent 名称..."
          value={agentName}
          onChange={(e) => onFilterChange({ ...filter, agentName: e.target.value, offset: 0 })}
          className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm
                     text-gray-200 placeholder-gray-500 focus:outline-none focus:border-blue-500"
        />
      </div>

      {/* 列表 */}
      <div className="flex-1 overflow-y-auto">
        {loading && <div className="p-4 text-center text-gray-500 text-sm">加载中...</div>}

        {!loading && items.length === 0 && (
          <div className="p-4 text-center text-gray-600 text-sm">
            暂无 Trace，运行示例 Agent 产生数据
          </div>
        )}

        {items.map((t) => (
          <div
            key={t.id}
            onClick={() => onSelect(t.id)}
            className={`p-3 border-b border-gray-800/50 cursor-pointer hover:bg-gray-800/50
              transition-colors ${t.id === selectedId ? 'bg-blue-900/30 border-l-2 border-l-blue-500' : ''}`}
          >
            <div className="text-xs text-gray-400 flex justify-between">
              <span className="text-blue-400 font-mono">{t.agent_name}</span>
              <span>{new Date(t.start_time).toLocaleTimeString('zh-CN')}</span>
            </div>
            <div className="text-sm text-gray-300 mt-0.5 truncate">{t.task}</div>
            <div className="flex gap-2 mt-1 text-xs text-gray-500">
              <span>{t.step_count} 步</span>
              <span>{t.total_tokens} tokens</span>
              {t.tools_called && <span className="text-green-500">{t.tools_called}</span>}
            </div>
          </div>
        ))}
      </div>

      {/* 分页 */}
      {total > limit && (
        <div className="p-2 border-t border-gray-800 flex justify-between items-center text-xs text-gray-500">
          <button
            disabled={offset === 0}
            onClick={() => onFilterChange({ ...filter, offset: Math.max(0, offset - limit) })}
            className="px-2 py-1 rounded hover:bg-gray-800 disabled:opacity-30"
          >
            ← 上一页
          </button>
          <span>{currentPage} / {pages}</span>
          <button
            disabled={offset + limit >= total}
            onClick={() => onFilterChange({ ...filter, offset: offset + limit })}
            className="px-2 py-1 rounded hover:bg-gray-800 disabled:opacity-30"
          >
            下一页 →
          </button>
        </div>
      )}
    </>
  )
}
