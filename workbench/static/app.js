const state = {
  samples: [],
  products: [],
  voices: [],
  typeMeta: {},
  productTags: {},
  taskTimer: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  return res.json();
}

function badge(text, kind = "") {
  return `<span class="badge ${kind}">${esc(text || "待判断")}</span>`;
}

function md(text) {
  return esc(text || "").replace(/\n/g, "<br>");
}

async function load() {
  const data = await api("/api/bootstrap");
  state.samples = data.samples || [];
  state.products = data.products || [];
  state.voices = data.voices || [];
  state.typeMeta = data.typeMeta || {};
  state.productTags = data.productTags || {};
  renderAll();
}

function switchView(view) {
  $$(".nav-button").forEach((btn) => btn.classList.toggle("active", btn.dataset.view === view));
  $$(".view").forEach((section) => section.classList.toggle("active", section.id === `view-${view}`));
  const active = document.querySelector(`.nav-button[data-view="${view}"] span`);
  $("#viewTitle").textContent = active ? active.textContent : "工作台";
  if (window.lucide) lucide.createIcons();
}

function renderAll() {
  renderProductOptions();
  renderSampleTables();
  renderMissing();
  renderResults();
  renderProducts();
  renderVoices();
  toggleTypeFields();
  if (window.lucide) lucide.createIcons();
}

function renderProductOptions() {
  const el = $("#productOptions");
  if (!el) return;
  el.innerHTML = state.products.map((item) => `<option value="${esc(item.name)}"></option>`).join("");
}

function matches(item, query) {
  return !query || JSON.stringify(item).includes(query);
}

function renderSampleTables() {
  renderTable("市场参考", "#marketTable", "#marketSearch");
  renderTable("达人合作", "#kolTable", "#kolSearch");
  renderTable("官号发布", "#officialTable", "#officialSearch");
}

function renderTable(type, target, searchTarget) {
  const query = ($(searchTarget)?.value || "").trim();
  const rows = state.samples.filter((item) => item.sampleType === type && matches(item, query));
  $(target).innerHTML = rows.map(sampleCard).join("") || `<div class="empty">还没有${esc(type)}样本。</div>`;
}

function sampleCard(item) {
  const gpt = item.gpt || {};
  const result = gpt.result || null;
  const missing = item.missing || [];
  const metrics = item.metrics || {};
  const title = item.title || item.url || item.id;
  const kind = missing.length ? "risk" : result ? "" : "warn";
  return `
    <article class="sample-card">
      <div class="sample-main">
        <p class="eyebrow">${esc(item.sampleType)} · ${esc(item.contentForm || "未识别")} · ${esc(item.processMode || "未设置")}</p>
        <h3>${esc(title)}</h3>
        <p class="muted">${esc(item.creator || "账号未知")} ${item.product ? `｜${esc(item.product)}` : ""} ${item.publishDate ? `｜${esc(item.publishDate)}` : ""}</p>
        ${item.note ? `<p>${esc(item.note)}</p>` : ""}
        <div class="row wrap">
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
          <div><strong>${esc(metrics.impressions || item.impressions || "-")}</strong><span>曝光/播放</span></div>
          <div><strong>${esc(metrics.itemClicks || item.itemClicks || "-")}</strong><span>商品点击</span></div>
          <div><strong>${esc(metrics.orders || item.orders || "-")}</strong><span>订单/GMV</span></div>
        </div>
        <div class="actions">
          ${item.url ? `<a href="${esc(item.url)}" target="_blank">打开链接</a>` : ""}
          ${gpt.inbox?.relativePath ? `<span>${esc(gpt.inbox.relativePath)}</span>` : ""}
          ${result?.relativePath ? `<button data-result="${esc(result.id)}" class="text-button">查看分析</button>` : ""}
        </div>
      </div>
    </article>
  `;
}

function renderMissing() {
  const rows = state.samples.filter((item) => (item.missing || []).length);
  $("#missingList").innerHTML = rows.map((item) => `
    <article class="missing-card">
      <div>
        <p class="eyebrow">${esc(item.sampleType)} · ${esc(item.title || item.url || item.id)}</p>
        <h3>GPT 需要你补充</h3>
        <ul>${(item.missing || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        ${item.note ? `<p class="muted">备注：${esc(item.note)}</p>` : ""}
      </div>
      <div class="row wrap">
        ${item.url ? `<a class="secondary" href="${esc(item.url)}" target="_blank">打开笔记</a>` : ""}
        ${badge(item.status, "risk")}
      </div>
    </article>
  `).join("") || `<div class="empty">暂无待补资料。资料越完整，GPT 判断越少瞎猜。</div>`;
}

function resultSummary(result) {
  const s = result.status || {};
  return [
    s.decision && `判断：${s.decision}`,
    s.replicate_priority && `优先级：${s.replicate_priority}`,
    s.recommended_direction && `方向：${s.recommended_direction}`,
    s.recommended_title && `标题：${s.recommended_title}`,
  ].filter(Boolean);
}

function renderResults() {
  const rows = state.samples.filter((item) => item.gpt?.result);
  $("#resultList").innerHTML = rows.map((item) => {
    const result = item.gpt.result;
    const summary = resultSummary(result);
    return `
      <article class="result-card" id="result-${esc(result.id)}">
        <div class="result-head">
          <div>
            <p class="eyebrow">${esc(item.sampleType)} · ${esc(item.contentForm || "")}</p>
            <h3>${esc(item.title || item.url || item.id)}</h3>
          </div>
          ${badge(item.gpt.status || "已完成分析")}
        </div>
        ${summary.length ? `<div class="summary-grid">${summary.map((x) => `<div>${esc(x)}</div>`).join("")}</div>` : ""}
        <details open>
          <summary>查看 GPT 分析全文</summary>
          <div class="markdown-box">${md(result.analysisText || "暂无分析正文。")}</div>
        </details>
        <p class="muted">结果路径：${esc(result.relativePath)}</p>
      </article>
    `;
  }).join("") || `<div class="empty">还没有 GPT 分析结果。完整分析后，结果会出现在这里。</div>`;
}

function renderProducts() {
  $("#productCount").textContent = `${state.products.length} 个`;
  $("#productList").innerHTML = state.products.map((item) => `
    <article class="card">
      <h3>${esc(item.name)}</h3>
      <p>${esc(item.category || "未分类")} ${item.age ? `｜${esc(item.age)}` : ""} ${item.taste ? `｜${esc(item.taste)}` : ""}</p>
      <div class="row wrap">
        ${(item.forms || []).map((x) => badge(x, "info")).join("")}
        ${(item.needs || []).map((x) => badge(x)).join("")}
        ${(item.timing || []).map((x) => badge(x, "warn")).join("")}
        ${(item.contentTags || []).map((x) => badge(x, "info")).join("")}
      </div>
      ${item.scenes ? `<p><strong>场景：</strong>${esc(item.scenes)}</p>` : ""}
      ${item.raw ? `<details><summary>查看原始资料</summary><p class="markdown-box">${md(item.raw)}</p></details>` : ""}
    </article>
  `).join("") || `<div class="empty">还没有产品卡。后续分析会用产品卡判断承接方向和禁区。</div>`;
}

function renderVoices() {
  $("#voiceCount").textContent = `${state.voices.length} 条`;
  $("#voiceList").innerHTML = state.voices.map((item) => `
    <article class="card">
      <h3>${esc(item.text)}</h3>
      <p class="muted">${esc(item.source || "未标注来源")} ${item.product ? `｜${esc(item.product)}` : ""}</p>
    </article>
  `).join("") || `<div class="empty">还没有用户原声。</div>`;
}

function collectPayload() {
  const sampleType = $("#sampleType").value;
  const product = sampleType === "达人合作" ? $("#kolProduct").value : sampleType === "官号发布" ? $("#officialProduct").value : $("#marketProduct").value;
  return {
    url: $("#urlInput").value.trim(),
    title: $("#titleInput").value.trim(),
    sampleType,
    contentForm: $("#contentForm").value,
    processMode: $("#processMode").value,
    note: $("#noteInput").value.trim(),
    recordReason: $("#recordReason").value,
    product,
    creator: $("#creatorInput").value.trim(),
    cost: $("#costInput").value.trim(),
    collabType: $("#collabType").value,
    tracking: $("#tracking").value,
    initialJudgement: $("#initialJudgement").value,
    hasCart: $("#hasCart").value,
    objective: $("#objective").value,
    publishDate: $("#publishDate").value.trim(),
  };
}

function resetForm() {
  ["#urlInput", "#titleInput", "#noteInput", "#marketProduct", "#creatorInput", "#kolProduct", "#costInput", "#officialProduct", "#publishDate"].forEach((s) => { const el = $(s); if (el) el.value = ""; });
  $("#processMode").value = "只登记";
  $("#contentForm").value = "图文";
  $("#recordReason").value = "";
  $("#collabType").value = "";
  $("#tracking").value = "";
  $("#initialJudgement").value = "不确定";
  $("#hasCart").value = "";
  $("#objective").value = "";
}

function pollTask(taskId) {
  if (!taskId) return;
  clearInterval(state.taskTimer);
  state.taskTimer = setInterval(async () => {
    const task = await api(`/api/task?id=${encodeURIComponent(taskId)}`);
    $("#taskLog").textContent = `${task.status || "处理中"}\n${task.message || task.error || ""}\n${task.packageId ? `分析包：${task.packageId}` : ""}`;
    if (["失败", "待 GPT 分析", "分析包生成成功，GitHub 上传失败"].includes(task.status) || task.packageId) {
      clearInterval(state.taskTimer);
      await load();
    }
  }, 2500);
}

function toggleTypeFields() {
  const type = $("#sampleType")?.value || "市场参考";
  $$(".conditional").forEach((el) => el.classList.toggle("hidden", el.dataset.for !== type));
}

function bindEvents() {
  $$(".nav-button").forEach((btn) => btn.addEventListener("click", () => switchView(btn.dataset.view)));
  ["#marketSearch", "#kolSearch", "#officialSearch"].forEach((s) => $(s)?.addEventListener("input", renderSampleTables));
  $("#sampleType").addEventListener("change", toggleTypeFields);
  $("#submitSample").addEventListener("click", async () => {
    const payload = collectPayload();
    if (!payload.url && !payload.title) {
      $("#taskLog").textContent = "至少填写链接或标题。";
      return;
    }
    $("#taskLog").textContent = "正在保存样本...";
    const res = await api("/api/sample", { method: "POST", body: JSON.stringify(payload) });
    if (res.taskId) {
      $("#taskLog").textContent = `已保存，正在后台抓取并生成分析包。任务：${res.taskId}`;
      pollTask(res.taskId);
    } else {
      $("#taskLog").textContent = "已保存。";
      await load();
    }
    resetForm();
  });
  $("#addProduct").addEventListener("click", async () => {
    const payload = {
      name: $("#productName").value.trim(),
      category: $("#productCategory").value.trim(),
      age: $("#productAge").value.trim(),
      taste: $("#productTaste").value.trim(),
      scenes: $("#productScenes").value.trim(),
      raw: $("#productRaw").value.trim(),
    };
    if (!payload.name && !payload.raw) return;
    await api("/api/product", { method: "POST", body: JSON.stringify(payload) });
    ["#productName", "#productCategory", "#productAge", "#productTaste", "#productScenes", "#productRaw"].forEach((s) => $(s).value = "");
    await load();
  });
  $("#addVoice").addEventListener("click", async () => {
    const payload = { text: $("#voiceText").value.trim(), source: $("#voiceSource").value.trim(), product: $("#voiceProduct").value.trim() };
    if (!payload.text) return;
    await api("/api/voice", { method: "POST", body: JSON.stringify(payload) });
    ["#voiceText", "#voiceSource", "#voiceProduct"].forEach((s) => $(s).value = "");
    await load();
  });
  document.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-result]");
    if (!btn) return;
    switchView("results");
    setTimeout(() => document.getElementById(`result-${btn.dataset.result}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
  });
}

bindEvents();
load();
