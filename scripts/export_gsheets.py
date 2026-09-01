"""scripts/export_gsheets.py — Google Sheets Optional Output Adapter

기존 Excel 출력(export_excel.py)과 독립적으로 동작하는 선택적 추가 출력 경로.
Google 라이브러리가 설치되지 않았거나 인증정보가 없으면 조용히 GsheetsNotConfigured
를 발생시키고 Excel 경로에는 영향을 주지 않는다.

설치 (선택):
    pip install -r requirements-gsheets.txt

환경변수:
    GOOGLE_APPLICATION_CREDENTIALS  Service Account JSON의 절대경로 (필수)
    GSHEET_SPREADSHEET_ID           대상 Spreadsheet ID (필수)

Workbook 구조 (이번 Slice):
    01_RAW        수집 데이터 (item 단위)
    03_CRAWL_LOG  수집 실행 로그 (crawl 단위)

향후 확장 예정 (이번 Slice 제외):
    02_MASTER     정제 데이터
    04_METRICS_DAILY 일별 집계
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 공개 시트 이름 — 향후 02_MASTER / 04_METRICS_DAILY 추가 시 여기만 확장
# ---------------------------------------------------------------------------
SHEET_RAW = "01_RAW"
SHEET_CRAWL_LOG = "03_CRAWL_LOG"

# 01_RAW 컬럼 순서 (헤더 행과 동일해야 한다)
RAW_COLUMNS: list[str] = [
    "crawl_id",
    "source_domain",
    "source_url",
    "collected_at",
    "item_key",
    "item_name",
    "category",
    "brand",
    "model",
    "price",
    "rating",
    "review_count",
    "region",
    "status",
    "raw_json",
]

# 03_CRAWL_LOG 컬럼 순서
CRAWL_LOG_COLUMNS: list[str] = [
    "crawl_id",
    "source_domain",
    "started_at",
    "completed_at",
    "requested_count",
    "collected_count",
    "status",
    "message",
]

# Google Sheets API 스코프
_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


# ---------------------------------------------------------------------------
# 예외
# ---------------------------------------------------------------------------


class GsheetsNotConfigured(Exception):
    """Google Sheets 연동에 필요한 라이브러리 또는 인증정보가 없을 때.

    Excel 출력 경로는 이 예외와 무관하게 항상 동작한다.
    이 예외를 잡아 skip 처리하거나 사용자에게 안내만 하면 된다.
    """


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------


def _require_google_libs() -> tuple[Any, Any]:
    """google-auth / google-api-python-client import.

    미설치 환경에서 ImportError 를 GsheetsNotConfigured 로 변환한다.

    Returns:
        (google.oauth2.service_account, googleapiclient.discovery) 튜플
    """
    try:
        from google.oauth2 import service_account  # type: ignore[import-untyped]
        from googleapiclient import discovery  # type: ignore[import-untyped]
    except ImportError as exc:
        raise GsheetsNotConfigured(
            "Google Sheets 라이브러리가 설치되지 않았습니다. "
            "설치 명령: pip install -r requirements-gsheets.txt\n"
            f"원인: {exc}"
        ) from exc
    return service_account, discovery


def _resolve_credentials(credentials_path: str | None) -> str:
    """Service Account JSON 경로를 확정한다.

    우선순위:
      1. 인자 credentials_path (명시적 전달)
      2. 환경변수 GOOGLE_APPLICATION_CREDENTIALS

    두 경로 모두 없으면 GsheetsNotConfigured.
    """
    path = credentials_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not path:
        raise GsheetsNotConfigured(
            "Service Account 인증정보 경로가 설정되지 않았습니다.\n"
            "다음 중 하나를 설정하세요:\n"
            "  환경변수: GOOGLE_APPLICATION_CREDENTIALS=<service_account.json 절대경로>\n"
            "  함수 인자: export_to_gsheets(..., credentials_path='<절대경로>')"
        )
    if not os.path.isfile(path):
        raise GsheetsNotConfigured(
            f"Service Account 파일을 찾을 수 없습니다: {path}\n"
            "경로가 올바른지, 파일이 존재하는지 확인하세요."
        )
    return path


def _resolve_spreadsheet_id(spreadsheet_id: str | None) -> str:
    """Spreadsheet ID를 확정한다.

    우선순위:
      1. 인자 spreadsheet_id (명시적 전달)
      2. 환경변수 GSHEET_SPREADSHEET_ID
    """
    sid = spreadsheet_id or os.environ.get("GSHEET_SPREADSHEET_ID", "")
    if not sid:
        raise GsheetsNotConfigured(
            "Spreadsheet ID가 설정되지 않았습니다.\n"
            "다음 중 하나를 설정하세요:\n"
            "  환경변수: GSHEET_SPREADSHEET_ID=<spreadsheet_id>\n"
            "  함수 인자: export_to_gsheets(..., spreadsheet_id='<id>')"
        )
    return sid


def _item_to_raw_row(item: dict, crawl_id: str, source_domain: str) -> list[Any]:
    """item dict를 01_RAW 행(RAW_COLUMNS 순)으로 변환한다."""
    now = datetime.now(timezone.utc).isoformat()
    # raw_json: 원본 dict 전체를 직렬화해 보존
    raw = json.dumps(item, ensure_ascii=False, default=str)
    return [
        crawl_id,
        source_domain,
        item.get("source_url", item.get("url", item.get("product_url", ""))),
        item.get("collected_at", now),
        item.get("item_key", item.get("id", "")),
        item.get("item_name", item.get("name", item.get("title", ""))),
        item.get("category", ""),
        item.get("brand", ""),
        item.get("model", ""),
        item.get("price", ""),
        item.get("rating", ""),
        item.get("review_count", ""),
        item.get("region", ""),
        item.get("status", item.get("availability", "")),
        raw,
    ]


def _crawl_log_to_row(crawl_log: dict) -> list[Any]:
    """crawl_log dict를 03_CRAWL_LOG 행(CRAWL_LOG_COLUMNS 순)으로 변환한다."""
    return [
        crawl_log.get("crawl_id", ""),
        crawl_log.get("source_domain", ""),
        crawl_log.get("started_at", ""),
        crawl_log.get("completed_at", ""),
        crawl_log.get("requested_count", ""),
        crawl_log.get("collected_count", ""),
        crawl_log.get("status", ""),
        crawl_log.get("message", ""),
    ]


# ---------------------------------------------------------------------------
# GsheetsAdapter — 얇은 API 래퍼 (향후 시트 추가 시 이 클래스만 확장)
# ---------------------------------------------------------------------------


class GsheetsAdapter:
    """Google Sheets REST API 래퍼.

    직접 사용도 가능하지만, 일반적으로는 `export_to_gsheets()` 를 쓴다.

    향후 02_MASTER / 04_METRICS_DAILY 추가 시 아래 패턴으로 확장:
        adapter.ensure_sheet("02_MASTER", MASTER_COLUMNS)
        adapter.append_rows("02_MASTER", rows)
    """

    def __init__(self, spreadsheet_id: str, service: Any):
        """
        Args:
            spreadsheet_id: Google Spreadsheet ID.
            service: googleapiclient.discovery.build() 로 만든 Sheets 서비스 객체.
        """
        self.spreadsheet_id = spreadsheet_id
        self._service = service
        self._sheets = service.spreadsheets()

    @classmethod
    def from_credentials(
        cls,
        spreadsheet_id: str,
        credentials_path: str,
    ) -> "GsheetsAdapter":
        """Service Account JSON에서 어댑터를 생성한다.

        Args:
            spreadsheet_id: 대상 Spreadsheet ID.
            credentials_path: Service Account JSON 절대경로.

        Raises:
            GsheetsNotConfigured: google 라이브러리 미설치 시.
        """
        service_account_mod, discovery_mod = _require_google_libs()
        creds = service_account_mod.Credentials.from_service_account_file(
            credentials_path, scopes=_SCOPES
        )
        service = discovery_mod.build("sheets", "v4", credentials=creds)
        return cls(spreadsheet_id=spreadsheet_id, service=service)

    # ------------------------------------------------------------------
    # 시트 관리
    # ------------------------------------------------------------------

    def list_sheet_titles(self) -> list[str]:
        """Spreadsheet에 존재하는 시트 이름 목록을 반환한다."""
        meta = self._sheets.get(spreadsheetId=self.spreadsheet_id).execute()
        return [s["properties"]["title"] for s in meta.get("sheets", [])]

    def ensure_sheet(self, title: str, headers: list[str]) -> None:
        """시트가 없으면 생성하고 헤더 행을 추가한다.

        이미 시트가 있으면 아무것도 하지 않는다 (헤더 중복 방지).

        Args:
            title: 시트 이름 (예: "01_RAW").
            headers: 헤더 컬럼 목록.
        """
        existing = self.list_sheet_titles()
        if title in existing:
            return

        # 시트 추가
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        self._sheets.batchUpdate(
            spreadsheetId=self.spreadsheet_id, body=body
        ).execute()
        logger.info("시트 생성: %s", title)

        # 헤더 행 기록
        self.append_rows(title, [headers])

    def append_rows(self, sheet_title: str, rows: list[list[Any]]) -> int:
        """시트 끝에 행을 추가한다.

        Args:
            sheet_title: 대상 시트 이름.
            rows: 추가할 행 목록 (각 행은 값 리스트).

        Returns:
            실제로 추가된 행 수.
        """
        if not rows:
            return 0
        range_notation = f"{sheet_title}!A1"
        body = {"values": rows}
        result = (
            self._sheets.values()
            .append(
                spreadsheetId=self.spreadsheet_id,
                range=range_notation,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body,
            )
            .execute()
        )
        updates = result.get("updates", {})
        count = updates.get("updatedRows", len(rows))
        logger.info("'%s' 시트에 %d행 추가", sheet_title, count)
        return count

    def get_row_count(self, sheet_title: str) -> int:
        """시트의 현재 데이터 행 수를 반환한다 (헤더 포함)."""
        result = (
            self._sheets.values()
            .get(spreadsheetId=self.spreadsheet_id, range=f"{sheet_title}!A:A")
            .execute()
        )
        values = result.get("values", [])
        return len(values)


# ---------------------------------------------------------------------------
# 공개 진입점
# ---------------------------------------------------------------------------


def export_to_gsheets(
    data: list[dict],
    crawl_log: dict | None = None,
    *,
    spreadsheet_id: str | None = None,
    credentials_path: str | None = None,
    crawl_id: str | None = None,
    source_domain: str = "",
) -> dict[str, int]:
    """크롤링 결과를 Google Sheets에 저장한다.

    기존 Excel 출력과 **독립적으로** 호출한다. 이 함수가 실패해도
    Excel 저장 흐름에는 영향을 주지 않는다.

    Args:
        data: 수집 결과 딕셔너리 리스트. 각 항목이 01_RAW 시트에 1행이 된다.
        crawl_log: 수집 실행 메타데이터. None이면 03_CRAWL_LOG는 건너뛴다.
            권장 키: crawl_id, source_domain, started_at, completed_at,
                      requested_count, collected_count, status, message
        spreadsheet_id: 대상 Spreadsheet ID.
            None이면 환경변수 GSHEET_SPREADSHEET_ID 를 읽는다.
        credentials_path: Service Account JSON 절대경로.
            None이면 환경변수 GOOGLE_APPLICATION_CREDENTIALS 를 읽는다.
        crawl_id: 수집 실행 식별자. None이면 UTC timestamp로 자동 생성한다.
        source_domain: 수집 대상 도메인 (예: "books.toscrape.com").

    Returns:
        {"raw_rows": N, "log_rows": M} — 실제로 추가된 행 수.

    Raises:
        GsheetsNotConfigured: 라이브러리 미설치 또는 인증정보 누락.
            이 예외를 잡아 skip 처리하고 Excel 출력은 그대로 진행할 것.
    """
    # 인증정보 확정 (없으면 GsheetsNotConfigured)
    creds = _resolve_credentials(credentials_path)
    sid = _resolve_spreadsheet_id(spreadsheet_id)

    # crawl_id 기본값
    if crawl_id is None:
        crawl_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    adapter = GsheetsAdapter.from_credentials(sid, creds)

    result: dict[str, int] = {"raw_rows": 0, "log_rows": 0}

    # 01_RAW
    if data:
        adapter.ensure_sheet(SHEET_RAW, RAW_COLUMNS)
        raw_rows = [_item_to_raw_row(item, crawl_id, source_domain) for item in data]
        result["raw_rows"] = adapter.append_rows(SHEET_RAW, raw_rows)

    # 03_CRAWL_LOG
    if crawl_log is not None:
        if "crawl_id" not in crawl_log:
            crawl_log = {**crawl_log, "crawl_id": crawl_id}
        if "source_domain" not in crawl_log:
            crawl_log = {**crawl_log, "source_domain": source_domain}
        adapter.ensure_sheet(SHEET_CRAWL_LOG, CRAWL_LOG_COLUMNS)
        log_row = _crawl_log_to_row(crawl_log)
        result["log_rows"] = adapter.append_rows(SHEET_CRAWL_LOG, [log_row])

    return result
