/* 카메라 설치 장소 유형 — 백엔드 schemas.CameraCreate.place_type 과 같다. 실측(UC10)은 차내(버스·열차)만 (R21-D8 정정) */
export const PLACE_TYPES = [
  { value: "bus_in", label: "버스 차내" },
  { value: "train_in", label: "열차 차내" },
  { value: "platform", label: "승강장" },
] as const;

export const isInVehicle = (t: string) => t === "bus_in" || t === "train_in";
export const placeLabel = (t: string) => PLACE_TYPES.find((p) => p.value === t)?.label ?? t;
