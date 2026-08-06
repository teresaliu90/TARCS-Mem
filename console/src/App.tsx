import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Database,
  FileCheck2,
  Filter,
  Gauge,
  KeyRound,
  LayoutDashboard,
  LifeBuoy,
  LockKeyhole,
  Menu,
  Network,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  X,
  XCircle,
} from "lucide-react";
import { api, Integrations, Memory, Overview } from "./api";

type Page =
  | "overview"
  | "sandbox"
  | "memories"
  | "review"
  | "observability"
  | "integrations";
const labels: Record<string, string> = {
  verified_active: "已生效",
  pending: "待审核",
  superseded: "已替代",
  expired: "已过期",
  rejected: "已驳回",
  candidate: "候选",
};
const sourceLabels: Record<string, string> = {
  official_policy: "正式制度",
  meeting_note: "会议纪要",
  user_claim: "用户陈述",
  approved_exception: "已审批例外",
  public_dataset: "公开数据",
  system_record: "系统记录",
};

function App() {
  const [page, setPage] = useState<Page>("overview");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [integrations, setIntegrations] = useState<Integrations | null>(null);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [selected, setSelected] = useState<Memory | null>(null);
  const [error, setError] = useState("");
  const [mobileNav, setMobileNav] = useState(false);
  const [apiKeyOpen, setApiKeyOpen] = useState(false);

  const refresh = async () => {
    setError("");
    try {
      const [nextOverview, nextIntegrations, nextMemories] = await Promise.all([
        api.overview(),
        api.integrations(),
        api.memories(),
      ]);
      setOverview(nextOverview);
      setIntegrations(nextIntegrations);
      setMemories(nextMemories.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "控制台暂时无法连接 API");
    }
  };
  useEffect(() => {
    void refresh();
  }, []);
  const nav = (next: Page) => {
    setPage(next);
    setMobileNav(false);
  };

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "is-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">T</div>
          <div>
            <strong>TARCS-Mem</strong>
            <span>治理控制台</span>
          </div>
          <button
            className="icon-button mobile-close"
            onClick={() => setMobileNav(false)}
            aria-label="关闭菜单"
          >
            <X size={18} />
          </button>
        </div>
        <div className="workspace">
          <span className="eyebrow">工作区</span>
          <button className="workspace-switch">
            <span className="workspace-dot" />
            默认演示租户 <ChevronRight size={15} />
          </button>
        </div>
        <nav aria-label="主导航">
          <NavItem
            icon={<LayoutDashboard size={17} />}
            label="治理总览"
            active={page === "overview"}
            onClick={() => nav("overview")}
          />
          <NavItem
            icon={<Sparkles size={17} />}
            label="安全测试场"
            active={page === "sandbox"}
            onClick={() => nav("sandbox")}
          />
          <NavItem
            icon={<Database size={17} />}
            label="可信记忆"
            badge={overview?.total_memories}
            active={page === "memories"}
            onClick={() => nav("memories")}
          />
          <NavItem
            icon={<FileCheck2 size={17} />}
            label="审核工作台"
            badge={overview?.review_queue}
            active={page === "review"}
            onClick={() => nav("review")}
          />
          <NavItem
            icon={<Activity size={17} />}
            label="Trace 与审计"
            active={page === "observability"}
            onClick={() => nav("observability")}
          />
          <NavItem
            icon={<Network size={17} />}
            label="集成中心"
            active={page === "integrations"}
            onClick={() => nav("integrations")}
          />
        </nav>
        <div className="sidebar-footer">
          <a
            className="nav-item"
            href="https://github.com/teresaliu90/TARCS-Mem/issues"
            target="_blank"
            rel="noreferrer"
          >
            <LifeBuoy size={17} />
            帮助与反馈
          </a>
          <div className="alpha">
            <span className="status-dot" />
            v0.8 Design Partner Edition
          </div>
        </div>
      </aside>
      {mobileNav && (
        <button
          className="scrim"
          onClick={() => setMobileNav(false)}
          aria-label="关闭导航"
        />
      )}
      <main className="main-content">
        <header className="topbar">
          <button
            className="icon-button menu-button"
            onClick={() => setMobileNav(true)}
            aria-label="打开菜单"
          >
            <Menu size={20} />
          </button>
          <div className="crumb">
            <span>默认演示租户</span>
            <ChevronRight size={15} />
            <strong>{pageTitle(page)}</strong>
          </div>
          <div className="top-actions">
            <button
              className={`connection ${error ? "is-error" : ""}`}
              onClick={() => error && setApiKeyOpen(true)}
            >
              <span className="status-dot" />
              {error ? "API 未连接" : "API 已连接"}
            </button>
            <button
              className="icon-button"
              onClick={() => void refresh()}
              aria-label="刷新数据"
            >
              <RefreshCw size={17} />
            </button>
            <button className="avatar" aria-label="当前用户">
              D
            </button>
          </div>
        </header>
        <div className="page-wrap">
          {error && (
            <div className="alert error">
              <ShieldAlert size={17} />
              {error}
              <button onClick={() => setError("")} aria-label="关闭提示">
                <X size={15} />
              </button>
            </div>
          )}
          {page === "overview" && (
            <OverviewPage overview={overview} onNavigate={nav} />
          )}
          {page === "sandbox" && <SandboxPage />}
          {page === "memories" && (
            <MemoriesPage
              memories={memories}
              onSelect={setSelected}
              onRefresh={refresh}
            />
          )}
          {page === "review" && (
            <ReviewPage
              memories={memories.filter((item) => item.status === "pending")}
              onDone={refresh}
            />
          )}
          {page === "observability" && <ObservabilityPage />}
          {page === "integrations" && (
            <IntegrationsPage
              integrations={integrations}
              onConfigureKey={() => setApiKeyOpen(true)}
            />
          )}
        </div>
      </main>
      {selected && (
        <DetailDrawer memory={selected} onClose={() => setSelected(null)} />
      )}
      {apiKeyOpen && (
        <ApiKeyModal onClose={() => setApiKeyOpen(false)} onSaved={refresh} />
      )}
    </div>
  );
}

function NavItem({
  icon,
  label,
  badge,
  active,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  badge?: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button className={`nav-item ${active ? "active" : ""}`} onClick={onClick}>
      {icon}
      <span>{label}</span>
      {badge !== undefined && badge > 0 && <em>{badge}</em>}
    </button>
  );
}
function pageTitle(page: Page) {
  return {
    overview: "治理总览",
    sandbox: "安全测试场",
    memories: "可信记忆",
    review: "审核工作台",
    observability: "Trace 与审计",
    integrations: "集成中心",
  }[page];
}
function SectionHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="section-header">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
  );
}
function Metric({
  icon,
  label,
  value,
  detail,
  tone = "neutral",
}: {
  icon: ReactNode;
  label: string;
  value: string | number;
  detail: string;
  tone?: string;
}) {
  return (
    <div className={`metric metric-${tone}`}>
      <div className="metric-icon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </div>
  );
}

function OverviewPage({
  overview,
  onNavigate,
}: {
  overview: Overview | null;
  onNavigate: (page: Page) => void;
}) {
  if (!overview) return <Loading />;
  return (
    <>
      <SectionHeader
        eyebrow="治理健康"
        title="让每一次回答都有边界"
        description="从一个页面看见可信记忆的状态、风险和下一步动作。"
        action={
          <button
            className="button primary"
            onClick={() => onNavigate("sandbox")}
          >
            <Sparkles size={16} />
            开始安全测试
          </button>
        }
      />
      <div className="metric-grid">
        <Metric
          icon={<ShieldCheck />}
          label="可信记忆"
          value={overview.status_counts.verified_active ?? 0}
          detail={`共 ${overview.total_memories} 条记录`}
          tone="good"
        />
        <Metric
          icon={<FileCheck2 />}
          label="待处理审核"
          value={overview.review_queue}
          detail="需要具名人工决定"
          tone={overview.review_queue ? "warn" : "neutral"}
        />
        <Metric
          icon={<ShieldAlert />}
          label="现行冲突"
          value={overview.active_conflicts}
          detail="候选与已生效版本重叠"
          tone={overview.active_conflicts ? "danger" : "good"}
        />
        <Metric
          icon={<Clock3 />}
          label="即将失效"
          value={overview.expiring_soon}
          detail="未来 30 天内到期"
        />
        <Metric
          icon={<LockKeyhole />}
          label="数据分级"
          value={overview.classification_counts.confidential ?? 0}
          detail="机密记录（默认禁止云端）"
          tone="neutral"
        />
      </div>
      <div className="overview-grid">
        <div className="panel health-panel">
          <div className="panel-heading">
            <div>
              <h2>治理状态</h2>
              <p>数据进入回答前，必须经过这些边界。</p>
            </div>
            <button
              className="text-button"
              onClick={() => onNavigate("memories")}
            >
              查看全部 <ArrowRight size={15} />
            </button>
          </div>
          <StatusBar
            label="已生效"
            value={overview.status_counts.verified_active ?? 0}
            total={overview.total_memories}
            tone="green"
          />
          <StatusBar
            label="待审核"
            value={overview.status_counts.pending ?? 0}
            total={overview.total_memories}
            tone="orange"
          />
          <StatusBar
            label="已替代 / 过期"
            value={
              (overview.status_counts.superseded ?? 0) +
              (overview.status_counts.expired ?? 0)
            }
            total={overview.total_memories}
            tone="gray"
          />
          <div className="privacy-note">
            <ShieldCheck size={16} />
            <span>{overview.privacy}</span>
          </div>
        </div>
        <div className="panel issue-panel">
          <div className="panel-heading">
            <div>
              <h2>需要处理</h2>
              <p>优先处理高风险治理事件。</p>
            </div>
            <button
              className="text-button"
              onClick={() => onNavigate("review")}
            >
              打开队列 <ArrowRight size={15} />
            </button>
          </div>
          {overview.issues.length ? (
            overview.issues.slice(0, 4).map((issue) => (
              <button
                className="issue-row"
                key={issue.id}
                onClick={() => onNavigate("review")}
              >
                <span className={`issue-icon ${issue.severity}`}>
                  <ShieldAlert size={15} />
                </span>
                <span>
                  <strong>{issue.title}</strong>
                  <small>
                    {issue.source_ref} · {issue.conflict_key}
                  </small>
                </span>
                <ChevronRight size={16} />
              </button>
            ))
          ) : (
            <Empty
              icon={<CheckCircle2 />}
              title="当前没有待处理事件"
              detail="治理队列保持清洁。"
            />
          )}
        </div>
      </div>
      <div className="next-step">
        <div className="next-icon">
          <Gauge size={20} />
        </div>
        <div>
          <span className="eyebrow">建议下一步</span>
          <h2>用安全测试场理解 TARCS-Mem 的价值</h2>
          <p>
            用三个无敏感数据的案例，直观看见过期、越权和冲突证据如何被拦截。
          </p>
        </div>
        <button
          className="button secondary"
          onClick={() => onNavigate("sandbox")}
        >
          查看案例 <ArrowRight size={16} />
        </button>
      </div>
    </>
  );
}
function StatusBar({
  label,
  value,
  total,
  tone,
}: {
  label: string;
  value: number;
  total: number;
  tone: string;
}) {
  return (
    <div className="status-bar">
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
      <div className="bar">
        <i
          className={tone}
          style={{
            width: `${total ? Math.max(4, (value / total) * 100) : 4}%`,
          }}
        />
      </div>
    </div>
  );
}

function SandboxPage() {
  const [scenario, setScenario] = useState(0);
  const [question, setQuestion] = useState(
    "2026年8月华南区销售折扣上限是多少？",
  );
  const [asOf, setAsOf] = useState("2026-08-15");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const selectScenario = (
    index: number,
    nextQuestion: string,
    nextDate: string,
  ) => {
    setScenario(index);
    setQuestion(nextQuestion);
    setAsOf(nextDate);
    setResult(null);
  };
  const run = async () => {
    setLoading(true);
    try {
      const value = await api.query(question, asOf);
      setResult(value);
    } catch (err) {
      setResult({
        outcome: "error",
        answer: err instanceof Error ? err.message : "请求失败",
      });
    } finally {
      setLoading(false);
    }
  };
  const answered = result?.outcome === "answered";
  const selectedEvidence =
    (result?.selected_evidence as Array<Record<string, unknown>> | undefined) ??
    [];
  return (
    <>
      <SectionHeader
        eyebrow="可解释演示"
        title="安全测试场"
        description="用无敏感数据的案例，比较普通检索和受治理回答的差异。"
        action={
          <span className="demo-badge">
            <span className="status-dot" />
            本地演示数据
          </span>
        }
      />
      <div className="scenario-tabs">
        <button
          className={`scenario ${scenario === 0 ? "active" : ""}`}
          onClick={() =>
            selectScenario(
              0,
              "2026年8月华南区销售折扣上限是多少？",
              "2026-08-15",
            )
          }
        >
          <ShieldCheck size={16} />
          <span>
            <strong>制度版本</strong>
            <small>新版本替代旧版本</small>
          </span>
        </button>
        <button
          className={`scenario ${scenario === 1 ? "active" : ""}`}
          onClick={() =>
            selectScenario(
              1,
              "2026年10月北区培训津贴是否已提高到900元？",
              "2026-10-01",
            )
          }
        >
          <ShieldAlert size={16} />
          <span>
            <strong>证据不足</strong>
            <small>系统应当明确拒答</small>
          </span>
        </button>
        <button
          className={`scenario ${scenario === 2 ? "active" : ""}`}
          onClick={() =>
            selectScenario(2, "财务机密文档能否发送给云端模型？", "2026-08-15")
          }
        >
          <LockKeyhole size={16} />
          <span>
            <strong>出境边界</strong>
            <small>机密内容默认拦截</small>
          </span>
        </button>
      </div>
      <div className="sandbox-grid">
        <div className="panel test-panel">
          <div className="panel-heading">
            <div>
              <h2>提一个业务问题</h2>
              <p>回答仅使用已通过状态、时效、权限和冲突治理的证据。</p>
            </div>
            <span className="local-label">
              <Database size={14} />
              零配置本地
            </span>
          </div>
          <label className="field">
            <span>问题</span>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              rows={4}
            />
          </label>
          <label className="field">
            <span>业务日期</span>
            <input
              type="date"
              value={asOf}
              onChange={(event) => setAsOf(event.target.value)}
            />
          </label>
          <button
            className="button primary wide"
            disabled={loading}
            onClick={() => void run()}
          >
            {loading ? (
              <RefreshCw className="spin" size={16} />
            ) : (
              <Search size={16} />
            )}
            {loading ? "正在查证" : "查证并解释"}
          </button>
          <div className="safety-checks">
            <SafetyCheck
              icon={<CheckCircle2 />}
              label="状态过滤"
              detail="仅使用已生效证据"
            />
            <SafetyCheck
              icon={<CheckCircle2 />}
              label="时间过滤"
              detail="按业务日期判断有效性"
            />
            <SafetyCheck
              icon={<CheckCircle2 />}
              label="引用校验"
              detail="来源缺失时拒绝生成"
            />
          </div>
        </div>
        <div className="comparison">
          <div className="comparison-head">
            <div>
              <h2>裁决结果</h2>
              <p>先看人能理解的结论，再展开技术细节。</p>
            </div>
            {result && (
              <span className={`outcome ${answered ? "good" : "warn"}`}>
                {answered ? "可信回答" : "需要谨慎"}
              </span>
            )}
          </div>
          {!result ? (
            <Empty
              icon={<Sparkles />}
              title="等待一次安全测试"
              detail="选择上方案例，或直接提问。"
            />
          ) : (
            <>
              <div
                className={`answer-box ${answered ? "answered" : "abstained"}`}
              >
                <span className="eyebrow">TARCS-Mem</span>
                <p>{String(result.answer ?? "系统没有返回答案")}</p>
                {answered && selectedEvidence[0] && (
                  <div className="citation">
                    <BookOpen size={15} />
                    <span>
                      {String(selectedEvidence[0].source_ref)} ·{" "}
                      {String(selectedEvidence[0].fact)}
                    </span>
                  </div>
                )}
              </div>
              <div className="ordinary-rag">
                <div>
                  <span className="eyebrow">普通 RAG 可能会</span>
                  <p>
                    {answered
                      ? "直接使用相似度最高的片段，容易忽略旧版本和冲突。"
                      : "在证据不足时仍尝试生成一个看似完整的答案。"}
                  </p>
                </div>
                <XCircle size={19} />
              </div>
              <details className="technical">
                <summary>
                  查看技术细节 <ChevronRight size={15} />
                </summary>
                <pre>
                  {JSON.stringify(result.decision_trace ?? result, null, 2)}
                </pre>
              </details>
            </>
          )}
        </div>
      </div>
    </>
  );
}
function SafetyCheck({
  icon,
  label,
  detail,
}: {
  icon: ReactNode;
  label: string;
  detail: string;
}) {
  return (
    <div className="safety-check">
      <span>{icon}</span>
      <div>
        <strong>{label}</strong>
        <small>{detail}</small>
      </div>
    </div>
  );
}

function MemoriesPage({
  memories,
  onSelect,
  onRefresh,
}: {
  memories: Memory[];
  onSelect: (memory: Memory) => void;
  onRefresh: () => void;
}) {
  const [filter, setFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const filtered = useMemo(
    () =>
      memories.filter(
        (item) =>
          (statusFilter === "all" || item.status === statusFilter) &&
          (!filter ||
            `${item.fact} ${item.source_ref} ${item.id}`
              .toLowerCase()
              .includes(filter.toLowerCase())),
      ),
    [memories, filter, statusFilter],
  );
  return (
    <>
      <SectionHeader
        eyebrow="知识治理"
        title="可信记忆"
        description="每条可回答信息都有来源、状态、生效时间和访问边界。"
        action={
          <button className="button secondary" onClick={onRefresh}>
            <RefreshCw size={15} />
            刷新列表
          </button>
        }
      />
      <div className="toolbar">
        <div className="search-field">
          <Search size={16} />
          <input
            placeholder="搜索事实、来源或记忆 ID"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          />
        </div>
        <label className="filter-select" aria-label="按状态筛选">
          <Filter size={15} />
          <select
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="all">全部状态</option>
            <option value="verified_active">已生效</option>
            <option value="pending">待审核</option>
            <option value="superseded">已替代</option>
            <option value="expired">已过期</option>
            <option value="rejected">已驳回</option>
          </select>
        </label>
        <span className="toolbar-count">{filtered.length} 条记录</span>
      </div>
      <div className="panel table-panel">
        <table>
          <thead>
            <tr>
              <th>记忆内容</th>
              <th>来源</th>
              <th>状态</th>
              <th>业务时间</th>
              <th>访问范围</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((memory) => (
              <tr key={memory.id} onClick={() => onSelect(memory)}>
                <td>
                  <strong>{memory.fact}</strong>
                  <small>{memory.id}</small>
                </td>
                <td>
                  <span className="source">
                    <span className="source-mark" />
                    {sourceLabels[memory.source_type] ?? memory.source_type}
                    <small>{memory.source_ref}</small>
                  </span>
                </td>
                <td>
                  <span className={`status-pill ${memory.status}`}>
                    {labels[memory.status]}
                  </span>
                </td>
                <td>
                  <span className="date-cell">
                    {memory.valid_from ?? "—"}
                    <small>
                      {memory.valid_to ? `至 ${memory.valid_to}` : "持续有效"}
                    </small>
                  </span>
                </td>
                <td>
                  <span className="access-cell">
                    <span
                      className={`classification ${memory.classification}`}
                    />
                    {memory.allowed_roles.length
                      ? memory.allowed_roles.join(", ")
                      : "租户内"}
                  </span>
                </td>
                <td>
                  <ChevronRight size={16} className="row-arrow" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!filtered.length && (
          <Empty
            icon={<Database />}
            title="没有匹配的记忆"
            detail="尝试清空搜索条件。"
          />
        )}
      </div>
    </>
  );
}

function ReviewPage({
  memories,
  onDone,
}: {
  memories: Memory[];
  onDone: () => void;
}) {
  const [active, setActive] = useState<Memory | null>(memories[0] ?? null);
  const [reviewer, setReviewer] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [messageError, setMessageError] = useState(false);
  useEffect(() => {
    if (!active && memories[0]) setActive(memories[0]);
  }, [memories, active]);
  const review = async (decision: "approve" | "reject") => {
    if (!active || !reviewer.trim()) {
      setMessageError(true);
      setMessage("请先填写审核人，确保决定可追溯。");
      return;
    }
    setBusy(true);
    try {
      await api.review(active.id, decision, reviewer, note);
      setMessageError(false);
      setMessage(
        decision === "approve"
          ? "已批准并激活，审计事件已记录。"
          : "已驳回，审计事件已记录。",
      );
      onDone();
    } catch (err) {
      setMessageError(true);
      setMessage(err instanceof Error ? err.message : "审核失败");
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <SectionHeader
        eyebrow="人工治理"
        title="审核工作台"
        description="候选信息不会自动覆盖正式制度。每一次决定都需要具名、备注和审计轨迹。"
        action={
          <span className="queue-count">
            <FileCheck2 size={16} />
            {memories.length} 条待处理
          </span>
        }
      />
      {message && (
        <div className={`alert ${messageError ? "error" : "success"}`}>
          {messageError ? (
            <ShieldAlert size={17} />
          ) : (
            <CheckCircle2 size={17} />
          )}
          {message}
        </div>
      )}
      <div className="review-layout">
        <div className="panel queue-panel">
          <div className="panel-heading">
            <div>
              <h2>待处理队列</h2>
              <p>优先处理有冲突的候选记忆。</p>
            </div>
            <button
              className="icon-button"
              onClick={onDone}
              aria-label="刷新审核队列"
            >
              <RefreshCw size={16} />
            </button>
          </div>
          {memories.map((memory) => (
            <button
              key={memory.id}
              className={`queue-row ${active?.id === memory.id ? "active" : ""}`}
              onClick={() => setActive(memory)}
            >
              <span className="queue-status">
                <ShieldAlert size={15} />
              </span>
              <span>
                <strong>{memory.fact}</strong>
                <small>
                  {sourceLabels[memory.source_type] ?? memory.source_type} ·{" "}
                  {memory.source_ref}
                </small>
              </span>
              <ChevronRight size={16} />
            </button>
          ))}
          {!memories.length && (
            <Empty
              icon={<CheckCircle2 />}
              title="审核队列为空"
              detail="新的候选记忆会出现在这里。"
            />
          )}
        </div>
        <div className="panel review-detail">
          {active ? (
            <>
              <div className="review-summary">
                <span className="status-pill pending">待审核</span>
                <span className="review-id">{active.id}</span>
              </div>
              <h2>{active.fact}</h2>
              <div className="impact-grid">
                <Impact
                  label="来源"
                  value={`${sourceLabels[active.source_type] ?? active.source_type} · ${active.source_ref}`}
                />
                <Impact
                  label="权威等级"
                  value={`${Math.round(active.authority * 100)} / 100`}
                />
                <Impact
                  label="业务时间"
                  value={active.valid_from ?? "未设置"}
                />
                <Impact label="数据分级" value={active.classification} />
              </div>
              <div className="decision-callout">
                <ShieldAlert size={18} />
                <div>
                  <strong>系统建议：保持待审核</strong>
                  <p>
                    低权威来源不能静默替代当前已生效的正式版本。批准前请确认来源、业务日期和影响范围。
                  </p>
                </div>
              </div>
              <label className="field">
                <span>
                  审核人 <i>必填</i>
                </span>
                <input
                  placeholder="姓名或企业账号"
                  value={reviewer}
                  onChange={(event) => setReviewer(event.target.value)}
                />
              </label>
              <label className="field">
                <span>审核备注</span>
                <textarea
                  rows={3}
                  placeholder="填写依据、工单号或拒绝原因"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                />
              </label>
              <div className="review-actions">
                <button
                  className="button danger"
                  disabled={busy}
                  onClick={() => void review("reject")}
                >
                  <XCircle size={16} />
                  驳回
                </button>
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={() => void review("approve")}
                >
                  <CheckCircle2 size={16} />
                  批准并激活
                </button>
              </div>
            </>
          ) : (
            <Empty
              icon={<FileCheck2 />}
              title="选择一条待审核记忆"
              detail="系统会展示来源、影响和建议。"
            />
          )}
        </div>
      </div>
    </>
  );
}
function Impact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ObservabilityPage() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const load = async () => {
    try {
      setError("");
      setData(await api.observability());
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法加载观测");
    }
  };
  useEffect(() => {
    void load();
  }, []);
  const spans =
    (data?.recent_spans as Array<Record<string, unknown>> | undefined) ?? [];
  return (
    <>
      <SectionHeader
        eyebrow="可观测性"
        title="Trace 与审计"
        description="先看需要处理的治理事件，再进入完整执行链路。原始问题和文档正文不会进入 Trace。"
        action={
          <button className="button secondary" onClick={() => void load()}>
            <RefreshCw size={15} />
            刷新观测
          </button>
        }
      />
      {error && <div className="alert error">{error}</div>}
      <div className="trace-grid">
        <div className="panel trace-summary">
          <div className="panel-heading">
            <div>
              <h2>最近 Trace</h2>
              <p>GuardRead 的选择、排序和输出状态。</p>
            </div>
            <Activity size={18} />
          </div>
          {spans.slice(0, 8).map((span, index) => (
            <div className="trace-row" key={`${String(span.span_id)}-${index}`}>
              <span
                className={`trace-dot ${span.status === "error" ? "error" : "ok"}`}
              />
              <div>
                <strong>{String(span.name)}</strong>
                <small>
                  trace {String(span.trace_id).slice(0, 12)}… ·{" "}
                  {String(span.duration_ms)} ms
                </small>
              </div>
              <span className="trace-status">
                {span.status === "error" ? "异常" : "完成"}
              </span>
            </div>
          ))}
          {!data && <Loading />}
          {data && spans.length === 0 && (
            <Empty
              icon={<Activity />}
              title="还没有 Trace"
              detail="运行一次安全测试后会在这里显示。"
            />
          )}
        </div>
        <div className="panel metrics-panel">
          <div className="panel-heading">
            <div>
              <h2>运行指标</h2>
              <p>安全的聚合指标，不包含正文。</p>
            </div>
            <Gauge size={18} />
          </div>
          <pre className="metrics-json">
            {JSON.stringify(
              data?.metrics ?? { status: "等待一次查询" },
              null,
              2,
            )}
          </pre>
          <div className="privacy-note">
            <LockKeyhole size={16} />
            <span>
              {String(
                data?.privacy ?? "观测数据不保存原始问题、文档正文或密钥",
              )}
            </span>
          </div>
        </div>
      </div>
    </>
  );
}

function IntegrationsPage({
  integrations,
  onConfigureKey,
}: {
  integrations: Integrations | null;
  onConfigureKey: () => void;
}) {
  return (
    <>
      <SectionHeader
        eyebrow="连接你的现有系统"
        title="集成中心"
        description="TARCS-Mem 作为治理层接在现有 Agent、模型、数据源和框架前面。"
        action={
          <button className="button secondary" onClick={onConfigureKey}>
            <KeyRound size={15} />
            配置 API Key
          </button>
        }
      />
      <div className="integration-intro">
        <div className="integration-intro-icon">
          <Network size={21} />
        </div>
        <div>
          <strong>先连接，再治理</strong>
          <p>
            每个连接器都明确显示会发送哪些数据，以及哪些安全边界仍由企业身份系统负责。
          </p>
        </div>
        <ArrowRight size={18} />
      </div>
      <div className="integration-grid">
        {integrations?.items.map((item) => (
          <div className="panel integration-card" key={item.id}>
            <div className="integration-card-head">
              <div className="integration-icon">
                <IntegrationIcon id={item.id} />
              </div>
              <span className={`integration-status ${item.status}`}>
                {item.status === "ready"
                  ? "可直接使用"
                  : item.status === "connected"
                    ? "已连接"
                    : "待配置"}
              </span>
            </div>
            <span className="eyebrow">{item.category}</span>
            <h2>{item.name}</h2>
            <p>{item.description}</p>
            <a href={item.docs} target="_blank" rel="noreferrer">
              查看接入说明 <ArrowRight size={14} />
            </a>
          </div>
        )) ?? <Loading />}
      </div>
    </>
  );
}
function IntegrationIcon({ id }: { id: string }) {
  const props = { size: 19 };
  if (id === "qdrant" || id === "confluence") return <Database {...props} />;
  if (id === "mcp" || id === "frameworks") return <Network {...props} />;
  if (id === "deepseek") return <Sparkles {...props} />;
  return <BookOpen {...props} />;
}
function DetailDrawer({
  memory,
  onClose,
}: {
  memory: Memory;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<{
    events: Array<Record<string, unknown>>;
    related_versions: Memory[];
  } | null>(null);
  useEffect(() => {
    void api
      .memory(memory.id)
      .then(setDetail)
      .catch(() => null);
  }, [memory.id]);
  return (
    <>
      <button
        className="drawer-scrim"
        onClick={onClose}
        aria-label="关闭详情"
      />
      <aside className="drawer">
        <div className="drawer-head">
          <div>
            <span className="eyebrow">记忆详情</span>
            <h2>{memory.id}</h2>
          </div>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="关闭详情"
          >
            <X size={18} />
          </button>
        </div>
        <div className="drawer-body">
          <span className={`status-pill ${memory.status}`}>
            {labels[memory.status]}
          </span>
          <h3>{memory.fact}</h3>
          <dl>
            <div>
              <dt>来源</dt>
              <dd>
                {sourceLabels[memory.source_type] ?? memory.source_type} ·{" "}
                {memory.source_ref}
              </dd>
            </div>
            <div>
              <dt>权威等级</dt>
              <dd>{Math.round(memory.authority * 100)} / 100</dd>
            </div>
            <div>
              <dt>业务时间</dt>
              <dd>
                {memory.valid_from ?? "未设置"}
                {memory.valid_to ? ` 至 ${memory.valid_to}` : " 起持续有效"}
              </dd>
            </div>
            <div>
              <dt>访问范围</dt>
              <dd>
                {memory.allowed_roles.length
                  ? memory.allowed_roles.join(", ")
                  : "租户内可见"}
              </dd>
            </div>
            <div>
              <dt>数据分级</dt>
              <dd>{memory.classification}</dd>
            </div>
          </dl>
          <div className="drawer-section">
            <h4>相关版本</h4>
            {detail?.related_versions?.length ? (
              detail.related_versions.map((item) => (
                <div className="related-row" key={item.id}>
                  <span className={`status-pill ${item.status}`}>
                    {labels[item.status]}
                  </span>
                  <span>{item.fact}</span>
                </div>
              ))
            ) : (
              <p className="muted">没有其他关联版本。</p>
            )}
          </div>
          <div className="drawer-section">
            <h4>审计事件</h4>
            {detail?.events?.length ? (
              detail.events.slice(-6).map((event, index) => (
                <div
                  className="event-row"
                  key={`${String(event.event_type)}-${index}`}
                >
                  <span>{String(event.event_type)}</span>
                  <small>{String(event.at)}</small>
                </div>
              ))
            ) : (
              <p className="muted">暂无审计事件。</p>
            )}
          </div>
        </div>
      </aside>
    </>
  );
}
function ApiKeyModal({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => void;
}) {
  const [value, setValue] = useState(
    () => window.sessionStorage.getItem("tarcsmem_api_key") ?? "",
  );
  const save = () => {
    const trimmed = value.trim();
    if (trimmed) window.sessionStorage.setItem("tarcsmem_api_key", trimmed);
    else window.sessionStorage.removeItem("tarcsmem_api_key");
    onClose();
    onSaved();
  };
  return (
    <div
      className="modal-scrim"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="api-key-title"
      >
        <div className="modal-head">
          <div>
            <span className="eyebrow">会话凭证</span>
            <h2 id="api-key-title">配置 API Key</h2>
            <p>
              仅保存在当前浏览器标签页的 sessionStorage
              中，关闭标签页后自动清除，不会写入服务端日志。
            </p>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="关闭">
            <X size={17} />
          </button>
        </div>
        <label className="field">
          <span>Bearer Token</span>
          <input
            autoFocus
            type="password"
            autoComplete="off"
            placeholder="未启用认证时可留空"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") save();
            }}
          />
        </label>
        <div className="modal-actions">
          <button
            className="button secondary"
            onClick={() => {
              setValue("");
              window.sessionStorage.removeItem("tarcsmem_api_key");
              onClose();
              onSaved();
            }}
          >
            清除
          </button>
          <button className="button primary" onClick={save}>
            <KeyRound size={15} />
            保存到本次会话
          </button>
        </div>
      </section>
    </div>
  );
}
function Empty({
  icon,
  title,
  detail,
}: {
  icon: ReactNode;
  title: string;
  detail: string;
}) {
  return (
    <div className="empty">
      <span>{icon}</span>
      <strong>{title}</strong>
      <p>{detail}</p>
    </div>
  );
}
function Loading() {
  return (
    <div className="loading">
      <RefreshCw className="spin" size={18} />
      加载治理数据…
    </div>
  );
}

export default App;
