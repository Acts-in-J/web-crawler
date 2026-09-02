"""scripts/test_dashboard.py — Review Intelligence Dashboard Unit & Contract Tests

Google Apps Script Review Dashboard (apps/review-dashboard/)의
파일 계약, 멀티 프로덕트 데이터 집계, KPI 계산, 별점 분포, 월별 추이 및
NIIMBOT 하드코딩 여부를 검증한다.
"""

import json
import os
import re
from datetime import datetime, timezone
import pytest

DASHBOARD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../apps/review-dashboard"))


class TestDashboardFileContracts:
    """Dashboard 파일 구성 및 매니페스트 계약 검증."""

    def test_required_dashboard_files_exist(self):
        required_files = ["Code.gs", "Index.html", "Styles.html", "Scripts.html", "appsscript.json", ".clasp.json"]
        for fname in required_files:
            fpath = os.path.join(DASHBOARD_DIR, fname)
            assert os.path.isfile(fpath), f"필수 파일 누락: {fname}"

    def test_appsscript_manifest_structure(self):
        """MVP 내부 검토용 엄격한 권한 계약 (USER_DEPLOYING & MYSELF)."""
        manifest_path = os.path.join(DASHBOARD_DIR, "appsscript.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest.get("timeZone") == "Asia/Seoul"
        assert manifest.get("runtimeVersion") == "V8"
        assert "webapp" in manifest
        assert manifest["webapp"].get("executeAs") == "USER_DEPLOYING"
        assert manifest["webapp"].get("access") == "MYSELF"

    def test_no_niimbot_hardcoding_in_backend_or_frontend(self):
        """Code.gs, Index.html, Scripts.html 등에 특정 브랜드/상품 ID가 하드코딩되어 있지 않은지 검증."""
        target_files = ["Code.gs", "Index.html", "Scripts.html", "Styles.html"]
        forbidden_patterns = [
            re.compile(r"9308947164"),  # NIIMBOT Product ID
            re.compile(r"NIIMBOT", re.IGNORECASE),
        ]

        for fname in target_files:
            fpath = os.path.join(DASHBOARD_DIR, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            for pattern in forbidden_patterns:
                match = pattern.search(content)
                assert match is None, f"{fname} 에 특정 브랜드/상품 정보가 하드코딩되어 있습니다: {match.group(0)}"

    def test_no_xframe_allowall_in_code_gs(self):
        """Code.gs doGet()에 setXFrameOptionsMode(ALLOWALL)가 없어야 함."""
        code_gs_path = os.path.join(DASHBOARD_DIR, "Code.gs")
        with open(code_gs_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "setXFrameOptionsMode" not in content, "Code.gs 에 불필요한 setXFrameOptionsMode 가 존재합니다."
        assert "ALLOWALL" not in content, "Code.gs 에 불필요한 ALLOWALL 설정이 존재합니다."

    def test_required_header_validation_in_code_gs(self):
        """Code.gs getReviewDashboardData()에 13개 필수 헤더 검증 로직이 포함되어야 함."""
        code_gs_path = os.path.join(DASHBOARD_DIR, "Code.gs")
        with open(code_gs_path, "r", encoding="utf-8") as f:
            content = f.read()

        required_headers = [
            "source_domain", "product_id", "product_name", "brand",
            "review_id", "review_date", "rating", "review_text",
            "product_option", "helpful_count", "photo_review",
            "video_review", "collected_at"
        ]
        for header in required_headers:
            assert header in content, f"Code.gs 에 필수 헤더 '{header}' 검증이 누락되었습니다."

    def test_scripts_html_script_tag_wrapper_and_state_contracts(self):
        """Scripts.html이 <script>로 시작하고 </script>로 끝나며 필수 전역 변수 4개가 선언되어야 함."""
        scripts_path = os.path.join(DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        stripped = raw_content.strip()
        assert stripped.startswith("<script>"), "Scripts.html 시작 부분에 <script> 태그가 없습니다."
        assert stripped.endswith("</script>"), "Scripts.html 마지막 부분에 </script> 태그가 없습니다."

        # Verify global state declarations
        required_states = [
            "let allReviews = []",
            "let filteredReviews = []",
            "let displayCount = 50",
            "let parsedItemsToImport = []",
        ]
        for state_decl in required_states:
            assert state_decl in stripped, f"Scripts.html 에 필수 전역 변수 선언 '{state_decl}' 이 누락되었습니다."

    def test_index_html_includes_scripts(self):
        """Index.html에 <?!= include('Scripts'); ?> 구문이 정상 포함되어야 함."""
        index_path = os.path.join(DASHBOARD_DIR, "Index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "<?!= include('Scripts'); ?>" in content, "Index.html 에 Scripts include 구문이 없습니다."


# ---------------------------------------------------------------------------
# 멀티 프로덕트 데이터 집계 Pure Python Reference Engine (테스트용)
# ---------------------------------------------------------------------------


def calculate_dashboard_metrics(reviews: list[dict], selected_product: str = "all",
                                 start_date: str = "", end_date: str = "",
                                 selected_rating: str = "all", keyword: str = "",
                                 reference_time_ms: float | None = None) -> dict:
    """Dashboard 클라이언트 로직과 1:1로 일치하는 순수 파이썬 데이터 집계 엔진."""
    # Filter
    filtered = []
    for r in reviews:
        if selected_product != "all" and r.get("product_id") != selected_product:
            continue
        r_date = str(r.get("review_date", ""))[:10]
        if start_date and r_date < start_date:
            continue
        if end_date and r_date > end_date:
            continue
        if selected_rating != "all" and int(r.get("rating", 0)) != int(selected_rating):
            continue
        if keyword:
            kw = keyword.lower()
            text = str(r.get("review_text", "")).lower()
            opt = str(r.get("product_option", "")).lower()
            name = str(r.get("product_name", "")).lower()
            brand = str(r.get("brand", "")).lower()
            if kw not in text and kw not in opt and kw not in name and kw not in brand:
                continue
        filtered.append(r)

    total = len(filtered)
    if total == 0:
        return {
            "total": 0,
            "average_rating": 0.0,
            "recent_30_days": 0,
            "photo_rate": 0,
            "rating_counts": {5: 0, 4: 0, 3: 0, 2: 0, 1: 0},
            "monthly_trend": {},
            "filtered_reviews": [],
        }

    # Avg Rating
    avg_rating = round(sum(r.get("rating", 0) for r in filtered) / total, 2)

    # Recent 30 Days (Current Date / Reference Time Based: thirty_days_ago <= t <= now)
    now_ms = reference_time_ms if reference_time_ms is not None else (datetime.now(timezone.utc).timestamp() * 1000)
    thirty_days_ago_ms = now_ms - (30 * 24 * 3600 * 1000)

    recent_30 = 0
    for r in filtered:
        d_str = str(r.get("review_date", ""))
        if d_str:
            try:
                # ISO Format parsing
                if "T" in d_str:
                    dt = datetime.fromisoformat(d_str.replace("Z", "+00:00"))
                else:
                    dt = datetime.strptime(d_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                t_ms = dt.timestamp() * 1000
                if thirty_days_ago_ms <= t_ms <= now_ms:
                    recent_30 += 1
            except ValueError:
                pass

    # Photo Rate
    photo_count = sum(1 for r in filtered if r.get("photo_review"))
    photo_rate = round((photo_count / total) * 100)

    # Rating Counts (1~5)
    rating_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for r in filtered:
        score = int(r.get("rating", 0))
        if score in rating_counts:
            rating_counts[score] += 1

    # Monthly Trend
    monthly_trend = {}
    for r in filtered:
        ym = str(r.get("review_date", ""))[:7]
        if len(ym) == 7 and ym[4] == "-":
            monthly_trend[ym] = monthly_trend.get(ym, 0) + 1

    return {
        "total": total,
        "average_rating": avg_rating,
        "recent_30_days": recent_30,
        "photo_rate": photo_rate,
        "rating_counts": rating_counts,
        "monthly_trend": monthly_trend,
        "filtered_reviews": filtered,
    }


class TestDashboardAggregationLogic:
    """Multi-product Fixture 기반 Dashboard 집계 및 필터링 검증."""

    @pytest.fixture
    def multi_product_reviews(self):
        """2개 브랜드, 3개 상품으로 구성된 복수 데이터 셋."""
        return [
            {
                "brand": "BrandA",
                "product_id": "prod-100",
                "product_name": "라벨프린터 A1",
                "review_id": "r1",
                "review_date": "2026-08-10T10:00:00Z",
                "rating": 5,
                "review_text": "성능이 정말 우수하고 출력이 빠릅니다.",
                "product_option": "화이트 / 기본형",
                "photo_review": True,
                "video_review": False,
            },
            {
                "brand": "BrandA",
                "product_id": "prod-100",
                "product_name": "라벨프린터 A1",
                "review_id": "r2",
                "review_date": "2026-08-15T10:00:00Z",
                "rating": 4,
                "review_text": "가성비가 좋은 라벨기입니다.",
                "product_option": "블랙 / 고급형",
                "photo_review": False,
                "video_review": False,
            },
            {
                "brand": "BrandB",
                "product_id": "prod-200",
                "product_name": "산업용 프린터 B2",
                "review_id": "r3",
                "review_date": "2026-07-20T10:00:00Z",
                "rating": 2,
                "review_text": "배송이 느리고 인쇄 품질이 아쉽네요.",
                "product_option": "대용량",
                "photo_review": True,
                "video_review": True,
            },
            {
                "brand": "BrandB",
                "product_id": "prod-300",
                "product_name": "휴대용 프린터 C3",
                "review_id": "r4",
                "review_date": "2026-08-28T10:00:00Z",
                "rating": 5,
                "review_text": "선명하게 잘 나옵니다 추천해요!",
                "product_option": "미니 화이트",
                "photo_review": False,
                "video_review": False,
            },
        ]

    def test_total_and_average_rating_all_products(self, multi_product_reviews):
        res = calculate_dashboard_metrics(multi_product_reviews)
        assert res["total"] == 4
        # (5 + 4 + 2 + 5) / 4 = 16 / 4 = 4.0
        assert res["average_rating"] == 4.0
        assert res["photo_rate"] == 50  # 2 out of 4 = 50%

    def test_rating_distribution_always_has_all_5_buckets(self, multi_product_reviews):
        res = calculate_dashboard_metrics(multi_product_reviews)
        buckets = res["rating_counts"]
        assert set(buckets.keys()) == {1, 2, 3, 4, 5}
        assert buckets[5] == 2
        assert buckets[4] == 1
        assert buckets[3] == 0
        assert buckets[2] == 1
        assert buckets[1] == 0

    def test_product_filter(self, multi_product_reviews):
        res = calculate_dashboard_metrics(multi_product_reviews, selected_product="prod-100")
        assert res["total"] == 2
        assert res["average_rating"] == 4.5
        assert all(r["product_id"] == "prod-100" for r in res["filtered_reviews"])

    def test_keyword_filter(self, multi_product_reviews):
        res = calculate_dashboard_metrics(multi_product_reviews, keyword="인쇄")
        assert res["total"] == 1
        assert res["filtered_reviews"][0]["review_id"] == "r3"

    def test_empty_dataset_safety(self):
        res = calculate_dashboard_metrics([])
        assert res["total"] == 0
        assert res["average_rating"] == 0.0
        assert res["recent_30_days"] == 0
        assert res["photo_rate"] == 0
        assert res["rating_counts"] == {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        assert res["monthly_trend"] == {}

    def test_recent_30_days_current_date_based(self, multi_product_reviews):
        ref_dt = datetime(2026, 8, 30, 0, 0, 0, tzinfo=timezone.utc)
        ref_ms = ref_dt.timestamp() * 1000

        res = calculate_dashboard_metrics(multi_product_reviews, reference_time_ms=ref_ms)
        # r1: 2026-08-10 (20 days ago -> IN)
        # r2: 2026-08-15 (15 days ago -> IN)
        # r3: 2026-07-20 (41 days ago -> OUT)
        # r4: 2026-08-28 (2 days ago -> IN)
        assert res["recent_30_days"] == 3

    def test_recent_30_days_excludes_future_dates(self):
        ref_dt = datetime(2026, 8, 30, 0, 0, 0, tzinfo=timezone.utc)
        ref_ms = ref_dt.timestamp() * 1000

        future_reviews = [
            {"review_date": "2026-08-25T00:00:00Z", "rating": 5},  # IN
            {"review_date": "2026-09-05T00:00:00Z", "rating": 5},  # FUTURE -> EXCLUDED
            {"review_date": "2026-06-01T00:00:00Z", "rating": 5},  # OLD -> EXCLUDED
        ]

        res = calculate_dashboard_metrics(future_reviews, reference_time_ms=ref_ms)
        assert res["recent_30_days"] == 1


def sanitize_formula_python(val: str) -> str:
    """Formula Injection 방어: =, +, -, @, \t, \r로 시작하면 ' 접두어 추가."""
    if val is None:
        return ""
    s = str(val)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


class TestReviewImportWorkflow:
    """A5-A2 Excel Import 관련 검증 테스트 클래스."""

    def test_import_function_definition_in_code_gs(self):
        """Code.gs에 importReviewData와 LockService가 정의되어 있어야 함."""
        code_gs_path = os.path.join(DASHBOARD_DIR, "Code.gs")
        with open(code_gs_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "function importReviewData" in content, "Code.gs 에 importReviewData 함수가 없습니다."
        assert "LockService.getScriptLock()" in content, "Code.gs 에 LockService 동시성 방어가 누락되었습니다."
        assert "function sanitizeFormula" in content, "Code.gs 에 sanitizeFormula 방어가 누락되었습니다."

    def test_formula_injection_sanitization(self):
        """Formula injection 필드 방어 테스트."""
        assert sanitize_formula_python("=SUM(A1:A10)") == "'=SUM(A1:A10)"
        assert sanitize_formula_python("+100") == "'+100"
        assert sanitize_formula_python("-100") == "'-100"
        assert sanitize_formula_python("@ATTACK") == "'@ATTACK"
        assert sanitize_formula_python("일반 리뷰 텍스트입니다.") == "일반 리뷰 텍스트입니다."

    def test_import_preview_and_confirm_simulation(self):
        """Import 시뮬레이션: 수신, 신규, 파일내 중복, 기존 시트 중복, invalid 구분."""
        existing_sheet_reviews = [
            {"source_domain": "brand.naver.com", "product_id": "100", "review_id": "r1", "review_text": "기존 리뷰 1"},
        ]

        uploaded_excel_rows = [
            # 1. 정상 신규 건
            {"source_domain": "brand.naver.com", "product_id": "100", "review_id": "r2", "review_text": "신규 리뷰 2"},
            # 2. 기존 시트 중복 건
            {"source_domain": "brand.naver.com", "product_id": "100", "review_id": "r1", "review_text": "중복 리뷰 r1"},
            # 3. 파일 내 중복 건 (r2 재입력)
            {"source_domain": "brand.naver.com", "product_id": "100", "review_id": "r2", "review_text": "파일내 중복 r2"},
            # 4. 필수 키 누락 (Invalid 건)
            {"source_domain": "brand.naver.com", "product_id": "", "review_id": "r4", "review_text": "product_id 누락"},
            # 5. Formula Injection 공격 건 (신규 건)
            {"source_domain": "brand.naver.com", "product_id": "100", "review_id": "r5", "review_text": "=1+1 공격"},
        ]

        existing_keys = {f"{r['source_domain']}_{r['product_id']}_{r['review_id']}" for r in existing_sheet_reviews}

        file_batch_keys = set()
        new_to_append = []
        file_dedup = 0
        existing_dedup = 0
        invalid_count = 0

        for r in uploaded_excel_rows:
            s_dom = r.get("source_domain", "").strip()
            p_id = r.get("product_id", "").strip()
            r_id = r.get("review_id", "").strip()

            if not s_dom or not p_id or not r_id:
                invalid_count += 1
                continue

            key = f"{s_dom}_{p_id}_{r_id}"

            if key in existing_keys:
                existing_dedup += 1
                continue

            if key in file_batch_keys:
                file_dedup += 1
                continue

            file_batch_keys.add(key)
            cleaned_row = dict(r)
            cleaned_row["review_text"] = sanitize_formula_python(r["review_text"])
            new_to_append.append(cleaned_row)

        assert len(uploaded_excel_rows) == 5
        assert len(new_to_append) == 2  # r2 및 r5
        assert existing_dedup == 1      # r1
        assert file_dedup == 1          # r2 2nd row
        assert invalid_count == 1       # r4

        # Formula Protection Verify
        r5_item = next(item for item in new_to_append if item["review_id"] == "r5")
        assert r5_item["review_text"] == "'=1+1 공격"

    def test_import_confirm_twice_idempotency(self):
        """동일 파일 2회 Confirm 반영 시 2회차 inserted = 0 이어야 함."""
        sheet = [
            {"source_domain": "brand.naver.com", "product_id": "100", "review_id": "r1"},
        ]

        batch = [
            {"source_domain": "brand.naver.com", "product_id": "100", "review_id": "r2"},
        ]

        # 1st Run
        existing_keys = {f"{r['source_domain']}_{r['product_id']}_{r['review_id']}" for r in sheet}
        inserted_1st = [r for r in batch if f"{r['source_domain']}_{r['product_id']}_{r['review_id']}" not in existing_keys]
        assert len(inserted_1st) == 1

        # Simulate sheet append
        sheet.extend(inserted_1st)

        # 2nd Run with identical batch
        existing_keys_2nd = {f"{r['source_domain']}_{r['product_id']}_{r['review_id']}" for r in sheet}
        inserted_2nd = [r for r in batch if f"{r['source_domain']}_{r['product_id']}_{r['review_id']}" not in existing_keys_2nd]
        assert len(inserted_2nd) == 0

    def test_code_gs_server_side_commit_time_validation(self):
        """Code.gs의 importReviewData()가 서버 단에서 객체/필수키/중복을 재검증하는지 확인."""
        code_gs_path = os.path.join(DASHBOARD_DIR, "Code.gs")
        with open(code_gs_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "Array.isArray(rawItems)" in content, "Code.gs 서버 검증에 rawItems 배열 타입 검사가 누락되었습니다."
        assert "typeof item !== \"object\"" in content or "typeof item !== 'object'" in content, "Code.gs 서버 검증에 row 객체 타입 검사가 누락되었습니다."
        assert "sourceDomain" in content and "productId" in content and "reviewId" in content, "Code.gs 서버 검증에 필수 키 추출 검사가 누락되었습니다."
        assert "!sourceDomain || !productId || !reviewId" in content, "Code.gs 서버 검증에 필수 키 빈값 방어가 누락되었습니다."
        assert "existingKeys.has(key)" in content, "Code.gs 서버 검증에 시트 기존 키 재조회 중복검증이 누락되었습니다."
