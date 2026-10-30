/* 내 API 키 (RBAC T107·T108) — 일반 사용자가 연계 시스템마다 신청한다. 원문은 신청 직후 한 번만 보인다(서버는 해시만 저장).
   운영 관리자가 승인해야 호출에 쓰인다(승인 전 403 KEY_PENDING). 운영 관리자 본인의 신청은 바로 승인된다.
   2026-09-30: API 를 쓰려는 사람에게 필요한 건 키와 짧은 사용법 — 긴 문서(API 활용 화면)는 운영 관리 메뉴로 옮기고 여기에 3단계 사용법을 둔다. */
import { useCallback, useEffect, useState } from "react";
import { ApiError, del, fmtTime, get, post, type GateError } from "../../api/client";
import { GateBlock } from "../../components/GateBlock";

interface ApiKey { key_id: number; name: string; key_prefix: string; status: "pending" | "active" | "rejected"; created_at: string; approved_at: string | null;
  last_used_at: string | null; revoked_at: string | null }
const PUBLIC_API = "https://p4.sumzip.com/API";   // 공개 API 주소 (내부망은 http://<서버>:9544) — manual.md 와 같다
const EXAMPLE = `curl -H "X-API-Key: cvk_…" \\
  "${PUBLIC_API}/v1/next-vehicle?route_id=30300037&stop_id=30300037:42620&limit=4"`;
const STATE = (k: ApiKey) => k.revoked_at ? <span className="muted">폐기 {fmtTime(k.revoked_at)}</span>
  : k.status === "pending" ? <b style={{ color: "var(--status-normal)" }}>승인 대기</b>
  : k.status === "rejected" ? <span style={{ color: "var(--status-crowded)" }}>반려</span> : <b style={{ color: "var(--status-free)" }}>사용 중</b>;

export default function Keys() {
  const [rows, setRows] = useState<ApiKey[]>([]);
  const [name, setName] = useState("");
  const [fresh, setFresh] = useState<{ name: string; key: string; status: ApiKey["status"] } | null>(null);
  const [gate, setGate] = useState<GateError | null>(null);
  const [copied, setCopied] = useState(false);
  const fail = (err: unknown) => setGate(err instanceof ApiError && err.gate ? err.gate : { gate: "—", reason_code: "ERROR", reason: (err as Error).message, resolver_role: "self" });
  const load = useCallback(() => get<ApiKey[]>("/v1/auth/keys", { auth: true }).then(setRows).catch(fail), []);
  useEffect(() => { load(); }, [load]);
  const issue = async (e: React.FormEvent) => {
    e.preventDefault(); setGate(null); setCopied(false);
    try { const k = await post<ApiKey & { key: string }>("/v1/auth/keys", { auth: true, body: { name: name.trim() } }); setFresh({ name: k.name, key: k.key, status: k.status }); setName(""); load(); }
    catch (err) { fail(err); }
  };
  const revoke = async (k: ApiKey) => {
    if (!window.confirm(`«${k.name}» 키(${k.key_prefix}…)를 폐기한다. 이 키로 부르는 연계 시스템은 즉시 거부된다.`)) return;
    try { await del(`/v1/auth/keys/${k.key_id}`, { auth: true }); load(); } catch (err) { fail(err); }
  };
  const copy = async () => { if (!fresh) return; try { await navigator.clipboard.writeText(fresh.key); setCopied(true); } catch { /* 직접 선택해 복사 */ } };
  return (
    <>
      <div className="page-title"><h1 className="t-display-md">API 키</h1>
        <p className="t-caption">버스 혼잡도·도착 정보를 우리 API 로 받아 쓰려면 키가 필요하다</p></div>
      <section className="utility-card stack" aria-label="사용법" style={{ marginBottom: 16 }}>
        <h3 className="t-body-strong">사용법</h3>
        <ol style={{ margin: 0, paddingLeft: 20 }}>
          <li>아래에서 <b>키를 신청</b>한다 — 쓸 곳(전광판·앱 등)마다 하나씩. 키 원문은 신청 직후 한 번만 보인다.</li>
          <li><b>운영 관리자가 승인</b>하면 상태가 «사용 중»이 된다.</li>
          <li>요청 헤더 <code>X-API-Key</code> 에 키를 넣어 부른다.</li>
        </ol>
        <pre aria-label="호출 예" style={{ whiteSpace: "pre-wrap", wordBreak: "break-all" }}>{EXAMPLE}</pre>
        <p className="t-caption muted">주소 <code>{PUBLIC_API}</code> · 모든 엔드포인트와 입출력은 <a href={PUBLIC_API + "/docs"} target="_blank" rel="noreferrer">API 문서(Swagger)</a></p>
      </section>
      <div className="stack">
        <form className="utility-card stack" onSubmit={issue} aria-label="키 발급">
          <h3 className="t-body-strong">새 키 신청</h3>
          <label className="field"><span className="t-caption">쓸 곳 이름</span>
            <input className="input" maxLength={40} value={name} onChange={(e) => setName(e.target.value)} placeholder="정류장 전광판" /></label>
          <button className="btn btn-primary" style={{ alignSelf: "flex-start" }} disabled={!name.trim()}>신청</button>
          {fresh && (
            <div className="gate" role="status" style={{ borderColor: "var(--status-free)" }}>
              <p className="t-body-strong">«{fresh.name}» 키 — 지금 한 번만 보인다. 안전한 곳에 저장한다</p>
              <p className="t-caption">{fresh.status === "active" ? "운영 관리자 본인 신청이라 바로 쓸 수 있다." : "운영 관리자가 승인하면 쓸 수 있다. 승인 전에 부르면 403 KEY_PENDING."}</p>
              <code style={{ display: "block", wordBreak: "break-all", userSelect: "all", margin: "8px 0" }} aria-label="발급된 키">{fresh.key}</code>
              <div className="row"><button type="button" className="btn btn-pearl" onClick={copy}>{copied ? "복사됨" : "복사"}</button>
                <button type="button" className="btn btn-pearl" onClick={() => setFresh(null)}>저장했다 — 닫기</button></div>
            </div>
          )}
        </form>
        <section className="utility-card stack" aria-label="내 키 목록">
          <h3 className="t-body-strong">내 키 (사용 중 {rows.filter((r) => !r.revoked_at && r.status === "active").length} · 승인 대기 {rows.filter((r) => !r.revoked_at && r.status === "pending").length})</h3>
          <table><thead><tr><th>이름</th><th>앞자리</th><th>신청</th><th>마지막 사용</th><th>상태</th><th /></tr></thead><tbody>
            {rows.length === 0 && <tr><td colSpan={6} className="muted">신청한 키가 없다</td></tr>}
            {rows.map((k) => (
              <tr key={k.key_id}><td>{k.name}</td><td><code>{k.key_prefix}…</code></td><td>{fmtTime(k.created_at)}</td><td>{fmtTime(k.last_used_at)}</td>
                <td>{STATE(k)}</td>
                <td>{!k.revoked_at && <button className="btn btn-pearl" onClick={() => revoke(k)}>폐기</button>}</td></tr>
            ))}
          </tbody></table>
        </section>
      </div>
      {gate && <div style={{ marginTop: 16 }}><GateBlock error={gate} onRetry={() => setGate(null)} /></div>}
    </>
  );
}
