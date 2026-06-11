const CONTENT_LEARNING_PROCESS_MODES = [
  "只登记",
  "先判断价值",
  "只拆结构",
  "分析产品承接",
  "生成创作大纲",
  "生成官号图文",
  "生成博主文字脚本",
  "完整分析",
  "等数据后分析",
];

function configureProcessModesOverride() {
  const select = document.querySelector("#processMode");
  if (!select) return;
  const current = select.value || "先判断价值";
  select.innerHTML = CONTENT_LEARNING_PROCESS_MODES.map((mode) => `<option>${esc(mode)}</option>`).join("");
  select.value = CONTENT_LEARNING_PROCESS_MODES.includes(current) ? current : "先判断价值";
}

function configureWorkbenchCopyOverride() {
  document.title = "小羊森林内容样本学习与创作转译系统";
  const brandSub = document.querySelector(".brand span");
  if (brandSub) brandSub.textContent = "内容学习与创作转译";
  const eyebrow = document.querySelector(".topbar .eyebrow");
  if (eyebrow) eyebrow.textContent = "小红书 / 样本学习 / 产品承接 / 创作转译";
  const status = document.querySelector(".status-pill span");
  if (status) status.textContent = "登记 → 初筛 → 产品承接 → 创作转译";
  const addPanelTitle = document.querySelector("#view-add .panel-head h2");
  if (addPanelTitle) addPanelTitle.textContent = "添加一条内容样本";
  const addPanelDesc = document.querySelector("#view-add .panel-head span");
  if (addPanelDesc) addPanelDesc.textContent = "先判断样本价值，再决定是否深拆或转译。";
  const principleTitle = document.querySelector("#view-add .muted-panel .panel-head h2");
  if (principleTitle) principleTitle.textContent = "系统判断原则";
  const principleDesc = document.querySelector("#view-add .muted-panel .panel-head span");
  if (principleDesc) principleDesc.textContent = "不是每条样本都值得复刻";
  const decisionItems = document.querySelectorAll("#view-add .decision-list div");
  const copy = [
    ["先判断价值", "样本进入后先判断保留、暂存还是丢弃，不默认每条都值得学。"],
    ["分样本池", "高价值复刻、结构参考、评论洞察、产品承接、反面避坑、暂存观察、低价值丢弃。"],
    ["看产品承接", "能承接才说怎么承接；不能承接就明确说不建议硬接。"],
    ["三种输出", "优先创作大纲；必要时再生成官号挂车图文或博主文字脚本。"],
  ];
  decisionItems.forEach((el, idx) => {
    if (!copy[idx]) return;
    el.innerHTML = `<strong>${esc(copy[idx][0])}</strong><span>${esc(copy[idx][1])}</span>`;
  });
}

function ensureSystemCheckPanelOverride() {
  const panel = document.querySelector("#view-add .muted-panel");
  if (!panel) return null;
  let box = document.querySelector("#systemCheckBox");
  if (box) return box;
  box = document.createElement("div");
  box.id = "systemCheckBox";
  box.className = "decision-list";
  box.style.marginBottom = "16px";
  box.innerHTML = `<div><strong>系统自检</strong><span>等待检查</span></div>`;
  const decisionList = panel.querySelector(".decision-list");
  if (decisionList) panel.insertBefore(box, decisionList);
  else panel.appendChild(box);
  return box;
}

function okText(value) {
  return value ? "通过" : "待确认";
}

function keywordHitText(map) {
  const rows = Object.entries(map || {});
  if (!rows.length) return "还没有可检查的关键词";
  const ok = rows.filter(([, value]) => value).map(([key]) => key);
  const miss = rows.filter(([, value]) => !value).map(([key]) => key);
  return `命中 ${ok.length}/${rows.length}${miss.length ? `；缺：${miss.join("、")}` : ""}`;
}

async function renderSystemCheckOverride() {
  const box = ensureSystemCheckPanelOverride();
  if (!box) return;
  box.innerHTML = `<div><strong>系统自检</strong><span>正在检查新逻辑是否接通...</span></div>`;
  try {
    const data = await fetch("/api/system_check", { cache: "no-store" }).then((res) => res.json());
    const latest = data.latestAnalysisInput || {};
    box.innerHTML = `
      <div><strong>系统自检</strong><span>${data.ok ? "基础链路通过" : "基础链路待确认"}</span></div>
      <div><strong>启动入口</strong><span>${data.serverV2Active ? "已运行 server_v2" : "未确认 server_v2"}</span></div>
      <div><strong>系统大脑</strong><span>${okText(data.promptFileExists && Object.values(data.promptKeywordHits || {}).every(Boolean))}｜${keywordHitText(data.promptKeywordHits)}</span></div>
      <div><strong>处理方式</strong><span>${data.processModesOk ? "已接入新选项" : "处理方式不完整"}</span></div>
      <div><strong>最新分析包</strong><span>${latest.exists ? `${latest.message}${latest.relativePath ? `｜${latest.relativePath}` : ""}` : latest.message || "还没有生成分析包"}</span></div>
      ${latest.exists ? `<div><strong>关键词检查</strong><span>${latest.ok ? "通过" : "待确认"}｜${keywordHitText(latest.keywordHits)}</span></div>` : ""}
    `;
  } catch (err) {
    box.innerHTML = `<div><strong>系统自检</strong><span>无法读取 /api/system_check，可能旧服务还在运行。请关闭旧黑窗口后重启。</span></div>`;
  }
}

const originalResetFormOverride = typeof resetForm === "function" ? resetForm : null;
resetForm = function resetFormOverride() {
  if (originalResetFormOverride) originalResetFormOverride();
  configureProcessModesOverride();
  configureWorkbenchCopyOverride();
  renderSystemCheckOverride();
  const process = document.querySelector("#processMode");
  if (process) process.value = "先判断价值";
  const form = document.querySelector("#contentForm");
  if (form && !form.value) form.value = "图文";
};

function isUrlLikeOverride(value) {
  const text = String(value || "").trim();
  return /^https?:\/\//i.test(text) || text.includes("xiaohongshu.com/explore/");
}

function noteIdFromUrlOverride(url) {
  const match = String(url || "").match(/explore\/([^/?#]+)/);
  return match ? match[1] : "";
}

function dateOnlyOverride(value) {
  const text = String(value || "").trim();
  const match = text.match(/\d{4}-\d{2}-\d{2}/);
  return match ? match[0] : "";
}

function readableSampleTitleOverride(item, analysisMeta = {}) {
  const manualTitle = String(item.title || "").trim();
  if (manualTitle && !isUrlLikeOverride(manualTitle)) return manualTitle;

  const analyzedTitle = String(analysisMeta.title || "").trim();
  if (analyzedTitle && !isUrlLikeOverride(analyzedTitle)) return analyzedTitle;

  const noteId = noteIdFromUrlOverride(item.url || manualTitle);
  return noteId ? `小红书笔记 ${noteId}` : (item.id || "未命名样本");
}

function readableAuthorOverride(item, analysisMeta = {}) {
  const manualAuthor = String(item.creator || "").trim();
  if (manualAuthor) return manualAuthor;

  const analyzedAuthor = String(analysisMeta.author || "").trim();
  if (analyzedAuthor) return analyzedAuthor;

  return "账号未知";
}

function readableContentFormOverride(item, result = null) {
  const raw = String(item.contentForm || "").trim();
  if (["图文", "视频"].includes(raw)) return raw;

  const analysisText = String(result?.analysisText || "");
  if (/视频里|视频中|口播|镜头|画面|字幕|剪辑/.test(analysisText)) return "视频";
  if (/图文|封面|内页|第\s*1\s*页|第一页|多页|图片/.test(analysisText)) return "图文";

  return "";
}

function sampleHeadlinePartsOverride(item, result = null, analysisMeta = {}) {
  const author = readableAuthorOverride(item, analysisMeta);
  const contentForm = readableContentFormOverride(item, result);
  const dateText = dateOnlyOverride(item.publishDate || item.createdAt || result?.status?.created_at || "");
  return [author, contentForm, dateText].filter(Boolean);
}

function sampleCard(item) {
  const gpt = item.gpt || {};
  const result = gpt.result || null;
  const analysisMeta = parseAnalysisMeta(result?.analysisText || "");
  const missing = item.missing || [];
  const title = readableSampleTitleOverride(item, analysisMeta);
  const metrics = cardMetrics(item, result, analysisMeta);
  const kind = missing.length ? "risk" : result ? "" : "warn";
  const reasonText = item.note || item.recordReason || "";
  const headlineParts = sampleHeadlinePartsOverride(item, result, analysisMeta);

  return `
    <article class="sample-card">
      <div class="sample-main">
        <h3>${headlineParts.map((x) => esc(x)).join(" ｜ ")}</h3>
        <p class="muted note-title">${esc(title)}</p>
        ${reasonText ? `<p>${esc(reasonText)}</p>` : ""}
        <div class="row wrap">
          ${badge(item.sampleType || "样本")}
          ${badge(item.processMode || "未标注", "info")}
          ${badge(item.status || gpt.status || "只登记", kind)}
          ${item.recordReason ? badge(item.recordReason, "info") : ""}
          ${item.tracking ? badge(item.tracking, "info") : ""}
          ${item.cost ? badge(`花费 ${item.cost}`, "warn") : ""}
          ${result ? badge("GPT 已分析") : ""}
          ${missing.length ? badge(`待补 ${missing.length} 项`, "risk") : ""}
        </div>
      </div>
      <div class="sample-side">
        <div class="mini-metrics">
          ${metrics.map((m) => `<div><strong>${esc(m.value)}</strong><span>${esc(m.label)}</span></div>`).join("")}
        </div>
        <div class="actions">
          ${item.url ? `<a href="${esc(item.url)}" target="_blank">打开原笔记</a>` : ""}
          ${gpt.inbox?.relativePath ? `<span>${esc(gpt.inbox.relativePath)}</span>` : ""}
          ${result?.relativePath ? `<button data-result="${esc(result.id)}" class="text-button">查看分析</button>` : ""}
        </div>
      </div>
    </article>
  `;
}

function renderMissing() {
  const rows = state.samples.filter((item) => (item.missing || []).length);
  $("#missingList").innerHTML = rows.map((item) => {
    const gpt = item.gpt || {};
    const result = gpt.result || null;
    const analysisMeta = parseAnalysisMeta(result?.analysisText || "");
    const title = readableSampleTitleOverride(item, analysisMeta);
    const headlineParts = sampleHeadlinePartsOverride(item, result, analysisMeta);
    const kind = (item.missing || []).length ? "risk" : "";

    return `
      <article class="missing-card">
        <div>
          <h3>${headlineParts.map((x) => esc(x)).join(" ｜ ")}</h3>
          <p class="muted note-title">${esc(title)}</p>
          <p class="eyebrow">GPT 需要你补充</p>
          <ul>${(item.missing || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
          ${item.note ? `<p class="muted">备注：${esc(item.note)}</p>` : ""}
          <div class="row wrap">
            ${badge(item.sampleType || "样本")}
            ${badge(item.processMode || "未标注", "info")}
            ${item.recordReason ? badge(item.recordReason, "info") : ""}
          </div>
        </div>
        <div class="row wrap">
          ${item.url ? `<a class="secondary" href="${esc(item.url)}" target="_blank">打开笔记</a>` : ""}
          ${badge(item.status || gpt.status || "待补资料", kind)}
        </div>
      </article>
    `;
  }).join("") || `<div class="empty">暂无待补资料。资料越完整，GPT 判断越少瞎猜。</div>`;
}

function resultCard(result, item = null) {
  const summary = resultSummary(result);
  const analysisMeta = parseAnalysisMeta(result?.analysisText || "");
  const title = item ? readableSampleTitleOverride(item, analysisMeta) : (analysisMeta.title || result.id);
  return `
    <article class="result-card" id="result-${esc(result.id)}">
      <div class="result-head">
        <div>
          <p class="eyebrow">${esc(item?.sampleType || "GPT 分析结果")} · ${esc(item?.contentForm || "")}</p>
          <h3>${esc(title)}</h3>
          ${analysisMeta.author ? `<p class="muted">${esc(analysisMeta.author)}</p>` : ""}
        </div>
        ${badge(item?.gpt?.status || result.status?.status || "已完成分析")}
      </div>
      ${summary.length ? `<div class="summary-grid">${summary.map((x) => `<div>${esc(x)}</div>`).join("")}</div>` : ""}
      <details open>
        <summary>查看 GPT 分析全文</summary>
        <div class="markdown-box">${md(result.analysisText || "暂无分析正文。")}</div>
      </details>
      <p class="muted">结果路径：${esc(result.relativePath)}</p>
    </article>
  `;
}

configureProcessModesOverride();
configureWorkbenchCopyOverride();
renderSystemCheckOverride();
const defaultProcessMode = document.querySelector("#processMode");
if (defaultProcessMode && defaultProcessMode.value === "只登记") defaultProcessMode.value = "先判断价值";
load();