import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Budget = {
  department: string;
  total_budget: number;
  spent: number;
  remaining: number;
  utilization_pct: number;
};

type SkillGap = {
  skill_id: string;
  skill_name: string;
  employee_count: number;
  average_gap: number;
};

type Summary = {
  employees: number;
  employees_with_gaps: number;
  open_skill_gaps: number;
  readiness_score: number;
  feasible_recommendations: number;
  rejected_candidates: number;
  enrollments: number;
  unique_completions: number;
  passed_completions: number;
  duplicate_completion_events: number;
  completion_rate: number;
  pass_rate: number;
  budgets: Budget[];
  top_skill_gaps: SkillGap[];
  rejection_reasons: Array<{ reason: string; count: number }>;
};

type Recommendation = {
  employee_id: string;
  first_name: string;
  last_name: string;
  department: string;
  skill_id: string;
  skill_name: string;
  gap: number;
  recommended_course_id: string;
  course_name: string;
  course_cost: number | string;
  meets_prerequisites: boolean;
  within_budget: boolean;
  available: boolean;
  capacity_available: boolean;
  recommendation_feasible: boolean;
  rejection_reasons: string;
};

const COLORS = ["#536dfe", "#13b89a", "#f7a94b", "#ec6b75", "#8969dc", "#53a9d8"];
const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

async function loadJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed (${response.status}): ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

function App() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [search, setSearch] = useState("");
  const [department, setDepartment] = useState("");
  const [includeRejected, setIncludeRejected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const recommendationUrl = useMemo(() => {
    const query = new URLSearchParams({ limit: "50" });
    if (search.trim()) query.set("search", search.trim());
    if (department) query.set("department", department);
    if (includeRejected) query.set("includeRejected", "true");
    return `/api/recommendations?${query.toString()}`;
  }, [department, includeRejected, search]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    Promise.all([
      loadJson<Summary>("/api/dashboard/summary"),
      loadJson<{ recommendations: Recommendation[] }>(recommendationUrl),
    ]).then(([nextSummary, recommendationResult]) => {
      if (!active) return;
      setSummary(nextSummary);
      setRecommendations(recommendationResult.recommendations);
    }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : "Unable to load dashboard.");
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [recommendationUrl]);

  const metricCards = summary ? [
    { label: "Active employees", value: summary.employees.toLocaleString(), detail: `${summary.employees_with_gaps.toLocaleString()} have skill gaps`, accent: "blue" },
    { label: "Open skill gaps", value: summary.open_skill_gaps.toLocaleString(), detail: `${summary.readiness_score}% average role readiness`, accent: "purple" },
    { label: "Feasible learning matches", value: summary.feasible_recommendations.toLocaleString(), detail: `${summary.rejected_candidates.toLocaleString()} candidates held for review`, accent: "green" },
    { label: "Course completion rate", value: `${(summary.completion_rate * 100).toFixed(1)}%`, detail: `${(summary.pass_rate * 100).toFixed(1)}% of distinct completions passed`, accent: "orange" },
  ] : [];

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-mark">Y</div>
        <div className="brand-copy"><strong>YottaFlex</strong><span>People intelligence</span></div>
        <nav className="top-nav"><span className="nav-active">Learning insights</span><span>Career pathways</span></nav>
        <div className="planning-pill"><span /> 2026 planning cycle</div>
      </header>

      <section className="page-heading">
        <div>
          <div className="eyebrow">TALENT DEVELOPMENT / OVERVIEW</div>
          <h1>Skills & learning</h1>
          <p>Turn capability gaps into practical, budget-aware growth plans.</p>
        </div>
        <div className="readiness-chip"><span className="readiness-dot" /> Role readiness <b>{summary ? `${summary.readiness_score}%` : "--"}</b></div>
      </section>

      {error && <div className="error-banner" role="alert"><strong>Dashboard unavailable.</strong> {error} Check the API and PostgreSQL connection.</div>}

      <section className="metric-grid" aria-label="Organization metrics">
        {metricCards.map((metric) => (
          <article className={`metric-card ${metric.accent}`} key={metric.label}>
            <div className="metric-label">{metric.label}</div>
            <div className="metric-value">{loading ? "..." : metric.value}</div>
            <div className="metric-detail">{metric.detail}</div>
          </article>
        ))}
      </section>

      <section className="chart-grid">
        <article className="panel chart-panel">
          <div className="panel-heading">
            <div><h2>Most common skill gaps</h2><p>Skills most often below role target</p></div>
            <span className="panel-tag">TOP 8</span>
          </div>
          <div className="chart-area">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={summary?.top_skill_gaps ?? []} layout="vertical" margin={{ left: 8, right: 20, top: 4, bottom: 4 }}>
                <CartesianGrid stroke="#edf0f6" horizontal={false} />
                <XAxis type="number" axisLine={false} tickLine={false} tick={{ fill: "#8290a5", fontSize: 11 }} />
                <YAxis type="category" dataKey="skill_name" width={142} axisLine={false} tickLine={false} tick={{ fill: "#536176", fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="employee_count" name="Employees" fill="#6278f4" radius={[0, 5, 5, 0]} barSize={15} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </article>
        <article className="panel chart-panel">
          <div className="panel-heading">
            <div><h2>Department budget health</h2><p>Planned learning-path commitments</p></div>
            <span className="panel-tag">USD</span>
          </div>
          <div className="budget-chart">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={summary?.budgets ?? []} dataKey="spent" nameKey="department" innerRadius={66} outerRadius={100} paddingAngle={3}>
                  {(summary?.budgets ?? []).map((entry, index) => <Cell key={entry.department} fill={COLORS[index % COLORS.length]} />)}
                </Pie>
                <Tooltip formatter={(value) => currency.format(Number(value))} />
              </PieChart>
            </ResponsiveContainer>
            <div className="budget-center"><strong>{summary?.budgets.length ?? 0}</strong><span>departments</span></div>
          </div>
          <div className="budget-legend">
            {(summary?.budgets ?? []).slice(0, 5).map((budget, index) => (
              <div className="legend-row" key={budget.department}>
                <span className="legend-dot" style={{ backgroundColor: COLORS[index % COLORS.length] }} />
                <span className="legend-name">{budget.department}</span>
                <b>{Number(budget.utilization_pct).toFixed(0)}%</b>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="panel recommendation-panel">
        <div className="panel-heading recommendation-heading">
          <div><h2>Learning recommendations</h2><p>Course matches evaluated against gap, prerequisites, availability, capacity and department budget.</p></div>
          <span className="result-count">{recommendations.length} shown</span>
        </div>
        <div className="filters">
          <label className="search-field">
            <span aria-hidden="true">⌕</span>
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search employee or course" aria-label="Search employee or course" />
          </label>
          <select value={department} onChange={(event) => setDepartment(event.target.value)} aria-label="Filter by department">
            <option value="">All departments</option>
            {(summary?.budgets ?? []).map((budget) => <option key={budget.department}>{budget.department}</option>)}
          </select>
          <label className="toggle-label">
            <input type="checkbox" checked={includeRejected} onChange={(event) => setIncludeRejected(event.target.checked)} />
            Include held candidates
          </label>
        </div>

        <div className="table-scroll">
          <table>
            <thead><tr><th>EMPLOYEE</th><th>SKILL GAP</th><th>RECOMMENDED COURSE</th><th>DEPARTMENT</th><th>EST. COST</th><th>DECISION</th></tr></thead>
            <tbody>
              {recommendations.map((item) => (
                <tr key={`${item.employee_id}-${item.skill_id}-${item.recommended_course_id}`}>
                  <td><div className="employee-cell"><span className="avatar">{item.first_name?.charAt(0)}{item.last_name?.charAt(0)}</span><span><b>{item.first_name} {item.last_name}</b><small>{item.employee_id}</small></span></div></td>
                  <td><span className="skill-name">{item.skill_name}</span><small className="gap-label">Gap: {item.gap} levels</small></td>
                  <td><b className="course-name">{item.course_name}</b><small>{item.recommended_course_id}</small></td>
                  <td>{item.department}</td>
                  <td>{currency.format(Number(item.course_cost))}</td>
                  <td>{item.recommendation_feasible
                    ? <span className="status-pill success">Ready</span>
                    : <span className="status-pill review">{item.rejection_reasons || "Review"}</span>}</td>
                </tr>
              ))}
              {!loading && recommendations.length === 0 && <tr><td className="empty-row" colSpan={6}>No matching course candidates. Try clearing filters or generate the dataset.</td></tr>}
              {loading && <tr><td className="empty-row" colSpan={6}>Loading recommendation data...</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <footer className="footer-note">
        <span>Decision traceability</span>
        <p>Feasible recommendations are separated from rejected candidates; completion events and post-course skill reassessments remain distinct measures.</p>
      </footer>
    </main>
  );
}

export default App;
