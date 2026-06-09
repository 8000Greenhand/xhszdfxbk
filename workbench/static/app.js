const state = {
  cases: [],
  insights: [],
  products: [],
  keywords: [],
  briefs: [],
  reviews: [],
  selectedCaseId: null,
  taskTimer: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  return res.json();
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function badge(text, kind = "") {
  return `<span class="badge ${kind}">${esc(text || "待判断")}</span>`;
}

function viewFile(path) {
  if (!path) return "";
  return path.replaceAll("\\", "/");
}

async function load() {
  const data = await api("/api/bootstrap");
  Object.assign(state, data);
  if (!state.selectedCaseId && state.cases.length) state.selectedCaseId = state.cases[0].id;
  renderAll();
}

function renderAll() {
  renderCases();
  renderAnalysis();
  renderInsights();
  renderProducts();
  renderKeywords();
  renderBriefSelectors();
  renderBriefs();
  renderReviews();
  if (window.lucide) lucide.createIcons();
}

function switchView(view) {
  $$(".nav-button").forEach((btn) => btn.classList.toggle("active", btn.dataset.view === view));
  $$(".view").forEach((section) => section.classList.toggle("active", section.id === `view-${view}`));
  const active = document.querySelector(`.nav-button[data-view="${view}"] span`);
  $("#viewTitle").textContent = active ? active.textContent : "工作台";
}

function renderCases() {
  const query = ($("#caseSearch")?.value || "").trim();
  const filter = ($("#caseFilter")?.value || "").trim();
  let cases = state.cases || [];
  if (query) {
    cases = cases.filter((item) => JSON.stringify(item).includes(query));
  }
  if (filter) {
    cases = cases.filter((item) => (item.analysis?.grade || "").startsWith(filter));
  }
  $("#caseTable").innerHTML = cases.map((item) => {
    const a = item.analysis || {};
    const m = item.metrics || {};
    const gradeKind = (a.grade || "").startsWith("A") ? "" : (a.grade || "").startsWith("D") ? "risk" : "warn";
    return `
      <button class="case-row" data-case-id="${esc(item.id)}">
        <div class="title-cell">
          <strong>${esc(item.title)}</strong>
          <span>${esc(item.author || "作者未知")} · ${esc(item.source || "市场样本")}</span>
        </div>
        <div>${badge(a.grade, gradeKind)}</div>
        <div>${badge(a.xiaoyangFit ? `适配 ${a.xiaoyangFit}` : "待适配", a.xiaoyangFit === "低" ? "risk" : "info")}</div>
        <div class="metric"><strong>${esc(m.collects || 0)}</strong><span>收藏</span></div>
        <div class="metric"><strong>${esc(m.saveRatio || 0)}</strong><span>收藏/点赞</span></div>
        <div>${badge(a.replicateDecision, a.riskLevel === "高" ? "risk" : "")}</div>
      </button>
    `;
  }).join("") || `<div class="empty">还没有案例。先粘贴一条小红书链接。</div>`;
  $$("#caseTable .case-row").forEach((row) => {
    row.addEventListener("click", () => {
      state.selectedCaseId = row.dataset.caseId;
      switchView("analysis");
      renderAnalysis();
    });
  });
}

function selectedCase() {
  return state.cases.find((item) => item.id === state.selectedCaseId) || state.cases[0];
}

function renderAnalysis() {
  const item = selectedCase();
  const empty = $("#analysisEmpty");
  const detail = $("#analysisDetail");
  if (!item) {
    empty.classList.remove("hidden");
    detail.classList.add("hidden");
    return;
  }
  empty.classList.add("hidden");
  detail.classList.remove("hidden");
  const a = item.analysis || {};
  const m = item.metrics || {};
  const img = item.files?.contactSheet ? `<img src="/local-image?path=${encodeURIComponent(item.files.contactSheet)}" alt="关键帧总览" />` : "";
  detail.innerHTML = `
    <section class="hero-panel">
      ${img}
      <div class="hero-body">
        <p class="eyebrow">${esc(a.viralType || "待判断")}</p>
        <h2>${esc(item.title)}</h2>
        <div class="facts">
          <div class="fact"><strong>${esc(m.likes || 0)}</strong><span>点赞</span></div>
          <div class="fact"><strong>${esc(m.collects || 0)}</strong><span>收藏</span></div>
          <div class="fact"><strong>${esc(m.comments || 0)}</strong><span>评论</span></div>
        </div>
        <div class="row">
          ${badge(a.grade)}
          ${badge(`适配 ${a.xiaoyangFit || "待判断"}`, a.xiaoyangFit === "低" ? "risk" : "info")}
          ${badge(`风险 ${a.riskLevel || "待判断"}`, a.riskLevel === "高" ? "risk" : "")}
        </div>
      </div>
    </section>
    <aside class="stack">
      ${analysisCard("为什么值得看", [
        `内容价值：${a.valueType || "待判断"}`,
        `账号打法：${a.accountStrategy?.type || "待判断"}`,
        `复刻优先级：${a.priorityLevel || "待判断"}（${a.priorityScore ?? "-"} 分）`,
        `收藏理由：${a.saveReason || ""}`,
        `评论动机：${a.commentReason || ""}`,
        `转化信号：${a.conversionSignal || "待判断"}`,
      ])}
      ${analysisCard("可复制性判断", [
        `可复制性：${a.reproducibilityScore ?? "-"} 分`,
        `证据充分度：${a.evidenceScore ?? "-"} 分`,
        `生产难度：${a.productionDifficulty || "待判断"}`,
        a.accountStrategy?.why,
        a.accountStrategy?.bestFor,
      ])}
      ${analysisCard("用户问题", [
        a.surfaceNeed,
        a.deepAnxiety,
        ...(a.userQuestions || []).slice(0, 4),
      ])}
      ${analysisCard("小羊森林适配", [
        `最终建议：${a.replicateDecision || "待判断"}`,
        `对应方向：${(a.productDirection || []).join("、")}`,
        `可复制：${(a.replicableParts || []).join("、")}`,
        `不要复制：${(a.notToCopy || []).join("、")}`,
      ])}
      ${analysisCard("需要补的证据", a.evidenceNeeded || [])}
      ${analysisCard("复刻执行法", a.replicatePlan || [])}
      ${analysisCard("反面风险", [
        ...(a.copyRisk || []),
        ...(a.negativeSignals || []),
      ])}
      ${analysisCard("安全表达", [
        ...(a.safeExpression || []),
        ...(a.riskWarnings || []),
      ])}
      ${item.files?.finalReport ? `<a class="primary" href="/open-file?path=${encodeURIComponent(item.files.finalReport)}" target="_blank"><i data-lucide="file-text"></i><span>打开原报告</span></a>` : ""}
    </aside>
  `;
  if (window.lucide) lucide.createIcons();
}

function analysisCard(title, lines) {
  const filtered = (lines || []).filter(Boolean);
  return `
    <section class="card">
      <h3>${esc(title)}</h3>
      <ul>${filtered.map((line) => `<li>${esc(line)}</li>`).join("")}</ul>
    </section>
  `;
}

function renderInsights() {
  $("#insightCount").textContent = `${state.insights.length} 条`;
  $("#insightList").innerHTML = state.insights.map((item) => `
    <article class="card">
      <h3>${esc(item.text)}</h3>
      <p>${esc(item.deepInsight)}</p>
      <div class="row">${badge(item.needType, "info")}${badge(`价值 ${item.value}`)}${badge(`风险 ${item.risk}`, item.risk === "高" ? "risk" : "")}</div>
      <p class="muted">${esc(item.topicSeed)}</p>
    </article>
  `).join("") || `<div class="empty">还没有用户原话。</div>`;
}

function renderProducts() {
  $("#productCount").textContent = `${state.products.length} 个`;
  $("#productList").innerHTML = state.products.map((item) => `
    <article class="card">
      <h3>${esc(item.name)}</h3>
      <p>${esc(item.form)} · ${esc(item.foodType)} · ${esc(item.status)}</p>
      <div class="row">${(item.internalDirections || []).map((x) => badge(x, "info")).join("")}</div>
      <p>对外表达：${esc((item.safeExpressions || []).join("、"))}</p>
      <p class="muted">缺失：${esc((item.missing || []).join("、") || "暂无")}</p>
    </article>
  `).join("") || `<div class="empty">还没有产品卡。</div>`;
}

function renderKeywords() {
  $("#keywordCount").textContent = `${state.keywords.length} 个`;
  $("#keywordList").innerHTML = state.keywords.slice(0, 120).map((item) => `
    <article class="card">
      <h3>${esc(item.keyword)}</h3>
      <p>${esc(item.topic)}</p>
      <div class="row">${badge(item.type, "info")}${badge(`优先级 ${item.priority}`)}${badge(`风险 ${item.risk}`, item.risk === "高" ? "risk" : "")}</div>
    </article>
  `).join("") || `<div class="empty">还没有关键词。</div>`;
}

function renderBriefSelectors() {
  $("#briefCase").innerHTML = state.cases.map((c) => `<option value="${esc(c.id)}">${esc(c.title)}</option>`).join("");
  $("#briefProduct").innerHTML = `<option value="">不指定产品</option>` + state.products.map((p) => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("");
  $("#briefInsight").innerHTML = `<option value="">不指定原话</option>` + state.insights.map((i) => `<option value="${esc(i.id)}">${esc(i.text.slice(0, 24))}</option>`).join("");
}

function renderBriefs() {
  $("#briefList").innerHTML = state.briefs.map((item) => `
    <article class="brief-card">
      <p class="eyebrow">${esc(item.goal)} · ${esc(item.status)}</p>
      <h3>${esc(item.topic)}</h3>
      <div class="columns">
        <div>${analysisCard("标题", item.titles)}</div>
        <div>${analysisCard("结构", item.structure)}</div>
        <div>${analysisCard("镜头", item.shots)}</div>
      </div>
      <p class="muted">开头：${esc(item.opening)}</p>
    </article>
  `).join("") || `<div class="empty">还没有创作任务。</div>`;
}

function renderReviews() {
  $("#reviewCount").textContent = `${state.reviews.length} 条`;
  $("#reviewList").innerHTML = state.reviews.map((item) => {
    const m = item.metrics || {};
    const kind = item.result === "成功样本" ? "" : item.result === "待优化样本" ? "risk" : "warn";
    return `
      <article class="card">
        <h3>${esc(item.title)}</h3>
        <p>${esc(item.objective)} · ${esc(item.publishDate || "未填发布时间")}</p>
        <div class="facts">
          <div class="fact"><strong>${esc(m.likes || 0)}</strong><span>点赞</span></div>
          <div class="fact"><strong>${esc(m.collects || 0)}</strong><span>收藏</span></div>
          <div class="fact"><strong>${esc(m.comments || 0)}</strong><span>评论</span></div>
        </div>
        <div class="row">${badge(item.result, kind)}${badge(`收藏比 ${m.saveRatio || 0}`, "info")}${badge(`问询 ${item.questionCount || 0}`)}</div>
        <ul>${(item.learning || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        <p class="muted">下一步：${esc(item.nextAction)}</p>
        ${item.manualConclusion ? `<p>${esc(item.manualConclusion)}</p>` : ""}
      </article>
    `;
  }).join("") || `<div class="empty">还没有发布复盘。</div>`;
}

async function pollTask(taskId) {
  clearInterval(state.taskTimer);
  state.taskTimer = setInterval(async () => {
    const task = await api(`/api/task?id=${encodeURIComponent(taskId)}`);
    $("#taskLog").textContent = `${task.status}\n${(task.log || []).join("\n")}`;
    if (["已完成", "失败", "missing"].includes(task.status)) {
      clearInterval(state.taskTimer);
      await load();
    }
  }, 2200);
}

function bindEvents() {
  $$(".nav-button").forEach((btn) => btn.addEventListener("click", () => switchView(btn.dataset.view)));
  $("#caseSearch").addEventListener("input", renderCases);
  $("#caseFilter").addEventListener("change", renderCases);
  $("#startAnalyze").addEventListener("click", async () => {
    const result = await api("/api/analyze", {
      method: "POST",
      body: JSON.stringify({ url: $("#urlInput").value, source: $("#sourceInput").value }),
    });
    if (!result.ok) {
      $("#taskLog").textContent = result.error;
      return;
    }
    $("#taskLog").textContent = "任务已开始";
    pollTask(result.task.id);
  });
  $("#addInsight").addEventListener("click", async () => {
    const result = await api("/api/insight", {
      method: "POST",
      body: JSON.stringify({
        text: $("#insightText").value,
        source: $("#insightSource").value,
        product: $("#insightProduct").value,
      }),
    });
    if (result.ok) {
      $("#insightText").value = "";
      await load();
    }
  });
  $("#addProduct").addEventListener("click", async () => {
    const result = await api("/api/product", {
      method: "POST",
      body: JSON.stringify({
        name: $("#productName").value,
        age: $("#productAge").value,
        raw: $("#productRaw").value,
      }),
    });
    if (result.ok) {
      $("#productName").value = "";
      $("#productRaw").value = "";
      await load();
    }
  });
  $("#addKeywords").addEventListener("click", async () => {
    const result = await api("/api/keywords", {
      method: "POST",
      body: JSON.stringify({ text: $("#keywordText").value }),
    });
    if (result.ok) {
      $("#keywordText").value = "";
      await load();
    }
  });
  $("#addBrief").addEventListener("click", async () => {
    const result = await api("/api/brief", {
      method: "POST",
      body: JSON.stringify({
        caseId: $("#briefCase").value,
        productId: $("#briefProduct").value,
        insightId: $("#briefInsight").value,
      }),
    });
    if (result.ok) await load();
  });
  $("#addReview").addEventListener("click", async () => {
    const result = await api("/api/review", {
      method: "POST",
      body: JSON.stringify({
        title: $("#reviewTitle").value,
        url: $("#reviewUrl").value,
        publishDate: $("#reviewDate").value,
        objective: $("#reviewObjective").value,
        likes: $("#reviewLikes").value,
        collects: $("#reviewCollects").value,
        comments: $("#reviewComments").value,
        commentText: $("#reviewCommentText").value,
        manualConclusion: $("#reviewConclusion").value,
      }),
    });
    if (result.ok) {
      ["#reviewTitle", "#reviewUrl", "#reviewDate", "#reviewObjective", "#reviewLikes", "#reviewCollects", "#reviewComments", "#reviewCommentText", "#reviewConclusion"].forEach((id) => $(id).value = "");
      await load();
    }
  });
}

bindEvents();
load();
