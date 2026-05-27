# AgentTrace 面试知识点准备

> 本文档整理了 AgentTrace 项目中用到的核心技术知识点，
> 以"面试官可能怎么问 → 你怎么答"的形式组织。
> 适合求职：AI Agent 算法岗 / 开发岗

---

## 目录

- [一、Agent 基础概念](#一agent-基础概念)
- [二、Python 核心技术](#二python-核心技术)
- [三、后端架构](#三后端架构)
- [四、数据库设计](#四数据库设计)
- [五、前端可视化](#五前端可视化)
- [六、Debug Agent 与元 Agent](#六debug-agent-与元-agent)
- [七、工程实践与架构设计](#七工程实践与架构设计)
- [八、开放性问题](#八开放性问题)
- [九、写在简历上的描述](#九写在简历上的描述)

---

## 一、Agent 基础概念

### Q1: 什么是 AI Agent？和普通 LLM 调用有什么区别？

**答：**

LLM 调用是"一次性回答"——用户问什么，模型直接给答案。模型不知道的事会瞎编（幻觉）。

Agent 是"循环决策"——用户提问题后，Agent 循环执行"思考→行动→观察"，直到能给出可靠的答案。每步都可能调用外部工具（搜索、计算器、API）获取真实信息，不是凭空回答。

用代码对比这两者：

```
普通 LLM:
  用户说"查北京天气" → LLM 直接生成回答 → 可能瞎编

Agent:
  用户说"查北京天气" → 思考"需要天气API"
                      → 调天气API，拿到实时数据
                      → 观察"晴，28度"
                      → 回答用户 → 有数据支撑
```

**Agent 的核心价值**：用工具弥补 LLM 知识的局限性。LLM 不知道今天的天气，但它知道怎么调天气API。Agent 就是把这个能力串起来。

**和 RAG 的区别**：RAG 是被动的——用户问什么，你去文档里搜，把搜到的内容塞进上下文让 LLM 回答。Agent 是主动的——它自己决定什么时候需要搜、用什么工具搜、搜完之后怎么办。Agent 比 RAG 多了一个"决策层"。

---

### Q2: 什么是 ReAct 框架？你们的项目怎么用的？

**答：**

ReAct = Reasoning + Acting。2022 年 Google Brain 提出。核心思想是让 LLM 交替进行"推理"和"行动"，而不是一步生成答案。

标准 ReAct 有三阶段：
```
思考 (Thought) → 行动 (Action) → 观察 (Observation) → 重复...
```

我们在项目中做了两处扩展：

1. **加了第 4 阶段：评估 (Evaluating)**。每轮 ReAct 结束后，Agent 对自己的决策打个置信度 (0~1)。如果置信度一直低于 0.5，说明 prompt 或上下文有问题。
2. **每个阶段的数据都结构化保存**。不是简单的文本日志，而是有类型的字段——思考内容、候选工具、被否决方案、工具参数、耗时毫秒数、Token 数。这样机器可以自动分析，人可以通过 Dashboard 可视化查看。

**为什么选择 ReAct**：ReAct 是最简的 Agent 范式，每步只做一件事（要么思考、要么行动、要么观察），好调试、好追踪。其他范式如 Plan-and-Solve（先规划再执行）虽然更强大，但决策链路更长，更难调试。

---

### Q3: AgentTrace 解决的是什么问题？

**答：**

Agent 开发者的**调试困境**。传统软件出 bug 可以看日志定位到某行代码。但 Agent 的行为不由代码逻辑决定——同样的 prompt 两次执行可能做出不同决策。

Agent 开发者面临的典型问题：

| 问题 | 调试难度 |
|------|---------|
| "Agent 为什么调了 5 次搜索？" | 日志里只有调用记录，看不出重复模式 |
| "Agent 用了 A 工具而不是 B，为什么？" | 完全不知道，只记录"用了A"不记录"为什么不用B" |
| "花了 5000 Token，哪步最贵？" | 没有逐步记录 |
| "改了 prompt，效果变好了吗？" | 凭感觉，没有量化对比 |

AgentTrace 把 Agent 的每次执行变成一条完整的 **Trace**（轨迹），包含每一步的思考、工具调用、结果、耗时、Token。开发者打开 Dashboard 就能看到决策树，知道 Agent 在哪步出错、为什么出错。

类比：AgentTrace for Agents = Chrome DevTools for 网页。

---

## 二、Python 核心技术

### Q4: 装饰器是什么？`@trace_agent` 是怎么工作的？

**答：**

装饰器是 Python 的"函数替换"机制。写 `@trace_agent(name="bot")` 时，实际发生的是：

```
trace_agent(name="bot") 返回一个"装饰器函数"
这个装饰器函数接收原始函数，返回一个新的"包装函数"
原始函数的名字指向了这个包装函数
```

所以当你调用被装饰的函数时，实际执行的是包装函数。包装函数在"执行前"和"执行后"加了逻辑——执行前创建 Trace，执行后 finalize Trace。业务函数本身不需要知道 Trace 的存在。

**和 Java 注解的区别**：Java 注解是元数据，本身不做事，需要 Spring AOP 在运行时解析。Python 装饰器是可执行代码，函数定义完立刻替换，不依赖任何框架。

**`@functools.wraps` 的作用**：没有它，装饰后的函数名会变成 `wrapper`，原始的 `__name__` 和 `__doc__` 都丢了。调试时堆栈全显示 `wrapper`，找不出是哪个函数出问题。

**这个设计为什么好**：关注点分离。业务代码只关心业务逻辑，追踪逻辑由装饰器统一处理。不用在每个 Agent 函数头尾写 20 行样板代码。

---

### Q5: `contextvars` 是干什么的？为什么不用全局变量？

**答：**

`contextvars` 是 Python 标准库提供的"上下文变量"。可以理解成**每个协程/线程自带的一个专属背包**——你在一个地方往背包里放东西，在另一个地方可以不传参直接取出来，而且不同协程之间的背包互相隔离。

**解决的问题**：`@trace_agent` 在外层创建了 Trace 对象，但 `reason()`、`act()`、`observe()` 这些辅助函数在里层也需要用到这个 Trace。怎么传递？

我们对比了三个方案：

| 方案 | 问题 |
|------|------|
| **传参** | 函数签名变了。假如你有 10 个 Agent、每个被 5 个地方调用，加一个参数就要改 50 个调用点。侵入性强 |
| **全局变量** | 两个请求同时进来时，后面的覆盖前面的。A 的 Trace 写到一半被 B 覆盖了，数据串了 |
| **contextvars** | 每个协程有自己独立的一份。A 取到 A 的，B 取到 B 的，互不干扰。也不用改函数签名 |

**和 Java ThreadLocal 的关系**：思路完全一样。Java 用 `ThreadLocal` 实现每个线程的私有存储，Python 的 `contextvars` 不仅支持线程隔离，还支持协程隔离。

**为什么还调用 `reset(token)`**：如果不恢复旧值，协程被回收到协程池后，下一个请求复用这个协程时会拿到上一个请求的旧 Trace。

---

### Q6: 上下文管理器是什么？`timed_act` 为什么用 `with` 语句？

**答：**

上下文管理器是 Python 的 `with` 语句背后的机制。核心概念是"进入时做某事，退出时自动做另一件事"。

最常见的例子是 `with open("file") as f`——进入时打开文件，退出时自动关闭（就算中间抛异常也会关闭）。

**为什么 `timed_act` 要用 `with`**：工具调用的前后有固定的模式——开始计时 → 执行工具 → 结束计时 → 记录结果。如果用 `try/finally` 手动处理，每个工具调用多 5 行代码。如果用 `with`，自动变成 3 行，而且**保证无论成功还是失败，结束计时和记录一定会执行**。

`__exit__` 的返回值：
- `False`：异常继续传播（我们用这个）
- `True`：吞掉异常（几乎永远不要这样做）

`__exit__` 收到三个异常参数（`exc_type`、`exc_val`、`exc_tb`），没异常时都是 `None`。我们利用这点：如果工具抛异常了，自动把错误信息记录到 Action 的 error 字段。

---

### Q7: 为什么用 Pydantic 而不是 dict 或 dataclass？

**答：**

Pydantic 提供了三种 dict 和 dataclass 没有的能力：

1. **类型校验前置**。写 `phase: StepPhase`，如果传入 `"reasonning"`（拼错了），Pydantic 在创建对象时就报 `ValidationError`，不会等到存数据库时才炸。用 dict 的话，这种 bug 要到运行时才暴露。
2. **嵌套模型自动序列化**。`Trace.model_dump_json()` 一行把整个对象（包含嵌套的 TraceStep、Decision、Action）变成 JSON，直接可以作为 API 响应。dict 需要手动递归处理。dataclass 也需要额外写序列化逻辑。
3. **IDE 友好**。`step.decision.thought` 全程自动补全。dict 的 `step["decision"]["thought"]` 全靠开发者记忆字段名。

在 AgentTrace 中，Pydantic 贯穿全链路：SDK 采集数据、Engine 接收数据、API 返回数据，**同一套数据模型从头用到尾**，不需要在每层写转换代码。这大大减少了 bug 概率。

---

### Q8: 枚举（Enum）有什么用？为什么 `StepPhase` 要用枚举？

**答：**

枚举的作用是**把一组固定的取值变成类型安全的常量**。

Agent 的 ReAct 阶段只有 4 种：思考、行动、观察、评估。如果用字符串表示：

```python
# 用字符串的问题
phase = "reasonning"  # 拼写错误，Python 不报错
... 500 行之后 ...
if phase == "reasoning":  # False！因为上面拼错了，但不会发现
    ...
```

这整类 bug 有一个专门的名称：**字符串常量散落（Stringly Typed）**。枚举从根源上消灭它：

```python
phase = StepPhase.REASONNING  # 立刻报 AttributeError
if phase == StepPhase.REASONING:  # 永远正确
```

更重要的价值在 API 层面。用字符串的话，后端 "reasoning" 和前端 "reasoning" 必须手动保持一致，写错一个字母就对接不上。枚举只需要定义一次，前端后端都用同一个序列化/反序列化逻辑。

---

## 三、后端架构

### Q9: 你们为什么选 FastAPI？

**答：**

最直接的原因是**模型兼容性**。我们的 SDK 用 Pydantic 定义了数据模型，FastAPI 也基于 Pydantic——请求体自动校验，响应体自动序列化。

这意味着：SDK 定义的 Trace 类，在 Engine 端直接作为 API 的请求类型，不需要写任何"JSON 转对象"的胶水代码。

第二个原因是**自动生成文档**。`http://localhost:8000/docs` 提供了交互式 Swagger 文档，开发和测试时可以在这个页面直接调 API，不需要用 Postman 或 curl。

---

### Q10: 列表查询为什么返回 `{total, items}` 而不是纯数组？

**答：**

这是 REST API 的分页设计规范。纯数组不告诉前端"总共多少条"——前端不知道有没有下一页。

```json
// 返回数组
[item1, item2, item3]

// 前端问题: 总共 3 条还是更多？下一页在哪？
```

```json
// 返回对象
{"total": 100, "offset": 0, "limit": 20, "items": [...]}

// 前端: 总共 100 条，当前 0-19，如果 offset+limit < total 就显示"下一页"
```

**为什么先 `count()` 再查数据**：分页查询需要两步。先 count 获取总数（用于前端计算总页数），再 offset+limit 获取当前页。如果不先 count，前端只能通过"下一页有没有数据"来推断是否最后一页，这种方式不够精确。

---

### Q11: 路由顺序有什么讲究？`/{trace_id}` 和 `/stats/summary` 的注册顺序为什么重要？

**答：**

FastAPI 按路由注册顺序匹配。`/{trace_id}` 是一个通配路由，会匹配任何 `/api/traces/xxx` 格式的路径。如果先注册它，`/api/traces/stats/summary` 的请求进来时，`stats` 会被当做一个 `trace_id` 去数据库查询，找不到就返回 404。

正确做法：**先注册具体路径，再注册通配路径**。

```python
# 先注册具体路径
@router.get("/stats/summary")   # 放在最前面
@router.get("/compare")          # 具体路径

# 再注册通配路径
@router.get("/{trace_id}")      # 放在最后面
```

这是 FastAPI 的常见陷阱，也是面试官喜欢问的点。

---

## 四、数据库设计

### Q12: Decision 和 Action 为什么存为 JSON 列，而不是拆成单独的表？

**答：**

这是一个**范式化 vs 反范式化**的决策。

理论上应该拆表：Decision 一张表、Action 一张表、Observatioin 一张表。这样可以按类型独立查询。

但实际不需要，原因：**Decision 和 Action 总是和它的 TraceStep 一起读写**。没有"单独查所有 Decision"或者"跨 Steps 查 Action"的场景。拆表只会增加 JOIN 的开销，没有任何收益。

而且 TraceStep 和 Decision/Action 是**严格的 1:1 关系**——一个 TraceStep 要么有 Decision、要么有 Action、要么有 Observation，不会同时有多个。

所以选择 JSON 列策略：
- 查询快：一次查表就能拿到完整的步骤数据
- 代码简单：不需要 JOIN，不需要拼接
- 扩展性好：如果要加新字段，直接加 JSON 里

这是"**根据实际查询场景决定存储结构**"的典型例子。不盲目追求范式化，也不全部用 JSON。

---

### Q13: SQLite 够用吗？什么时候需要换成 PostgreSQL？

**答：**

SQLite 适用于：
- 单机开发/测试
- 个人使用
- 少量 Trace 数据（几千条）

当单机不够用时，需要换成 PostgreSQL：
- 多人同时读写
- 海量数据
- 高可用要求

架构上已经做了兼容。Repository 模式把所有数据库操作封装在一个类里，换数据库只需要改一下连接 URL，API 路由层的代码完全不动：

```python
# SQLite
TraceRepository("sqlite:///agenttrace.db")

# PostgreSQL（注释掉上行，取消这行注释）
TraceRepository("postgresql://user:pass@host:5432/agenttrace")
```

---

## 五、前端可视化

### Q14: 为什么用决策树（而不是表格或原始 JSON）来展示 Trace？

**答：**

因为**三种信息要同时展示**：

1. **时序**——步骤的先后顺序
2. **阶段分类**——这一步是在思考、行动还是观察
3. **关联关系**——哪次行动对应哪次观察

表格能展示 1 和 2，但 3（关联关系）需要用户自己去匹配序号。JSON 原始数据太"密"了，没有视觉分层。

决策树用颜色区分阶段（蓝色=思考、绿色=行动、黄色=观察），用箭头表示步骤流向，用位置表示时间顺序。用户一眼就能看完整个 Agent 的执行过程，找到异常步骤。

而且决策树是可交互的：点击节点看详情、拖拽移动位置、缩放看整体或局部。这些是静态表格/JSON 做不到的。

**颜色编码为什么这么设计**：
- 蓝色（思考）= 冷静、分析中
- 绿色（行动）= 执行、操作中
- 黄色（观察）= 等待、接收中
- 紫色（评估）= 反思、总结中

颜色有情绪暗示，让用户不用读文字也能感知当前阶段。

---

### Q15: 时间线回放是怎么实现的？为什么需要它？

**答：**

时间线回放就是把 Agent 的执行过程变成一个"视频"。用户拖动滑块，选择任何时间点，该点之前的所有步骤高亮显示，之后的步骤灰度淡化。

**实现原理**：
- 滑块位置决定一个"当前步骤索引"
- 所有节点根据索引判断：如果序号 <= 当前索引，不透明度 100%；否则 25%
- 当滑块移动时触发重渲染，节点透明度有 0.3 秒的过渡动画（CSS transition）

**为什么需要它**：
- Agent 的执行是时间流，用户理解也需要时间流——不是一次性看全部
- 配合右侧详情面板，用户拖到第 3 步，右侧就展示第 3 步的思考/行动细节
- 调试"Agent 从哪步开始出错的"时，可以逐帧播放直到问题出现

---

## 六、Debug Agent 与元 Agent

### Q16: 什么是"元 Agent"？Debug Agent 和普通 Agent 有什么区别？

**答：**

"元 Agent"是指**一个用来分析其他 Agent 的 Agent**。

普通人眼中的 Agent：帮用户查天气、订机票、写报告。

Debug Agent 的"工作"是分析另一个 Agent 的 Trace，找出它的问题。Debug Agent 的 "用户" 是开发者，不是最终用户。

**Debug Agent 的分层设计**：

- **算法层**：纯规则检测。不需要 LLM，毫秒级返回。检测 6 种模式：重复调用、工具失败、低置信度、缺少兜底策略、Token 浪费、高延迟。
- **LLM 层**：把算法检测到的问题 + Trace 原始数据发给 DeepSeek，让 LLM 生成诊断报告（根因分析、修复建议、综合评分）。

为什么分两层？因为不是每次都需要 LLM。纯算法分析 1ms 出结果，告诉你"有 3 个问题"。如果你只想知道"有没有问题"，算法就够了。只有当你需要"怎么修"时才调 LLM（慢、花钱）。

**6 种自动检测模式**：

| 模式 | 检测规则 | 为什么是有问题的 |
|------|---------|----------------|
| 重复调用 | 同一工具连续 3+ 次 | 死循环，Agent 卡住了 |
| 工具失败 | action.error 不为空 | 工具不可用或参数错误 |
| 低置信度 | confidence < 0.5 | Agent 不确定自己在做什么 |
| 缺少兜底 | 失败后没有替代方案 | 鲁棒性差，一次失败就全剧终 |
| Token 浪费 | 单步 > 总 Token 的 50% | prompt 太长或上下文堆积 |
| 高延迟 | > 2s 或 > 平均的 3 倍 | 工具性能问题 |

---

### Q17: Debug Agent 的输出是什么样的？怎么验证它准不准？

**答：**

Debug Agent 输出两样东西：

**1. 算法分析结果**（结构化 JSON）

```json
{
  "trace_id": "trace_xxx",
  "summary": {
    "health": "warning",   // healthy / warning / critical
    "issue_count": 3
  },
  "issues": [
    {"type": "repeated_calls", "severity": "high", "tool": "web_search", ...},
    {"type": "tool_failure", "severity": "high", "tool": "external_api", ...},
    {"type": "low_confidence", "severity": "medium", ...}
  ]
}
```

**2. LLM 诊断报告**

```json
{
  "diagnosis": "Agent 陷入了 web_search 死循环，连续调用 4 次相同工具",
  "severity": "critical",
  "score": 35,
  "root_causes": ["缺少停止条件"],
  "prompt_suggestions": ["在 system prompt 添加: '如果连续 3 次搜索相似结果，停止并汇总'"],
  "architecture_suggestions": ["为工具添加 max_retries 参数"]
}
```

**怎么验证准确性**：我们构造了一条已知问题的 Trace（连续 4 次调 web_search + 工具失败 + 低置信度），跑算法分析。结果全部 5 个问题都被检测到，没有漏报。LLM 诊断的评分为 35/100，也与预期一致（严重异常）。

---

## 七、工程实践与架构设计

### Q18: 你们的项目分层是怎么设计的？为什么这么分？

**答：**

三层架构，每层职责单一：

```
SDK 层     —— 数据采集。驻留在 Agent 进程内，不关心数据怎么存
Engine 层  —— 存储与查询。独立服务，不关心数据怎么来的
Dashboard 层 —— 可视化展示。浏览器端，不关心数据怎么处理的
```

**为什么分层**：

1. **解耦部署**。SDK 在 Agent 进程里跑，Engine 在服务器上跑。Agent 进程挂了不影响已有 Traces，Engine 挂了不影响 Agent 继续执行。
2. **技术栈分离**。SDK 是 Python，Engine 是 FastAPI，Dashboard 是 React。每层可以用最适合的语言和技术，不用妥协。
3. **易测试**。每层可以单独测试。SDK 的单元测试不需要启动 Engine，Engine 的接口测试不需要启动 Dashboard。

**层间通信**：SDK → Engine 通过 HTTP（`POST /api/traces`）。Engine → Dashboard 通过 HTTP（`GET /api/traces/...`）。每次通信的传输对象就是 Pydantic 序列化后的 JSON。

---

### Q19: 依赖注入在项目里怎么用的？为什么需要它？

**答：**

具体的例子是 `LLMTracer`。它不直接创建 LLM 客户端，而是通过构造函数接收一个 `chat_fn` 函数：

```python
class LLMTracer:
    def __init__(self, chat_fn):
        self._chat = chat_fn  # chat_fn = (messages, tools) → response
```

**好处**：LLMTracer 不需要知道调用的是 DeepSeek、OpenAI、Claude 还是本地模型。它只关心一件事——调用 `chat_fn` 并记录结果。今天用 DeepSeek，注入 `client.chat_with_tools`；明天换 Claude，注入 `claude_client`；测试时注入一个 mock 函数。LLMTracer 本身一行代码不用改。

**和硬编码的区别**：

```python
# 硬编码——换模型要改代码
class LLMTracer:
    def step(self, msg, tools):
        response = deepseek_client.chat(msg, tools)  # 写死了
        ...

# 依赖注入——换模型不碰代码
class LLMTracer:
    def step(self, msg, tools):
        response = self._chat(msg, tools)  # 谁传的, 调谁
        ...
```

---

### Q20: `LLMTracer` 和 `timed_act` 的关系是什么？

**答：**

**`LLMTracer` 是高级封装**，**`timed_act` + `reason()` 是底层基础**。

```
LLMTracer.step() → 内部调 chat_fn 调用 LLM
                 → 自动调 reason()（记录思考 + Token 数）
                 → 返回 LLM 响应

LLMTracer.execute() → 内部调用工具函数
                    → 用 timed_act 自动计时
                    → 自动调 observe()（记录观察结果）
                    → 返回工具结果
```

所以 `LLMTracer` 是基于 `reason()` + `timed_act` + `observe()` 这三个底层函数的自动版本。底层函数给你完全的控制权，`LLMTracer` 给你开发效率。

如果你只需要简单场景，用 `LLMTracer` 一步完成。如果你需要自定义逻辑（比如在执行工具前后加自己的处理），用底层函数手动组装。

---

## 八、开放性问题

### Q21: 这个项目最难的挑战是什么？

**答：**

最难的挑战是**数据模型的设计**——怎么把 Agent 的决策过程变成一个精确、完整、可扩展的数据结构。

不是写代码难，是**设计什么"值得记"什么"不值得记"**。

我们一开始只记录了"调了什么工具"和"结果是什么"，后来发现这对调试完全不够。比如 Agent 调用了 A 工具而不是 B 工具——你不知道它考虑过 B 吗？考虑了但为什么没选？这些信息在定位"prompt 设计是否合理"时至关重要。

所以我们增加了 `tool_candidates`（候选工具列表）和 `rejected_alternatives`（被否决方案的文本）。这两个字段让调试从"知道 Agent 选了什么"升级到"知道 Agent 的完整思考过程"。

`rejected_alternatives` 特别有价值——它是自由文本，没有固定格式。Agent 可能 reject 另一个工具、可能 reject 一种策略、也可能 reject"直接回答"。这种非结构化的信息不是用来量化的，而是用来**做定性分析**的。当 Agent 出问题时，你读一下它否决了什么方案，通常比看它选了什么更容易定位根因。

---

### Q22: 如果重新做这个项目，会怎么做不同的？

**答：**

1. **先做 WebSocket 再做 HTTP**。现在 Trace 是 Agent 跑完后一次性 POST 到 Engine 的。如果 Agent 跑一个长时间任务（比如 10 分钟），用户要等任务结束后才能在 Dashboard 看到数据。如果用 WebSocket，每步执行结果实时推送到 Dashboard，用户可以实时观察 Agent 的决策过程。

2. **LangChain 回调的优先级更高**。我们一开始面向"手写 Agent"的场景，后来才做了 LangChain 回调。但实际上很多团队用 LangChain/LangGraph 开发 Agent，如果他们可以直接 `pip install` 加一个回调参数就接入，比先学 `@trace_agent` 再改造代码要友好得多。

3. **默认端口冲突处理**。开发中多次遇到端口占用导致服务启动失败。应该加一个端口检测逻辑——启动时检测 8000/3000 是否被占用，被占用时自动尝试下一个端口或者提示用户。

---

### Q23: 你怎么保证这个工具对开发者是有用的？

**答：**

验证方法就是**自己先踩坑**。我们先用 `travel_agent_demo.py` 反复跑，把每次的 Trace 发到 Engine，在 Dashboard 上观察。

第一次跑完看到 Trace 时，发现 `total_tokens: 0`——因为 LLM 调用的 Token 数根本没有被记录。这就是 Debug Agent 的起点：你自己是第一个用户，如果你看到 Trace 觉得信息不够，说明其他人也会觉得不够。

这是"**吃自己的狗粮**"（Dogfooding）原则。我们至少迭代了三次数据结构：

- v0：只有 thought 和 action，没有候选方案 → 调试时总是猜"为什么选这个"
- v1：加了 tool_candidates → 知道选了啥、还考虑过啥
- v2：加了 rejected_alternatives → 知道否决了什么方案

每次迭代的动力都是"我自己调试 Agent 时觉得缺了某个信息"。

---

### Q24: 生产环境要用需要加什么？

**答：**

1. **认证**。当前没有任何权限控制，谁都能调 API。生产环境需要 API Key 认证。
2. **数据保留策略**。Trace 数据随着时间积累会越来越多。需要设定保留期限（比如 30 天），自动清理旧数据。
3. **告警机制**。Debug Agent 目前需要手动点击"诊断"按钮。生产环境应该自动运行，发现问题时通过飞书/Slack/邮件通知。
4. **多租户隔离**。多人协作时，A 的 Trace 不应该被 B 看到。
5. **性能优化**。当 Trace 数量达到百万级时，当前 SQLite 的简单查询可能不够。需要加索引、分表、或者换成 PostgreSQL。

---

## 九、写在简历上的描述

### 项目名称：AgentTrace

**一句话描述**：
> 开源的 Agent 决策调试器——像 Chrome DevTools 一样调试 AI Agent。

**建议的简历描述**：

```
AgentTrace — 开源 Agent 可观测性工具（Python + FastAPI + React）
- 设计了一套基于 ReAct 范式的 Agent 轨迹数据模型，将 Agent 每一步的思考、
  工具调用、决策理由、候选方案结构化存储，替代传统文本日志方案
- 开发了 Python SDK（装饰器 + contextvars + Pydantic），
  一行代码为任意 Agent 接入轨迹自动采集
- 搭建了 FastAPI + SQLAlchemy 后端服务，支持 9 个 REST 端点，
  SQLite 存储、CSV/JSON 导出、A/B 对比
- 实现 Debug Agent（元 Agent）：用 LLM 自动分析 Agent 执行轨迹，
  检测死循环/工具失败/低置信度等 6 种异常模式并生成诊断报告
- 开发了 React + ReactFlow 可视化 Dashboard，支持决策树展示、
  时间线回放、AI 诊断集成
- 已发布到 GitHub (https://github.com/jiamoonyue/AgentTrace)，
  53 个源文件、8,000+ 行代码
```

**面试时一句话介绍**：

> "我做了个 Agent 调试工具。不是又一个 Agent 示例，而是能装在任何 Agent 上的'行车记录仪'。它记录 Agent 的每一步决策，生成带颜色的决策树。还内置了一个 Debug Agent，能自动分析 Trace 找 bug 给改建议。"

---

## 附录：知识点快速索引

| 知识点 | AgentTrace 中的位置 | 面试重要性 |
|--------|-------------------|:--------:|
| Agent 定义 | 项目核心概念 | ★★★★★ |
| ReAct 框架 | models.py | ★★★★★ |
| Python 装饰器 | decorators.py | ★★★★☆ |
| contextvars | decorators.py | ★★★★★ |
| 上下文管理器 | decorators.py (timed_act) | ★★★☆☆ |
| Pydantic | models.py | ★★★★☆ |
| FastAPI | api/server.py, routes/ | ★★★★☆ |
| SQLAlchemy | storage/ | ★★★☆☆ |
| REST API 设计 | routes/traces.py | ★★★★☆ |
| React/RectFlow | dashboard/ | ★★★☆☆ |
| 依赖注入 | tracer.py | ★★★★☆ |
| 分层架构 | sdk/engine/dashboard | ★★★★★ |
| 元 Agent | debug_agent/ | ★★★★★ |
| 可观测性 | 项目核心价值 | ★★★★★ |
