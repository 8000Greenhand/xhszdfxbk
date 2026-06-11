function pendingAnalysisCard(item) {
  const gpt = item.gpt || {};
  const inbox = gpt.inbox || {};
  const title = typeof readableSampleTitleOverride === "function" ? readableSampleTitleOverride(item, {}) : (item.title || item.url || item.id);
  const headlineParts = typeof sampleHeadlinePartsOverride === "function" ? sampleHeadlinePartsOverride(item, null, {}) : [item.creator || "账号未知", item.contentForm || ""];
  const created = item.createdAt || inbox.createdAt || "";
  return `
    <article class="result-card pending-result-card" id="pending-${esc(item.id || inbox.id || inbox.folder)}">
      <div class="result-head">
        <div>
          <p class="eyebrow">${esc(item.sampleType || "样本")} · ${esc(item.processMode || "待分析")}</p>
          <h3>${esc(title)}</h3>
          <p class="muted">${esc(headlineParts.filter(Boolean).join(" ｜ "))}</p>
        </div>
        ${badge("待 GPT 分析", "warn")}
      </div>
      <div class="summary-grid">
        <div>状态：分析包已生成，还不是最终 GPT 分析结果</div>
        <div>处理方式：${esc(item.processMode || "未标注")}</div>
        <div>创建时间：${esc(created || "未记录")}</div>
        <div>分析包：${esc(inbox.relativePath || item.analysisPackageId || "未找到路径")}</div>
      </div>
      <details>
        <summary>这是什么意思？</summary>
        <div class="markdown-box">
          这张卡表示系统已经把笔记整理成 analysis_input.md，并且已经按“样本初筛 → 样本池分类 → 产品承接 → 创作出口”的新逻辑生成了给 GPT 的输入包。<br><br>
          但它还没有对应的 analysis_result.md，所以还不能算“已完成分析”。等 GPT 分析结果写回 analysis_results 后，这张卡会变成“已完成分析”。
        </div>
      </details>
      ${item.url ? `<p class="muted">原笔记：${esc(item.url)}</p>` : ""}
    </article>
  `;
}

function completedResultItemsOverride() {
  const linked = state.samples.filter((item) => item.gpt?.result);
  const linkedIds = new Set(linked.map((item) => item.gpt.result.id));
  const orphanResults = Object.values(state.analysisResults || {}).filter((result) => !linkedIds.has(result.id));
  return { linked, orphanResults };
}

function renderResults() {
  const pending = state.samples.filter((item) => item.gpt?.inbox && !item.gpt?.result);
  const { linked, orphanResults } = completedResultItemsOverride();
  const html = [
    pending.length ? `<div class="empty" style="margin-bottom:12px; text-align:left;">待 GPT 分析：${pending.length} 条。它们已经生成分析包，但还没有写回最终分析结果。</div>` : "",
    ...pending.map(pendingAnalysisCard),
    linked.length || orphanResults.length ? `<div class="empty" style="margin:16px 0 12px; text-align:left;">已完成分析：${linked.length + orphanResults.length} 条</div>` : "",
    ...linked.map((item) => resultCard(item.gpt.result, item)),
    ...orphanResults.map((result) => resultCard(result, null)),
  ].join("");
  $("#resultList").innerHTML = html || `<div class="empty">还没有 GPT 分析包或分析结果。保存一条需要分析的样本后，会先出现在“待 GPT 分析”。</div>`;
}

load();
