/* S5 샘플 선택 — 서버에 미리 둔 자유 이용 허가 사진·영상(GET /v1/web/samples)을 골라 로컬 파일처럼 넘긴다.
   받은 파일은 이 브라우저 안에서만 쓰고, 제출은 로컬 파일과 같은 경로(/v1/web/*)로 간다. 출처·라이선스를 함께 표시한다. */
import { useEffect, useState } from "react";
import { get, getBlob } from "../api/client";
import type { SampleMedia } from "../api/types";

const mb = (b: number) => `${(b / 1024 / 1024).toFixed(1)} MB`;

export function SamplePicker({ value, onPick }: { value: string; onPick: (name: string, file: File | null) => void }) {
  const [items, setItems] = useState<SampleMedia[] | null>(null);
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    get<SampleMedia[]>("/v1/web/samples").then(setItems).catch(() => setItems([]));
  }, []);

  const choose = async (name: string) => {
    setError("");
    const it = items?.find((s) => s.file === name);
    if (!it) { onPick("", null); return; }
    setLoading(name);
    try {
      const blob = await getBlob(`/v1/web/samples/${it.file.split("/").map(encodeURIComponent).join("/")}`);
      onPick(name, new File([blob], it.file.split("/").pop() ?? it.file, { type: it.content_type }));
    } catch (e) {
      setError(`샘플을 받지 못했다 — ${(e as Error).message}`);
      onPick("", null);
    } finally { setLoading(""); }
  };

  if (items && !items.length) return null;   // 서버에 샘플이 없으면 숨긴다
  const cur = items?.find((s) => s.file === value);
  return (
    <label className="field"><span className="t-caption">샘플 선택 (서버에 준비된 사진·영상)</span>
      <select className="input" value={value} onChange={(e) => choose(e.target.value)} disabled={!items || !!loading} aria-label="샘플 선택">
        <option value="">{items ? "— 샘플 없이 직접 파일 선택 —" : "샘플 목록 불러오는 중…"}</option>
        {items?.map((s) => <option key={s.file} value={s.file}>{s.kind === "video" ? "영상" : "사진"} · {s.title} ({mb(s.bytes)})</option>)}
      </select>
      {loading && <span className="t-caption muted">샘플 받는 중…</span>}
      {error && <span className="t-caption status status-crowded">{error}</span>}
      {cur && !loading && (
        <span className="t-caption muted">
          {cur.description ? `${cur.description} · ` : ""}출처: <a href={cur.source_url} target="_blank" rel="noreferrer">{cur.author}</a>, {cur.license}
        </span>
      )}
    </label>
  );
}
