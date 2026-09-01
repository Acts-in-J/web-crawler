"""scripts/test_export_gsheets.py — Google Sheets Adapter 테스트

두 층으로 분리:
  Unit  — mock 사용, credential 없어도 항상 실행.
  Live  — 실제 Service Account + Spreadsheet 가 준비됐을 때만 실행.
          pytest -k live  또는 환경변수가 설정된 경우에 자동 실행.

실행:
  # Unit only (항상 가능)
  pytest scripts/test_export_gsheets.py -v -k "not live"

  # Live write (credential 준비 후)
  $env:GOOGLE_APPLICATION_CREDENTIALS="C:/path/to/service_account.json"
  $env:GSHEET_SPREADSHEET_ID="<spreadsheet_id>"
  pytest scripts/test_export_gsheets.py -v -k live
"""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# 공통 fixture / 헬퍼
# ---------------------------------------------------------------------------

DUMMY_DATA = [
    {
        "item_name": "테스트 상품 A",
        "price": 15000,
        "rating": 4.5,
        "review_count": 42,
        "source_url": "https://example.com/item/1",
        "item_key": "item-001",
        "category": "도서",
        "brand": "BrandA",
        "model": "ModelX",
        "region": "서울",
        "status": "판매중",
    },
    {
        "item_name": "테스트 상품 B",
        "price": 23000,
        "rating": 3.8,
        "review_count": 17,
        "source_url": "https://example.com/item/2",
        "item_key": "item-002",
    },
    {
        "item_name": "테스트 상품 C",
        "price": 9900,
        "source_url": "https://example.com/item/3",
        "item_key": "item-003",
    },
]

DUMMY_CRAWL_LOG = {
    "source_domain": "example.com",
    "started_at": "2026-09-01T06:00:00Z",
    "completed_at": "2026-09-01T06:01:00Z",
    "requested_count": 10,
    "collected_count": 3,
    "status": "success",
    "message": "unit test dummy",
}


def _has_live_credentials() -> bool:
    """실제 live write에 필요한 환경변수가 모두 있는지 확인."""
    return bool(
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        and os.environ.get("GSHEET_SPREADSHEET_ID")
    )


# ---------------------------------------------------------------------------
# Unit — import / 예외 / data 변환 (항상 실행)
# ---------------------------------------------------------------------------


class TestImportAndExceptions:
    """export_gsheets.py 를 import하는 것 자체는 google 라이브러리 없이도 된다."""

    def test_module_imports_without_google_libs(self):
        """google 라이브러리 없이도 모듈 import 가 성공해야 한다."""
        import export_gsheets  # noqa: F401

    def test_gsheets_not_configured_is_exception(self):
        from export_gsheets import GsheetsNotConfigured
        assert issubclass(GsheetsNotConfigured, Exception)

    def test_missing_credentials_raises_not_configured(self, monkeypatch):
        """GOOGLE_APPLICATION_CREDENTIALS 미설정 → GsheetsNotConfigured."""
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
        monkeypatch.delenv("GSHEET_SPREADSHEET_ID", raising=False)
        from export_gsheets import GsheetsNotConfigured, export_to_gsheets
        with pytest.raises(GsheetsNotConfigured, match="인증정보 경로"):
            export_to_gsheets(DUMMY_DATA, credentials_path=None, spreadsheet_id="fake")

    def test_missing_spreadsheet_id_raises_not_configured(self, monkeypatch, tmp_path):
        """GSHEET_SPREADSHEET_ID 미설정 → GsheetsNotConfigured."""
        fake_cred = tmp_path / "service_account.json"
        fake_cred.write_text("{}")
        monkeypatch.delenv("GSHEET_SPREADSHEET_ID", raising=False)
        from export_gsheets import GsheetsNotConfigured, export_to_gsheets
        with pytest.raises(GsheetsNotConfigured, match="Spreadsheet ID"):
            export_to_gsheets(
                DUMMY_DATA,
                credentials_path=str(fake_cred),
                spreadsheet_id=None,
            )

    def test_missing_google_lib_raises_not_configured(self, monkeypatch, tmp_path):
        """google 라이브러리가 없으면 GsheetsNotConfigured (ImportError 래핑)."""
        fake_cred = tmp_path / "service_account.json"
        fake_cred.write_text("{}")
        monkeypatch.setenv("GSHEET_SPREADSHEET_ID", "fake-sheet-id")

        import sys
        import importlib

        # google.oauth2 를 가상으로 숨긴다
        with patch.dict(sys.modules, {"google.oauth2": None, "google.oauth2.service_account": None}):
            import export_gsheets
            importlib.reload(export_gsheets)  # 모듈 상태 리셋
            from export_gsheets import GsheetsNotConfigured

            with pytest.raises(GsheetsNotConfigured, match="라이브러리"):
                # _require_google_libs() 를 직접 호출
                export_gsheets._require_google_libs()


class TestDataConversion:
    """item dict → 시트 행 변환 로직."""

    def test_item_to_raw_row_length(self):
        from export_gsheets import RAW_COLUMNS, _item_to_raw_row
        row = _item_to_raw_row(DUMMY_DATA[0], "crawl-001", "example.com")
        assert len(row) == len(RAW_COLUMNS)

    def test_item_to_raw_row_values(self):
        from export_gsheets import _item_to_raw_row
        row = _item_to_raw_row(DUMMY_DATA[0], "crawl-001", "example.com")
        # crawl_id
        assert row[0] == "crawl-001"
        # source_domain
        assert row[1] == "example.com"
        # source_url
        assert row[2] == "https://example.com/item/1"
        # item_name
        assert row[5] == "테스트 상품 A"
        # price
        assert row[9] == 15000
        # raw_json 은 마지막 컬럼 — JSON 파싱 가능해야 함
        raw = json.loads(row[-1])
        assert raw["item_name"] == "테스트 상품 A"

    def test_item_to_raw_row_missing_fields_are_empty(self):
        """필수가 아닌 필드가 없으면 빈 문자열."""
        from export_gsheets import _item_to_raw_row
        minimal = {"item_name": "X", "price": 100}
        row = _item_to_raw_row(minimal, "c1", "dom.com")
        # category (index 6), brand (7), model (8) 빈값
        assert row[6] == ""
        assert row[7] == ""
        assert row[8] == ""

    def test_crawl_log_to_row_length(self):
        from export_gsheets import CRAWL_LOG_COLUMNS, _crawl_log_to_row
        row = _crawl_log_to_row(DUMMY_CRAWL_LOG)
        assert len(row) == len(CRAWL_LOG_COLUMNS)

    def test_crawl_log_to_row_values(self):
        from export_gsheets import _crawl_log_to_row
        log = {**DUMMY_CRAWL_LOG, "crawl_id": "c-999"}
        row = _crawl_log_to_row(log)
        assert row[0] == "c-999"
        assert row[6] == "success"

    def test_column_lists_are_correct_length(self):
        from export_gsheets import CRAWL_LOG_COLUMNS, RAW_COLUMNS
        assert len(RAW_COLUMNS) == 15
        assert len(CRAWL_LOG_COLUMNS) == 8


class TestGsheetsAdapterUnit:
    """GsheetsAdapter 를 mock service 로 단위 테스트."""

    def _make_adapter(self, existing_sheets: list[str] | None = None):
        """mock service 를 주입한 GsheetsAdapter 반환."""
        from export_gsheets import GsheetsAdapter

        existing = existing_sheets or []
        mock_service = MagicMock()
        sheets_api = mock_service.spreadsheets.return_value

        # list_sheet_titles() 가 사용하는 .get().execute()
        sheets_api.get.return_value.execute.return_value = {
            "sheets": [{"properties": {"title": t}} for t in existing]
        }

        # append_rows() 가 사용하는 .values().append().execute()
        sheets_api.values.return_value.append.return_value.execute.return_value = {
            "updates": {"updatedRows": 99}
        }

        # get_row_count() 가 사용하는 .values().get().execute()
        sheets_api.values.return_value.get.return_value.execute.return_value = {
            "values": [["h1"], ["r1"], ["r2"]]  # header + 2 rows
        }

        return GsheetsAdapter("fake-sheet-id", mock_service)

    def test_list_sheet_titles_empty(self):
        adapter = self._make_adapter([])
        assert adapter.list_sheet_titles() == []

    def test_list_sheet_titles_with_sheets(self):
        adapter = self._make_adapter(["01_RAW", "03_CRAWL_LOG"])
        titles = adapter.list_sheet_titles()
        assert "01_RAW" in titles
        assert "03_CRAWL_LOG" in titles

    def test_ensure_sheet_creates_when_missing(self):
        from export_gsheets import RAW_COLUMNS
        adapter = self._make_adapter([])  # 시트 없음
        adapter.ensure_sheet("01_RAW", RAW_COLUMNS)
        # batchUpdate 가 호출돼야 함
        adapter._sheets.batchUpdate.assert_called_once()

    def test_ensure_sheet_skips_when_exists(self):
        from export_gsheets import RAW_COLUMNS
        adapter = self._make_adapter(["01_RAW"])  # 이미 있음
        adapter.ensure_sheet("01_RAW", RAW_COLUMNS)
        # batchUpdate 호출 없어야 함
        adapter._sheets.batchUpdate.assert_not_called()

    def test_append_rows_returns_count(self):
        adapter = self._make_adapter(["01_RAW"])
        count = adapter.append_rows("01_RAW", [["a", "b"], ["c", "d"]])
        assert count == 99  # mock 에서 updatedRows=99

    def test_append_rows_empty_returns_zero(self):
        adapter = self._make_adapter(["01_RAW"])
        count = adapter.append_rows("01_RAW", [])
        assert count == 0
        # API 호출 없어야 함
        adapter._sheets.values.return_value.append.assert_not_called()

    def test_get_row_count(self):
        adapter = self._make_adapter(["01_RAW"])
        count = adapter.get_row_count("01_RAW")
        assert count == 3  # mock values: header + 2 rows


class TestExportToGsheetsUnit:
    """export_to_gsheets() 최상위 진입점 — GsheetsAdapter.from_credentials 를 mock."""

    def _patched_export(self, monkeypatch, tmp_path, existing_sheets=None):
        """인증 + from_credentials 를 mock 처리한 export_to_gsheets 호출 헬퍼."""
        fake_cred = tmp_path / "service_account.json"
        fake_cred.write_text(json.dumps({"type": "service_account"}))
        monkeypatch.setenv("GSHEET_SPREADSHEET_ID", "fake-id")

        from export_gsheets import GsheetsAdapter
        adapter_instance = MagicMock(spec=GsheetsAdapter)
        adapter_instance.list_sheet_titles.return_value = existing_sheets or []
        adapter_instance.append_rows.return_value = len(DUMMY_DATA)

        return fake_cred, adapter_instance

    def test_export_returns_raw_row_count(self, monkeypatch, tmp_path):
        fake_cred, adapter_mock = self._patched_export(monkeypatch, tmp_path, ["01_RAW"])

        import export_gsheets
        with patch.object(export_gsheets.GsheetsAdapter, "from_credentials", return_value=adapter_mock):
            result = export_gsheets.export_to_gsheets(
                DUMMY_DATA,
                credentials_path=str(fake_cred),
                spreadsheet_id="fake-id",
                source_domain="example.com",
            )

        assert result["raw_rows"] == len(DUMMY_DATA)
        assert result["log_rows"] == 0  # crawl_log 없음

    def test_export_with_crawl_log(self, monkeypatch, tmp_path):
        fake_cred, adapter_mock = self._patched_export(monkeypatch, tmp_path, ["01_RAW", "03_CRAWL_LOG"])
        adapter_mock.append_rows.side_effect = [3, 1]  # raw, log

        import export_gsheets
        with patch.object(export_gsheets.GsheetsAdapter, "from_credentials", return_value=adapter_mock):
            result = export_gsheets.export_to_gsheets(
                DUMMY_DATA,
                crawl_log=DUMMY_CRAWL_LOG,
                credentials_path=str(fake_cred),
                spreadsheet_id="fake-id",
                source_domain="example.com",
            )

        assert result["raw_rows"] == 3
        assert result["log_rows"] == 1

    def test_export_empty_data_skips_raw_sheet(self, monkeypatch, tmp_path):
        fake_cred, adapter_mock = self._patched_export(monkeypatch, tmp_path)

        import export_gsheets
        with patch.object(export_gsheets.GsheetsAdapter, "from_credentials", return_value=adapter_mock):
            result = export_gsheets.export_to_gsheets(
                [],
                credentials_path=str(fake_cred),
                spreadsheet_id="fake-id",
            )

        assert result["raw_rows"] == 0
        # 01_RAW 시트 append 호출 없어야 함
        adapter_mock.append_rows.assert_not_called()

    def test_crawl_id_auto_generated(self, monkeypatch, tmp_path):
        """crawl_id 를 안 넘기면 타임스탬프 기반 ID가 자동 생성된다."""
        fake_cred, adapter_mock = self._patched_export(monkeypatch, tmp_path, ["01_RAW"])

        import export_gsheets
        with patch.object(export_gsheets.GsheetsAdapter, "from_credentials", return_value=adapter_mock):
            export_gsheets.export_to_gsheets(
                DUMMY_DATA[:1],
                credentials_path=str(fake_cred),
                spreadsheet_id="fake-id",
                source_domain="example.com",
            )

        # append_rows 의 첫 번째 인자가 행 리스트 — 행[0][0] 이 crawl_id
        args = adapter_mock.append_rows.call_args
        rows_arg = args[0][1]  # positional: sheet_title, rows
        assert len(rows_arg[0][0]) > 0  # crawl_id 가 빈 문자열이 아님


# ---------------------------------------------------------------------------
# Live Write — GOOGLE_APPLICATION_CREDENTIALS + GSHEET_SPREADSHEET_ID 필요
# ---------------------------------------------------------------------------

_live_skip = pytest.mark.skipif(
    not _has_live_credentials(),
    reason=(
        "Live write 테스트: 환경변수를 설정하세요.\n"
        "  $env:GOOGLE_APPLICATION_CREDENTIALS='<service_account.json 절대경로>'\n"
        "  $env:GSHEET_SPREADSHEET_ID='<spreadsheet_id>'"
    ),
)


@_live_skip
class TestLiveWrite:
    """실제 Google Sheets에 dummy 3건을 쓰고 확인 후 정리."""

    def test_live_write_raw_and_log(self):
        """01_RAW 에 3건, 03_CRAWL_LOG 에 1건 쓰고 행 수 증가를 확인한다."""
        from export_gsheets import (
            SHEET_CRAWL_LOG,
            SHEET_RAW,
            GsheetsAdapter,
        )

        creds_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
        sid = os.environ["GSHEET_SPREADSHEET_ID"]

        adapter = GsheetsAdapter.from_credentials(sid, creds_path)

        # 현재 행 수 기록
        adapter.ensure_sheet(SHEET_RAW, __import__("export_gsheets").RAW_COLUMNS)
        adapter.ensure_sheet(SHEET_CRAWL_LOG, __import__("export_gsheets").CRAWL_LOG_COLUMNS)
        before_raw = adapter.get_row_count(SHEET_RAW)
        before_log = adapter.get_row_count(SHEET_CRAWL_LOG)

        # 실제 write
        import export_gsheets
        crawl_log = {
            **DUMMY_CRAWL_LOG,
            "message": "[LIVE TEST] pytest automated write — safe to delete",
        }
        result = export_gsheets.export_to_gsheets(
            DUMMY_DATA,
            crawl_log=crawl_log,
            source_domain="example.com",
            crawl_id="pytest-live-001",
        )

        # 행 수 검증
        after_raw = adapter.get_row_count(SHEET_RAW)
        after_log = adapter.get_row_count(SHEET_CRAWL_LOG)

        assert after_raw == before_raw + len(DUMMY_DATA), (
            f"01_RAW: 예상 +{len(DUMMY_DATA)}행, 실제 +{after_raw - before_raw}행"
        )
        assert after_log == before_log + 1, (
            f"03_CRAWL_LOG: 예상 +1행, 실제 +{after_log - before_log}행"
        )
        assert result["raw_rows"] > 0
        assert result["log_rows"] > 0

    def test_live_write_only_data_no_log(self):
        """crawl_log=None 이면 03_CRAWL_LOG 는 건드리지 않는다."""
        from export_gsheets import SHEET_CRAWL_LOG, GsheetsAdapter
        import export_gsheets

        creds_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
        sid = os.environ["GSHEET_SPREADSHEET_ID"]

        adapter = GsheetsAdapter.from_credentials(sid, creds_path)
        adapter.ensure_sheet(SHEET_CRAWL_LOG, export_gsheets.CRAWL_LOG_COLUMNS)
        before_log = adapter.get_row_count(SHEET_CRAWL_LOG)

        result = export_gsheets.export_to_gsheets(
            DUMMY_DATA[:1],
            crawl_log=None,
            source_domain="example.com",
            crawl_id="pytest-live-002",
        )

        after_log = adapter.get_row_count(SHEET_CRAWL_LOG)
        assert after_log == before_log, "crawl_log=None 인데 CRAWL_LOG 행이 증가했다"
        assert result["log_rows"] == 0
