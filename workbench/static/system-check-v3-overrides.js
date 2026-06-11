async function renderSystemCheckOverride() {
  const box = ensureSystemCheckPanelOverride();
  if (!box) return;
  box.innerHTML = `<div><strong>系统自检</strong><span>正在检查新逻辑是否接通...</span></div>`;
  try {
    const data = await fetch("/api/system_check", { cache: "no-store" }).then((res) => res.json());
    const latest = data.latestAnalysisInput || {};
    const serverLabel = data.serverVersion
      ? `已运行 ${data.serverVersion}`
      : (data.serverV3Active ? "已运行 server_v3" : (data.serverV2Active ? "已运行 server_v2" : "未确认启动入口"));
    const analyzerLabel = data.analyzer ? `｜${data.analyzer}` : "";
    box.innerHTML = `
      <div><strong>系统自检</strong><span>${data.ok ? "基础链路通过" : "基础链路待确认"}</span></div>
      <div><strong>启动入口</strong><span>${serverLabel}${analyzerLabel}</span></div>
      <div><strong>系统大脑</strong><span>${okText(data.promptFileExists && Object.values(data.promptKeywordHits || {}).every(Boolean))}｜${keywordHitText(data.promptKeywordHits)}</span></div>
      <div><strong>处理方式</strong><span>${data.processModesOk ? "已接入新选项" : "处理方式不完整"}</span></div>
      <div><strong>最新分析包</strong><span>${latest.exists ? `${latest.message}${latest.relativePath ? `｜${latest.relativePath}` : ""}` : latest.message || "还没有生成分析包"}</span></div>
      ${latest.exists ? `<div><strong>关键词检查</strong><span>${latest.ok ? "通过" : "待确认"}｜${keywordHitText(latest.keywordHits)}</span></div>` : ""}
    `;
  } catch (err) {
    box.innerHTML = `<div><strong>系统自检</strong><span>无法读取 /api/system_check，可能旧服务还在运行。请关闭旧黑窗口后重启。</span></div>`;
  }
}

renderSystemCheckOverride();
