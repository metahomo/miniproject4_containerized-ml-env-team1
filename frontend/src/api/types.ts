/* 계약 타입 — contracts/openapi.yaml 에서 손으로 옮긴 최소 집합. `npm run gen:api` 로 전체 생성본을 덮어쓸 수 있다. */
export type CrowdingLevel = "free" | "normal" | "crowded" | "uncertain";
export type BasisType = "measured" | "no_measurement" | "unavailable";
export type ReadinessState = "ready" | "preparing" | "unavailable";

export interface Warning { code: string; detail?: string | null }

export interface DetectorStatus {
  kind: string; model: string; loaded: boolean; load_seconds?: number | null; warmed_up_at?: string | null;
  last_infer_ms?: number | null; note?: string | null;
}
export interface Readiness { readiness: ReadinessState; updated_at: string; model_commit?: string | null; detector?: DetectorStatus | null }

export interface Assessment {
  assessment_id: number; camera_id: string; captured_at?: string | null;
  occupied_area_ratio: number; vacant_capacity_ratio: number; crowding_level: CrowdingLevel; is_reference_only: boolean;
  person_count: number; capacity?: number | null; over_capacity?: boolean; remaining_persons?: number | null; remaining_not_computable: boolean; mean_confidence: number;
  warnings: Warning[]; notice: string; processed_at: string; response_ms?: number | null;
  versions: { roi_id: number; spec_id?: number | null; threshold_policy_id: number; model_commit: string };
}
export interface MeasurementStatus {
  vehicle_id: string; vacant_ratio_agg: number; crowding_level_agg: CrowdingLevel; coverage_num: number; coverage_den: number; persons_sum?: number | null; capacity?: number | null;
  partial_coverage: boolean; measured_at: string; expires_at: string; applied_validity_minutes: number; demo_mode: boolean; already_expired: boolean;
}
export interface MeasurementResult { assessment: Assessment; measurement: MeasurementStatus }
export interface NextVehicleItem {
  vehicle_id?: string | null; expected_arrival_at?: string | null; basis_type: BasisType; vacant_ratio?: number | null; persons_sum?: number | null; capacity?: number | null;
  crowding_level?: CrowdingLevel | null; measured_at?: string | null; coverage_num?: number | null; coverage_den?: number | null; warnings: Warning[];
}
export interface NextVehicleResponse {
  route_id: string; stop_id: string; place_kind: string; vehicles: NextVehicleItem[]; applied_validity_minutes: number;
  validity_source: string; notice: string; demo_mode: boolean; fetched_at: string; source_status: string;
}
export interface CameraStatus {
  camera_id: string; place_type: string; route_id?: string | null; stop_id?: string | null; vehicle_type_id?: string | null;
  has_roi: boolean; roi_stale: boolean; has_capacity: boolean; has_mapping: boolean; vehicle_id?: string | null; capacity?: number | null;
  powered?: boolean;   // 카메라 전원 (S2b). off 면 진단 요청 거부 (G4 CAMERA_POWER_OFF)
}
/** S2b 카메라 전원 관리 표 한 행 (GET /v1/admin/camera-power) */
export interface CameraPowerRow {
  camera_id: string; mode: "rail" | "bus"; place_type: string; route_id?: string | null; route_name?: string | null; vehicle_id?: string | null;
  car_position?: number | null; run_state?: "running" | "stopped" | null; capacity?: number | null; persons?: number | null; density?: number | null;
  crowding_level?: string | null; last_diagnosed_at?: string | null; powered: boolean; powered_at?: string | null; operation: "normal" | "offline" | "off";
  frame_source?: string | null; poll_interval_s: number; last_error?: string | null;
}
export interface Roi { roi_id: number; camera_id: string; polygon: number[][]; vertex_count: number; area: number; roi_area_m2?: number | null; footprint_m2?: number | null; effective_from: string; superseded_at?: string | null; created_by: string }
export interface Mapping { map_id: number; camera_id: string; vehicle_id: string; vehicle_type_id?: string | null; verify_status: string; verified_at?: string | null; effective_from: string; input_method: string; sibling_cameras: string[] }
export interface ThresholdPolicy { policy_id: number; free_min_ratio: number; crowded_max_ratio: number; count_conf_min?: number | null; effective_from: string; created_at: string; created_by: string; is_current: boolean; is_scheduled?: boolean }
export interface ValidityPreviewRow { route_id: string; route_name?: string | null; headway_minutes?: number | null; validity_minutes: number; validity_source: string }
export interface ValidityPolicyView { policy: Record<string, unknown> & { demo_on?: boolean; demo_end_at?: string | null; factor?: number; cap_minutes?: number; default_minutes?: number; window_minutes?: number; route_exceptions?: { route_id: string; minutes: number }[] }; preview: ValidityPreviewRow[] }
export interface OpsStatus { readiness: Readiness; demo_on: boolean; demo_end_at?: string | null; roi_stale_cameras: string[]; expired_measurements_today: number }
export interface GateEvent { event_id: number; gate_code: string; screen_code: string; subject_kind: string; subject_id: string; occurred_at: string; reason_code: string; reason_text?: string | null; resolver_role: string; request_sent_at?: string | null; request_sent_by?: string | null; resolved_at?: string | null }
export interface BatchItem { seq: number; status: string; assessment?: Assessment; reject?: { gate: string; reason: string } }
export interface BatchResult { batch_id: number; camera_id: string; items: BatchItem[]; consistency: { roi_id: number; spec_id?: number | null; threshold_policy_id: number; frames_discarded: number; audit_records: number } }
export interface VerificationRun { run_id: number; batch_id: number; ratio_match_rate: number; level_match_rate: number; verdict: string; versions: Record<string, unknown>; items: Array<Record<string, unknown>> }
export interface ApiGuide { version: string; updated_at: string; readiness: Readiness; catalog: Array<{ feature_code: string; uc_ref: string; path?: string | null; method?: string | null; input_desc: string; output_desc: string; error_reasons?: string | null; warning_types?: string | null }>; guideline_md: string; manual_md: string; model_card_md: string; openapi_url: string }
export interface Integration { integration_id: number; instance_id: number; registered_at: string; registered_by: string; test_request_id?: number | null; first_response_ms?: number | null; status: string; reverted_reason?: string | null }

/* 규격 변환 — /v1/web/* 응답 (웹 화면 제출 경로) */
export interface Normalization {
  applied: boolean; steps: string[];
  from: { format: string; width: number; height: number; bytes?: number | null };
  to: { format: string; width: number; height: number; bytes?: number | null };
}
export type WebAssessment = Assessment & { normalization?: Normalization };
export interface VideoInfo { width: number; height: number; fps: number; frame_count: number; duration_s: number; codec: string }
export interface VideoItem {
  t: number; status: "accepted" | "rejected"; assessment?: Assessment;
  reject?: { gate?: string; reason_code?: string; reason?: string }; smoothed_vacant_ratio?: number | null;
}
/** GET /v1/web/samples — 서버에 미리 둔 자유 이용 허가 사진·영상 */
export interface SampleMedia {
  file: string; title: string; description?: string; kind: "image" | "video"; bytes: number; content_type: string;
  source_url: string; license: string; author: string;
}
export interface VideoResult {
  camera_id: string; video: VideoInfo; interval_s: number; requested_interval_s?: number | null; mode: "interval" | "single";
  items: VideoItem[]; smooth_window: number;
  summary: { frames: number; accepted: number; uncertain: number; rejected: number; vacant_min?: number | null; vacant_max?: number | null; vacant_median?: number | null };
}
// T099 이용자 조회 — 이름으로 찾기, 버스 번호로 상태
export interface RouteRef { route_id: string; route_name: string; route_no: string; mode: string }
export interface StopRef { stop_id: string; route_id: string; route_name: string; route_no: string; stop_name: string }
export type VehicleStatus = NextVehicleItem & { expires_at?: string | null; demo_mode: boolean; notice: string };
