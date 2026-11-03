import os
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
SUMTONG_ROOT = os.path.abspath(os.path.join(PROJECT_DIR, ".."))

# 1. 폰트 등록 (맑은 고딕)
WINDIR = os.environ.get("WINDIR", "C:\\Windows")
font_normal = os.path.join(WINDIR, "Fonts", "malgun.ttf")
font_bold = os.path.join(WINDIR, "Fonts", "malgunbd.ttf")

pdfmetrics.registerFont(TTFont("Malgun", font_normal))
pdfmetrics.registerFont(TTFont("Malgun-Bold", font_bold))

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(num_pages)
            super().showPage()
        super().save()

    def draw_footer(self, page_count):
        self.saveState()
        self.setFont("Malgun", 8.5)
        self.setFillColor(colors.HexColor("#718096"))
        self.setStrokeColor(colors.HexColor("#CBD5E0"))
        self.setLineWidth(0.5)
        self.line(36, 32, 559, 32)
        self.drawString(36, 20, "sumtong / 13-yolo11-distance | Docker 환경 구축 및 CPU/GPU 전환 보고서")
        page_str = f"페이지 {self._pageNumber} / {page_count}"
        self.drawRightString(559, 20, page_str)
        self.restoreState()

def build_pdf(output_pdf_path):
    os.makedirs(os.path.dirname(output_pdf_path), exist_ok=True)
    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=40
    )

    title_style = ParagraphStyle(
        "DocTitle",
        fontName="Malgun-Bold",
        fontSize=17,
        leading=23,
        textColor=colors.HexColor("#1A365D"),
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        "DocSubTitle",
        fontName="Malgun",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#4A5568"),
        spaceAfter=10
    )
    h1_style = ParagraphStyle(
        "SectionH1",
        fontName="Malgun-Bold",
        fontSize=11.5,
        leading=16,
        textColor=colors.HexColor("#2B6CB0"),
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True
    )
    h2_style = ParagraphStyle(
        "SectionH2",
        fontName="Malgun-Bold",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#2D3748"),
        spaceBefore=7,
        spaceAfter=3,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        "BodyDark",
        fontName="Malgun",
        fontSize=8.5,
        leading=13,
        textColor=colors.HexColor("#2D3748"),
        spaceAfter=4
    )
    box_style = ParagraphStyle(
        "BoxContent",
        fontName="Malgun",
        fontSize=8.2,
        leading=12,
        textColor=colors.HexColor("#1A202C")
    )
    code_style = ParagraphStyle(
        "CodeText",
        fontName="Malgun",
        fontSize=7.8,
        leading=11,
        textColor=colors.HexColor("#C53030")
    )
    th_style = ParagraphStyle(
        "THStyle",
        fontName="Malgun-Bold",
        fontSize=8.0,
        leading=11,
        textColor=colors.white,
        alignment=1
    )
    td_style = ParagraphStyle(
        "TDStyle",
        fontName="Malgun",
        fontSize=7.8,
        leading=11,
        textColor=colors.HexColor("#2D3748")
    )
    td_bold_style = ParagraphStyle(
        "TDBoldStyle",
        fontName="Malgun-Bold",
        fontSize=7.8,
        leading=11,
        textColor=colors.HexColor("#1A365D")
    )

    story = []

    # =========================================================================
    # 헤더 섹션
    # =========================================================================
    story.append(Paragraph("YOLO11 버스 객실 분석 파이프라인 Docker 환경 구축 보고서 (v1.2)", title_style))
    story.append(Paragraph("<b>[방안 A] 독립 도커 컨테이너(yolo11-bus-distance:1.2) 환경 패키징 및 CPU 시연 · GPU 운영 가이드</b>", subtitle_style))

    # 메타 정보 박스
    meta_data = [
        [
            Paragraph("<b>프로젝트</b>: miniproject4_containerized-ml-env-team1", box_style),
            Paragraph("<b>작업 디렉터리</b>: 13-yolo11-distance", box_style),
        ],
        [
            Paragraph("<b>구축 방식</b>: [방안 A] 올인원 독립 실행형 컨테이너", box_style),
            Paragraph("<b>기본 실행 환경</b>: CPU 시연 모드 (경량 빌드)", box_style),
        ],
        [
            Paragraph("<b>적용 파이프라인</b>: 이중 모델 융합 추론 + 데이터 증강/학습", box_style),
            Paragraph("<b>이미지 버전</b>: yolo11-bus-distance:1.2 (v1.2)", box_style)
        ]
    ]
    t_meta = Table(meta_data, colWidths=[260, 263])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EDF2F7")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E0")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 7),
        ('RIGHTPADDING', (0,0), (-1,-1), 7),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 8))

    # =========================================================================
    # 1. 도커화 아키텍처 전략: [방안 A] 독립 도커 이미지 환경 구성
    # =========================================================================
    story.append(Paragraph("1. 도커화 아키텍처 전략: [방안 A] 독립 도커 이미지 환경 구성", h1_style))
    story.append(Paragraph(
        "본 프로젝트의 컴퓨터 비전 파이프라인(YOLO11 기반 객체 거리 측정 및 YOLOv8 Head 이중 모델 융합 추론, 데이터 증강 및 파인튜닝)을 "
        "어디서나 즉시 실행 및 검증할 수 있도록 <b>[방안 A] 독립 도커 이미지 환경</b>으로 구축하였습니다. "
        "전체 웹 백엔드 서버에 결합되지 않고 독립 컨테이너로서 연구·검증·학습·추론 전체 사이클을 완전하게 재현합니다.",
        body_style
    ))

    arch_compare = [
        [Paragraph("구분", th_style), Paragraph("[방안 A] 독립 도커 이미지 (채택)", th_style), Paragraph("[방안 B] 프로젝트 분리형 (기존)", th_style)],
        [
            Paragraph("<b>컨테이너 구성</b>", td_bold_style),
            Paragraph("단독 <code>yolo11-runner</code> 올인원 서비스", td_style),
            Paragraph("<code>trainer</code> 및 <code>backend</code> 2개 서비스 분리", td_style)
        ],
        [
            Paragraph("<b>수행 범위</b>", td_bold_style),
            Paragraph("데이터 증강 → 분할 → 학습 → 이중 모델 추론 → 리포트", td_style),
            Paragraph("학습(trainer) / 웹 API 서빙(backend) 분할", td_style)
        ],
        [
            Paragraph("<b>장점</b>", td_bold_style),
            Paragraph("외부 서비스(DB/Nginx/Web) 종속 없이 즉시 시연 및 단독 재현 가능", td_style),
            Paragraph("대규모 마이크로서비스 운영 시 서비스별 스케일아웃에 유리", td_style)
        ],
        [
            Paragraph("<b>시연 적합성</b>", td_bold_style),
            Paragraph("<b>최상</b> (명령어 1줄로 추론 및 시각화 결과 즉시 산출)", td_style),
            Paragraph("보통 (전체 Compose 스택 및 환경변수 사전 준비 필요)", td_style)
        ]
    ]
    t_comp = Table(arch_compare, colWidths=[80, 243, 200])
    t_comp.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2B6CB0")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E0")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F7FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_comp)
    story.append(Spacer(1, 8))

    # =========================================================================
    # 2. 도커 환경 핵심 구성 및 볼륨 설계
    # =========================================================================
    story.append(Paragraph("2. Dockerfile 및 docker-compose.yml 상세 설계", h1_style))
    story.append(Paragraph(
        "<b>(1) CPU 경량화 Dockerfile 최적화</b><br/>"
        "• 기본 베이스로 <code>python:3.11-slim</code>을 채택하고, PyTorch 공식 CPU 휠(<code>--index-url https://download.pytorch.org/whl/cpu</code>)을 "
        "설치하여 CUDA 툴킷이 포함된 수 GB의 불필요한 용량과 빌드 시간을 획기적으로 절감하였습니다.<br/>"
        "• <code>requirements.txt</code> 설치 시 <code>grep -vE '^(torch|torchvision|nvidia-)=='</code> 필터링을 거쳐 CPU 전용 라이브러리가 덮어쓰여지지 않도록 보호했습니다.<br/>"
        "• 빌드 컨텍스트를 <code>13-yolo11-distance</code> 자체로 단순화하여 컨테이너 빌드 효율을 극대화했습니다.",
        body_style
    ))

    story.append(Paragraph("<b>(2) 호스트-컨테이너 간 볼륨 매핑 구조</b>", h2_style))
    vol_table = [
        [Paragraph("호스트 경로", th_style), Paragraph("컨테이너 경로", th_style), Paragraph("권한", th_style), Paragraph("역할 및 데이터 내용", th_style)],
        [
            Paragraph("<code>../backend/models</code>", td_style),
            Paragraph("<code>/app/backend/models</code>", td_style),
            Paragraph("ro (읽기전용)", td_style),
            Paragraph("공유 가중치 (head_crowdhuman_n1280.pt, yolo11n.pt)", td_style)
        ],
        [
            Paragraph("<code>../backend/samples</code>", td_style),
            Paragraph("<code>/app/backend/samples</code>", td_style),
            Paragraph("ro (읽기전용)", td_style),
            Paragraph("실제 버스 객실 검증 이미지 (bus_full.jpg, bus_empty.jpg)", td_style)
        ],
        [
            Paragraph("<code>./data</code>", td_style),
            Paragraph("<code>/app/data</code>", td_style),
            Paragraph("rw (읽기/쓰기)", td_style),
            Paragraph("원천 이미지 및 증강 데이터 풀 (sample.jpg 등)", td_style)
        ],
        [
            Paragraph("<code>./datasets</code>", td_style),
            Paragraph("<code>/app/datasets</code>", td_style),
            Paragraph("rw (읽기/쓰기)", td_style),
            Paragraph("YOLO 학습용 train/val 분할 데이터셋 (data.yaml)", td_style)
        ],
        [
            Paragraph("<code>./results</code>", td_style),
            Paragraph("<code>/app/results</code>", td_style),
            Paragraph("rw (읽기/쓰기)", td_style),
            Paragraph("추론 결과 이미지 및 PDF/HTML 리포트 산출물", td_style)
        ]
    ]
    t_vol = Table(vol_table, colWidths=[105, 115, 60, 243])
    t_vol.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2B6CB0")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E0")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F7FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_vol)
    story.append(Spacer(1, 8))

    # =========================================================================
    # 3. 파이프라인 코드 유연화 (호스트/도커 겸용)
    # =========================================================================
    story.append(Paragraph("3. 파이프라인 코드 유연화 (컨테이너·호스트 완전 호환)", h1_style))
    story.append(Paragraph(
        "도커 환경과 기존 로컬 개발 환경 모두에서 무수정 동작할 수 있도록 파이프라인 코드를 유연화하였습니다.<br/>"
        "• <b>환경 변수 우선 탐색</b>: <code>CV_MODELS_DIR</code> 환경 변수를 지원하여 컨테이너 마운트 경로(<code>/app/backend/models</code>)를 "
        "우선 참조하고, 미지정 시 로컬 상대 경로(<code>../../backend/models</code>)로 자동 폴백합니다.<br/>"
        "• <b>실행 디바이스 자동 감지</b>: <code>DualModelVacancyPipeline(..., device=None)</code> 초기화 시 "
        "<code>torch.cuda.is_available()</code>을 자동 판별하여 GPU 가용 환경에서는 'cuda', CPU 환경에서는 'cpu'로 설정하며, "
        "추론(<code>infer</code>) 시 <code>predict(..., device=self.device)</code>에 직접 전달되도록 개선했습니다.",
        body_style
    ))

    # =========================================================================
    # 4. CPU 모드 시연 실행 절차
    # =========================================================================
    story.append(Paragraph("4. CPU 모드 시연 실행 절차 (Command Reference)", h1_style))
    story.append(Paragraph(
        "시연은 <code>docker compose run</code> 명령어를 통해 즉시 수행할 수 있습니다:",
        body_style
    ))

    cmd_box = [
        [Paragraph(
            "<b>1) 이미지 빌드:</b><br/>"
            "<font color='#C53030'>docker compose -f 13-yolo11-distance/docker-compose.yml build</font><br/><br/>"
            "<b>2) 기본 샘플 이미지(data/sample.jpg) 이중 모델 융합 추론:</b><br/>"
            "<font color='#C53030'>docker compose -f 13-yolo11-distance/docker-compose.yml run --rm yolo11-runner \\<br/>"
            "&nbsp;&nbsp;python scripts/test_dual_vacancy.py --source /app/data/sample.jpg --out /app/results/output_sample.jpg</font><br/><br/>"
            "<b>3) 백엔드 버스 실사(bus_full.jpg) 융합 추론:</b><br/>"
            "<font color='#C53030'>docker compose -f 13-yolo11-distance/docker-compose.yml run --rm yolo11-runner \\<br/>"
            "&nbsp;&nbsp;python scripts/test_dual_vacancy.py --source /app/backend/samples/bus_full.jpg --out /app/results/dual_full.jpg</font>",
            box_style
        )]
    ]
    t_cmd = Table(cmd_box, colWidths=[523])
    t_cmd.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F7FAFC")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E0")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_cmd)
    story.append(Spacer(1, 10))

    # =========================================================================
    # 5. ★ GPU 환경 전환 핵심 수정 가이드 (체크리스트)
    # =========================================================================
    story.append(KeepTogether([
        Paragraph("5. ★ GPU(CUDA) 환경 전환 핵심 수정 가이드 (Checklist)", h1_style),
        Paragraph(
            "차후 GPU 가속 서버 및 클라우드 환경으로 이전할 때 수정해야 하는 4대 포인트를 코드 레벨에서 완벽히 기록하였습니다.",
            body_style
        )
    ]))

    gpu_checklist = [
        [Paragraph("항목", th_style), Paragraph("CPU 시연 모드 (현재)", th_style), Paragraph("GPU 환경 전환 시 수정 내용", th_style)],
        [
            Paragraph("<b>[수정 1]<br/>Dockerfile<br/>베이스 및 Torch</b>", td_bold_style),
            Paragraph(
                "<code>FROM python:3.11-slim</code><br/>"
                "<code>RUN pip install --index-url https://.../cpu torch torchvision</code>",
                td_style
            ),
            Paragraph(
                "<b>교체:</b><br/>"
                "<code>FROM pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime</code><br/>"
                "※ 공식 이미지에 CUDA/Torch가 내장되므로 CPU 휠 설치 RUN 라인 주석 처리",
                td_style
            )
        ],
        [
            Paragraph("<b>[수정 2]<br/>docker-compose<br/>deploy 리소스</b>", td_bold_style),
            Paragraph(
                "<code>deploy</code> 설정 주석 처리<br/>"
                "<code>image: yolo11-bus-distance:cpu</code>",
                td_style
            ),
            Paragraph(
                "<b>주석 해제 및 태그 변경:</b><br/>"
                "<code>image: yolo11-bus-distance:gpu</code><br/>"
                "<code>deploy.resources.reservations.devices:</code><br/>"
                "<code>&nbsp;&nbsp;- driver: nvidia, count: all, capabilities: [gpu]</code>",
                td_style
            )
        ],
        [
            Paragraph("<b>[수정 3]<br/>단독 docker run<br/>CLI 플래그</b>", td_bold_style),
            Paragraph("<code>docker run --rm ...</code>", td_style),
            Paragraph("<b><code>--gpus all</code> 플래그 추가:</b><br/><code>docker run --gpus all --rm ...</code>", td_style)
        ],
        [
            Paragraph("<b>[수정 4]<br/>스크립트 실행<br/>디바이스 설정</b>", td_bold_style),
            Paragraph(
                "추론: 자동 감지(CPU 할당)<br/>"
                "학습: <code>python scripts/train_bus.py --device cpu</code>",
                td_style
            ),
            Paragraph(
                "추론: <code>torch.cuda.is_available()</code> 자동 감지(GPU 자동 할당)<br/>"
                "학습: <code>python scripts/train_bus.py --device 0</code> (명시 할당)",
                td_style
            )
        ]
    ]
    t_gpu = Table(gpu_checklist, colWidths=[90, 200, 233])
    t_gpu.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#D69E2E")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E0")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#FFFDF5")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_gpu)
    story.append(Spacer(1, 8))

    # =========================================================================
    # 6. 결론 및 산출물 요약
    # =========================================================================
    story.append(KeepTogether([
        Paragraph("6. 구축 결과 및 산출물 요약", h1_style),
        Paragraph(
            "• <b>산출물 파일</b>:<br/>"
            "&nbsp;&nbsp;1) <code>13-yolo11-distance/Dockerfile</code> (CPU 경량 빌드 + GPU 주석 가이드)<br/>"
            "&nbsp;&nbsp;2) <code>13-yolo11-distance/docker-compose.yml</code> (호스트-컨테이너 간 볼륨 매핑 서비스)<br/>"
            "&nbsp;&nbsp;3) <code>13-yolo11-distance/DOCKER_GUIDE.md</code> (시연 및 GPU 전환 상세 매뉴얼)<br/>"
            "&nbsp;&nbsp;4) <code>13-yolo11-distance/src/dual_pipeline.py</code> (환경 변수 및 디바이스 자동 감지 개선)<br/>"
            "• <b>기대 효과</b>: 로컬 시연 시 수 초 이내의 가벼운 컨테이너 구동이 가능하며, 호스트 OS 환경에 구애받지 않고 일관된 버스 혼잡도 이중 모델 추론 결과를 재현할 수 있습니다.",
            body_style
        )
    ]))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"✅ PDF 보고서 생성 완료: {output_pdf_path}")

if __name__ == "__main__":
    out_pdf_kr = os.path.join(PROJECT_DIR, "docs", "버스_객실_분석_파이프라인_Docker_구축_보고서.pdf")
    out_pdf_en = os.path.join(PROJECT_DIR, "docs", "docker_pipeline_setup_report.pdf")
    build_pdf(out_pdf_kr)
    build_pdf(out_pdf_en)
