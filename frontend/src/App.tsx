import { useEffect, useMemo, useState } from "react";
import { Copy, Download, FlaskConical, Layers3, Plus, Table2, Trash2 } from "lucide-react";

const API = "http://localhost:8000/api";
type Source = { name: string; fields: { name: string; type: string }[] };
type Step = Record<string, unknown> & { type: string };
type Template = { id: string; operation: string; status: string; notes?: string; last_import_result?: { status: string; error_text: string } | null };
type BuildResult = { id: string; json: unknown; validation: { check: string; passed: boolean; reason: string }[]; templates: { id: string; status: string }[]; download_url: string };

async function request(path: string, init?: RequestInit) {
  const response = await fetch(`${API}${path}`, init);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
  return payload;
}

export default function App() {
  const [page, setPage] = useState<"Sources" | "Pipeline Builder" | "Template Lab">("Sources");
  const [sources, setSources] = useState<Source[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [goldenViews, setGoldenViews] = useState<string[]>([]);
  const [baseView, setBaseView] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [steps, setSteps] = useState<Step[]>([]);
  const [viewName, setViewName] = useState("GeneratedView");
  const [build, setBuild] = useState<BuildResult | null>(null);

  const refresh = async () => {
    try {
      const [sourceList, templateList, goldenList] = await Promise.all([request("/sources"), request("/templates"), request("/golden")]);
      setSources(sourceList);
      setTemplates(templateList);
      setGoldenViews(goldenList);
      setBaseView((current) => current || goldenList[0] || "");
    } catch (e) { setError(message(e)); }
  };
  useEffect(() => { void refresh(); }, []);
  const columns = useMemo(() => sources.flatMap((table) => table.fields.map((field) => ({ table: table.name, ...field }))), [sources]);

  async function uploadSources(files: FileList | null) {
    if (!files?.length) return;
    const form = new FormData();
    Array.from(files).forEach((file) => form.append("files", file));
    try { setSources(await request("/sources", { method: "POST", body: form })); setError(""); setNotice("Sources uploaded."); }
    catch (e) { setError(message(e)); }
  }

  function addStep(type: string) {
    const first = columns[0]?.name ?? "";
    const table = sources[0]?.name ?? "";
    const secondTable = sources[1]?.name ?? table;
    const initial: Record<string, Step> = {
      projection: { type, keep_columns: columns.map((column) => column.name), renames: {} },
      filter: { type, column: first, operator: "=", values: [""] },
      join: { type, left_table: table, right_table: secondTable, join_type: "inner", key_pairs: [{ left_column: first, right_column: first }] },
      association: { type, target_table: secondTable, key_pairs: [{ left_column: first, right_column: first }], association_name: "Association" },
    };
    const template = templates.find((item) => item.id === type) as (Template & { placeholders?: { name: string; type: string }[] }) | undefined;
    const dynamic = template ? Object.fromEntries((template.placeholders ?? [])
      .filter((item) => item.type !== "generated" && !item.name.startsWith("uuid:") && item.name !== "now_ms")
      .map((item) => [item.name, ""])) : {};
    const newStep = initial[type] ?? { type, ...dynamic };
    if (newStep) setSteps((current) => [...current, newStep]);
  }
  function updateStep(index: number, patch: Record<string, unknown>) {
    setSteps((current) => current.map((step, i) => i === index ? { ...step, ...patch } : step));
  }
  function moveStep(index: number, direction: -1 | 1) {
    setSteps((current) => {
      const target = index + direction;
      if (target < 0 || target >= current.length) return current;
      const next = [...current]; [next[index], next[target]] = [next[target], next[index]]; return next;
    });
  }
  async function buildView() {
    try {
      const result = await request("/build", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ view_name: viewName, base_view: baseView || null, steps }) });
      setBuild(result); setError("");
    } catch (e) { setError(message(e)); setBuild(null); }
  }
  async function copyJson() {
    if (build) { await navigator.clipboard.writeText(JSON.stringify(build.json, null, 2)); setNotice("JSON copied."); }
  }

  return <div className="min-h-screen">
    <header className="topbar">
      <div className="brand"><span className="brand-icon"><FlaskConical size={18} /></span><div><strong>Template Lab</strong><small>Datasphere view testing tool</small></div></div>
      <div className="no-ai">TEMPLATE-BASED · NO AI</div>
    </header>
    <main className="shell">
      <nav className="tabs">
        {(["Sources", "Pipeline Builder", "Template Lab"] as const).map((tab) => <button className={page === tab ? "tab active" : "tab"} onClick={() => { setPage(tab); setError(""); }} key={tab}>{tab === "Sources" ? <Table2 size={16} /> : tab === "Pipeline Builder" ? <Layers3 size={16} /> : <FlaskConical size={16} />}{tab}</button>)}
      </nav>
      {(error || notice) && <div className={error ? "alert error" : "alert success"}><span>{error || notice}{error.startsWith("No template for ") && <button className="inline-link" onClick={() => { setPage("Template Lab"); setError(""); }}>Open Template Lab</button>}</span><button onClick={() => { setError(""); setNotice(""); }}>×</button></div>}
      {page === "Sources" && <section>
        <div className="page-heading"><div><p className="eyebrow">START HERE</p><h1>Source tables</h1><p>Upload 1–3 source or entity JSON exports. Their columns will be available in the pipeline builder.</p></div></div>
        <label className="upload-card"><span className="upload-icon"><Plus /></span><strong>Choose source JSON files</strong><span>One to three files · JSON format</span><input type="file" accept=".json,application/json" multiple onChange={(event) => void uploadSources(event.target.files)} /></label>
        <div className="source-grid">{sources.map((source) => <article className="panel source-card" key={source.name}><div className="panel-title"><Table2 size={17} /><strong>{source.name}</strong><span className="count">{source.fields.length} columns</span></div><div className="field-list">{source.fields.map((field) => <div className="field-row" key={field.name}><span>{field.name}</span><code>{field.type}</code></div>)}</div></article>)}</div>
        {sources.length === 0 && <p className="empty">No sources uploaded yet.</p>}
      </section>}
      {page === "Pipeline Builder" && <section>
        <div className="page-heading"><div><p className="eyebrow">COMPOSE A VIEW</p><h1>Pipeline Builder</h1><p>Choose operations and order them to create a Datasphere graphical view.</p></div><div className="view-settings"><input className="view-name" value={viewName} onChange={(e) => setViewName(e.target.value)} aria-label="View name" placeholder="View name" />{goldenViews.length > 0 && <select className="view-name" aria-label="Base view" value={baseView} onChange={(e) => setBaseView(e.target.value)}>{goldenViews.map((view) => <option key={view} value={view}>{view}</option>)}</select>}</div></div>
        <div className="toolbar"><span>Add step</span>{templates.map((template) => <button className="secondary" key={template.id} onClick={() => addStep(template.id)}><Plus size={14} />{capitalize(template.operation)}</button>)}</div>
        <div className="flow">{["Source", ...steps.map((step) => capitalize(step.type)), "Output"].map((label, index) => <span className="flow-node" key={`${label}-${index}`}>{label}</span>)}</div>
        <div className="step-list">{steps.map((step, index) => <article className="panel step-card" key={`${step.type}-${index}`}><div className="step-heading"><span className="step-number">{index + 1}</span><strong>{capitalize(step.type)}</strong><div className="step-actions"><button onClick={() => moveStep(index, -1)} aria-label="Move step up">↑</button><button onClick={() => moveStep(index, 1)} aria-label="Move step down">↓</button><button onClick={() => setSteps((current) => current.filter((_, i) => i !== index))} aria-label="Delete step"><Trash2 size={15} /></button></div></div><StepForm step={step} sources={sources} columns={columns} templates={templates} onChange={(patch) => updateStep(index, patch)} /></article>)}</div>
        {steps.length === 0 && <div className="empty panel">Add a step to start building your pipeline.</div>}
        <div className="build-row"><button className="primary" disabled={!steps.length} onClick={() => void buildView()}>Build JSON</button></div>
        {build && <div className="results">
          <div className="result-head"><h2>Build result</h2><button className="secondary" onClick={() => void copyJson()}><Copy size={15} />Copy JSON</button><a className="secondary" href={`${API}${build.download_url}`} download><Download size={15} />Download JSON</a></div>
          <div className="panel"><h3>Validation report</h3>{build.validation.map((check) => <div className="validation-row" key={check.check}><span className={check.passed ? "pass" : "fail"}>{check.passed ? "PASS" : "FAIL"}</span><strong>{check.check}</strong><span>{check.reason}</span></div>)}</div>
          <div className="panel"><h3>Templates used</h3>{build.templates.map((template) => <span className={`badge ${template.status}`} key={template.id}>{template.id} · {template.status}</span>)}</div>
          <pre className="json-view">{JSON.stringify(build.json, null, 2)}</pre>
        </div>}
      </section>}
      {page === "Template Lab" && <TemplateLab templates={templates} refresh={refresh} setError={setError} setNotice={setNotice} />}
    </main>
  </div>;
}

function StepForm({ step, sources, columns, templates, onChange }: { step: Step; sources: Source[]; columns: { table: string; name: string; type: string }[]; templates: Template[]; onChange: (patch: Record<string, unknown>) => void }) {
  const sourceFields = (table: string) => sources.find((item) => item.name === table)?.fields ?? [];
  const choose = (label: string, key: string, values: string[], selected: string) => <label className="form-field">{label}<select value={selected} onChange={(e) => onChange({ [key]: e.target.value })}>{values.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>;
  if (step.type === "projection") return <div className="form-grid"><label className="form-field full">Keep columns<select multiple value={step.keep_columns as string[]} onChange={(e) => onChange({ keep_columns: Array.from(e.target.selectedOptions, (option) => option.value) })}>{columns.map((column) => <option key={`${column.table}.${column.name}`} value={column.name}>{column.table}.{column.name}</option>)}</select></label><label className="form-field full">Renames (source=output, comma separated)<input value={Object.entries(step.renames as Record<string, string>).map(([from, to]) => `${from}=${to}`).join(", ")} onChange={(e) => onChange({ renames: Object.fromEntries(e.target.value.split(",").map((pair) => pair.split("=").map((part) => part.trim())).filter((pair) => pair.length === 2 && pair[0] && pair[1])) })} /></label><p className="hint">Use Ctrl/⌘ to select multiple columns.</p></div>;
  if (step.type === "filter") return <div className="form-grid">{choose("Column", "column", columns.map((column) => column.name), String(step.column))}{choose("Operator", "operator", ["=", "!=", ">", ">=", "<", "<=", "in", "contains", "isNull", "isNotNull"], String(step.operator))}<label className="form-field">Values (comma separated)<input value={(step.values as unknown[]).map(String).join(", ")} onChange={(e) => onChange({ values: e.target.value.split(",").map((value) => value.trim()) })} /></label></div>;
  const join = step.type === "join";
  const leftKey = join ? "left_table" : "target_table";
  if (join || step.type === "association") {
    const firstPair = (step.key_pairs as { left_column: string; right_column: string }[])[0] ?? { left_column: "", right_column: "" };
    const updatePair = (field: "left_column" | "right_column", value: string) => onChange({ key_pairs: [{ ...firstPair, [field]: value }] });
    const leftTable = join ? String(step.left_table ?? "") : "";
    const rightTable = join ? String(step.right_table ?? "") : String(step.target_table ?? "");
    const leftColumns = join ? sourceFields(leftTable).map((field) => field.name) : columns.map((column) => column.name);
    const rightColumns = sourceFields(rightTable).map((field) => field.name);
    return <div className="form-grid">{choose(join ? "Left table" : "Source table", leftKey, sources.map((source) => source.name), String(step[leftKey] ?? ""))}{join && choose("Right table", "right_table", sources.map((source) => source.name), String(step.right_table ?? ""))}{join && choose("Join type", "join_type", ["inner", "left", "right", "full"], String(step.join_type ?? "inner"))}{!join && <label className="form-field">Association name<input value={String(step.association_name ?? "")} onChange={(e) => onChange({ association_name: e.target.value })} /></label>}<div className="form-field full"><span>Key columns</span><div className="key-pair"><label className="form-field">Left key<select value={firstPair.left_column} onChange={(e) => updatePair("left_column", e.target.value)}>{leftColumns.map((name) => <option key={name}>{name}</option>)}</select></label><label className="form-field">Right key<select value={firstPair.right_column} onChange={(e) => updatePair("right_column", e.target.value)}>{rightColumns.map((name) => <option key={name}>{name}</option>)}</select></label></div></div></div>;
  }
  const metadata = templates.find((template) => template.id === step.type) as (Template & { placeholders?: { name: string; type: string; description?: string }[] }) | undefined;
  const placeholders = metadata?.placeholders?.filter((item) => item.type !== "generated") ?? [];
  return <div className="form-grid">{placeholders.map((placeholder) => <label className="form-field" key={placeholder.name}>{placeholder.description || placeholder.name}<input value={String(step[placeholder.name] ?? "")} onChange={(e) => onChange({ [placeholder.name]: e.target.value })} /></label>)}{placeholders.length === 0 && <p className="hint">Set any template-specific values in the JSON editor in Template Lab.</p>}</div>;
}

function TemplateLab({ templates, refresh, setError, setNotice }: { templates: Template[]; refresh: () => Promise<void>; setError: (value: string) => void; setNotice: (value: string) => void }) {
  const [operation, setOperation] = useState("projection");
  const [fileA, setFileA] = useState<File | null>(null);
  const [fileB, setFileB] = useState<File | null>(null);
  const [learned, setLearned] = useState<Record<string, unknown> | null>(null);
  const [editor, setEditor] = useState("");
  const [selected, setSelected] = useState("");
  const [resultStatus, setResultStatus] = useState("verified");
  const [resultText, setResultText] = useState("");
  const [editorError, setEditorError] = useState("");
  const editorValid = useMemo(() => {
    if (!editor) return true;
    try { JSON.parse(editor); return true; } catch { return false; }
  }, [editor]);
  async function learn() {
    if (!fileA || !fileB) { setError("Choose both file A and file B."); return; }
    const form = new FormData(); form.append("file_a", fileA); form.append("file_b", fileB); form.append("operation", operation);
    try {
      const result = await request("/templates/learn", { method: "POST", body: form });
      setLearned(result); setSelected(result.id); setEditor(JSON.stringify({ template: result.template, manifest: result.manifest }, null, 2)); setError("");
    } catch (e) { setError(message(e)); }
  }
  async function save() {
    try {
      const parsed = JSON.parse(editor);
      await request(`/templates/${selected || operation}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(parsed) });
      setNotice("Draft template saved."); await refresh();
    } catch (e) { setEditorError(e instanceof SyntaxError ? "Editor content is not valid JSON." : message(e)); }
  }
  async function importResult() {
    try {
      await request(`/templates/${selected}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: resultStatus, error_text: resultText }) });
      setNotice("Import result saved."); await refresh();
    } catch (e) { setError(message(e)); }
  }
  async function loadTemplate(template: Template) {
    setSelected(template.id);
    try {
      const templateResponse = await fetch(`${API}/templates/${template.id}`);
      if (!templateResponse.ok) throw new Error("Template file is empty or unavailable. Learn it from files A and B.");
      const json = await templateResponse.json();
      setEditor(JSON.stringify(json, null, 2));
    } catch (e) { setError(message(e)); }
  }

  return <section>
    <div className="page-heading"><div><p className="eyebrow">LEARN FROM EXPORTS</p><h1>Template Lab</h1><p>Compare two real exports, edit a draft template, and record the Datasphere import result.</p></div></div>
    <div className="template-layout">
      <aside className="panel template-list"><div className="panel-title"><strong>Templates</strong></div>{templates.map((template) => <button className={selected === template.id ? "template-item selected" : "template-item"} key={template.id} onClick={() => void loadTemplate(template)}><span>{template.operation}</span><span className={`badge ${template.status}`}>{template.status}</span></button>)}{templates.find((template) => template.id === selected)?.last_import_result && <div className="import-summary"><strong>Last import: {templates.find((template) => template.id === selected)?.last_import_result?.status}</strong><p>{templates.find((template) => template.id === selected)?.last_import_result?.error_text || "No error text provided."}</p></div>}</aside>
      <div className="template-work">
        <div className="panel"><h2>Learn a template</h2><div className="form-grid"><label className="form-field">Operation<select value={operation} onChange={(e) => setOperation(e.target.value)}>{templates.map((template) => <option key={template.id} value={template.id}>{template.operation}</option>)}</select></label><label className="form-field">File A (before)<input type="file" accept=".json,application/json" onChange={(e) => setFileA(e.target.files?.[0] ?? null)} /></label><label className="form-field">File B (after)<input type="file" accept=".json,application/json" onChange={(e) => setFileB(e.target.files?.[0] ?? null)} /></label><button className="primary align-end" onClick={() => void learn()}>Compare A and B</button></div></div>
        {learned && <div className="panel"><h2>Changed paths</h2>{(["query", "elements", "uiModel"] as const).map((group) => <div className="diff-group" key={group}><h3>{group}</h3>{((learned.diff as Record<string, { path: string; old: unknown; new: unknown }[]>)[group] ?? []).map((change) => <div className="diff-row" key={change.path}><code>{change.path}</code><pre>- {JSON.stringify(change.old)}{"\n"}+ {JSON.stringify(change.new)}</pre></div>)}</div>)}</div>}
        <div className="panel"><h2>Draft template editor</h2><p className="hint">Edit placeholders and insertion paths as JSON. {editorValid ? "Valid JSON." : "Editor content is not valid JSON."}</p><textarea className="editor" spellCheck={false} value={editor} onChange={(e) => { setEditor(e.target.value); setEditorError(""); }} placeholder={'{"template": {}, "manifest": {}}'} /><div className="editor-footer"><span className="error-text">{editorError}</span><button className="primary" disabled={!editorValid} onClick={() => void save()}>Save draft</button></div></div>
        <div className="panel"><h2>Import result</h2><div className="form-grid"><label className="form-field">Result<select value={resultStatus} onChange={(e) => setResultStatus(e.target.value)}><option value="verified">Verified</option><option value="failed">Failed</option></select></label><label className="form-field full">Datasphere error text<textarea value={resultText} onChange={(e) => setResultText(e.target.value)} placeholder="Paste the import error, if any." /></label></div><button className="secondary" disabled={!selected} onClick={() => void importResult()}>Save import result</button></div>
      </div>
    </div>
  </section>;
}

function message(error: unknown) { return error instanceof Error ? error.message : "An unexpected error occurred."; }
function capitalize(text: string) { return text.charAt(0).toUpperCase() + text.slice(1); }
