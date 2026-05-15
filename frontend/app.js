const STATUS_LABEL = {
  queued: "대기 중",
  collecting: "자막·댓글 수집 중",
  filtering: "댓글 필터링 중",
  summarizing: "산문 요약 생성 중",
  done: "완료",
  failed: "실패",
};

const $form = document.getElementById("form");
const $url = document.getElementById("url");
const $status = document.getElementById("status");
const $result = document.getElementById("result");

$form.addEventListener("submit", async (e) => {
  e.preventDefault();
  $result.innerHTML = "";
  $status.textContent = "요청 전송...";

  try {
    const res = await fetch("/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: $url.value }),
    });
    if (!res.ok) throw new Error(`POST /jobs ${res.status}`);
    const body = await res.json();

    if (body.cached && body.result) {
      renderResult(body.result);
      return;
    }
    pollJob(body.job_id);
  } catch (err) {
    $status.innerHTML = `<span class="error">에러: ${err.message}</span>`;
  }
});

async function pollJob(jobId) {
  while (true) {
    const res = await fetch(`/jobs/${jobId}`);
    if (!res.ok) {
      $status.innerHTML = `<span class="error">에러: GET /jobs/${jobId} ${res.status}</span>`;
      return;
    }
    const meta = await res.json();
    const label = STATUS_LABEL[meta.status] || meta.status;
    const pct = Math.round((meta.progress || 0) * 100);
    $status.textContent = `${label}... ${pct}%`;

    if (meta.status === "done") {
      const r = await fetch(`/jobs/${jobId}/result`);
      renderResult(await r.json());
      return;
    }
    if (meta.status === "failed") {
      const msg = meta.error ? `${meta.error.code}: ${meta.error.message}` : "unknown";
      $status.innerHTML = `<span class="error">실패: ${msg}</span>`;
      return;
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
}

function renderResult(payload) {
  $status.textContent = "완료";
  const s = payload.summary || {};
  const stats = payload.filter_stats || {};
  $result.innerHTML = `
    <div class="summary">
      <div class="paragraph"><span class="label">영상 내용</span>${escape(s.content || "")}</div>
      <div class="paragraph"><span class="label">시청자 반응</span>${escape(s.reaction || "")}</div>
      <div class="paragraph"><span class="label">집중 장면</span>${escape(s.highlights || "")}</div>
    </div>
    <p style="color:#888;font-size:0.85em;">
      필터 통과: 일반 ${stats.passed_general}/${stats.total_general},
      타임스탬프 ${stats.passed_timestamp}/${stats.total_timestamp}
    </p>
  `;
}

function escape(s) {
  return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}
