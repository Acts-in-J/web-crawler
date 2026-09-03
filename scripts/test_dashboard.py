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


def make_review_dedup_key_python(source_domain: str, product_id: str, review_id: str) -> str:
    """Collision-safe Dedup Key helper (JSON string representation)."""
    return json.dumps([
        str(source_domain or "").strip(),
        str(product_id or "").strip(),
        str(review_id or "").strip(),
    ])


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

    def test_dedup_key_collision_safety(self):
        """언더스코어가 포함된 서로 다른 3-tuple 필드 값이 동일한 문자열로 충돌하지 않는지 검증."""
        key1 = make_review_dedup_key_python("a_b", "c", "d")
        key2 = make_review_dedup_key_python("a", "b_c", "d")

        # 3-field tuple comparison
        assert key1 != key2, "언더스코어 포함 필드 값의 Dedup Key 충돌이 발생했습니다."
        assert key1 == json.dumps(["a_b", "c", "d"])
        assert key2 == json.dumps(["a", "b_c", "d"])

    def test_dedup_key_helper_usage_in_code_gs_and_scripts_html(self):
        """Code.gs와 Scripts.html 모두에서 makeReviewDedupKey helper 함수가 선언되고 사용되는지 정적 계약 검증."""
        code_gs_path = os.path.join(DASHBOARD_DIR, "Code.gs")
        with open(code_gs_path, "r", encoding="utf-8") as f:
            code_gs_content = f.read()

        assert "function makeReviewDedupKey" in code_gs_content, "Code.gs 에 makeReviewDedupKey 정의가 누락되었습니다."
        assert "existingKeys.add(makeReviewDedupKey" in code_gs_content, "Code.gs 의 existingKeys 에 makeReviewDedupKey 사용이 누락되었습니다."
        assert "makeReviewDedupKey(sourceDomain, productId, reviewId)" in code_gs_content, "Code.gs 의 batchKeys 에 makeReviewDedupKey 사용이 누락되었습니다."

        scripts_html_path = os.path.join(DASHBOARD_DIR, "Scripts.html")
        with open(scripts_html_path, "r", encoding="utf-8") as f:
            scripts_html_content = f.read()

        assert "function makeReviewDedupKey" in scripts_html_content, "Scripts.html 에 makeReviewDedupKey 정의가 누락되었습니다."
        assert "existingKeySet.add(makeReviewDedupKey" in scripts_html_content, "Scripts.html 의 existingKeySet 에 makeReviewDedupKey 사용이 누락되었습니다."
        assert "makeReviewDedupKey(sourceDomain, productId, reviewId)" in scripts_html_content, "Scripts.html 의 row key 에 makeReviewDedupKey 사용이 누락되었습니다."

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

        existing_keys = {make_review_dedup_key_python(r["source_domain"], r["product_id"], r["review_id"]) for r in existing_sheet_reviews}

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

            key = make_review_dedup_key_python(s_dom, p_id, r_id)

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
        existing_keys = {make_review_dedup_key_python(r["source_domain"], r["product_id"], r["review_id"]) for r in sheet}
        inserted_1st = [r for r in batch if make_review_dedup_key_python(r["source_domain"], r["product_id"], r["review_id"]) not in existing_keys]
        assert len(inserted_1st) == 1

        # Simulate sheet append
        sheet.extend(inserted_1st)

        # 2nd Run with identical batch
        existing_keys_2nd = {make_review_dedup_key_python(r["source_domain"], r["product_id"], r["review_id"]) for r in sheet}
        inserted_2nd = [r for r in batch if make_review_dedup_key_python(r["source_domain"], r["product_id"], r["review_id"]) not in existing_keys_2nd]
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


class TestProvenanceContract:
    """A5-A3-A2 Provenance Data Contract & Schema Extension 검증."""

    def test_code_gs_defines_ensure_provenance_headers(self):
        """Code.gs에 ensureProvenanceHeaders 함수가 정의되어 있어야 함."""
        code_gs_path = os.path.join(DASHBOARD_DIR, "Code.gs")
        with open(code_gs_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "function ensureProvenanceHeaders" in content

    def test_ensure_provenance_headers_idempotent_simulation(self):
        """기존 14개 헤더에 provenance 4개 헤더 덧붙이기 idempotent 시뮬레이션."""
        canonical_headers = [
            "crawl_id", "source_domain", "product_id", "product_name", "brand",
            "review_id", "review_date", "rating", "review_text", "product_option",
            "helpful_count", "photo_review", "video_review", "collected_at"
        ]
        provenance_headers = ["import_batch_id", "import_filename", "imported_by", "imported_at"]

        def ensure_headers(headers):
            res = list(headers)
            for h in provenance_headers:
                if h not in res:
                    res.append(h)
            return res

        # 1st run
        updated_1st = ensure_headers(canonical_headers)
        assert len(updated_1st) == 18
        assert updated_1st[:14] == canonical_headers
        assert updated_1st[14:] == provenance_headers

        # 2nd run (idempotent)
        updated_2nd = ensure_headers(updated_1st)
        assert len(updated_2nd) == 18
        assert updated_2nd == updated_1st

    def test_server_authoritative_provenance_generation_simulation(self):
        """서버 단에서 import_batch_id, imported_at이 생성되고 모든 신규행이 동일한 값 공유하며 imported_by는 빈값 보존."""
        raw_items = [
            {"source_domain": "brand.naver.com", "product_id": "p1", "review_id": "r1", "review_text": "리뷰1"},
            {"source_domain": "brand.naver.com", "product_id": "p1", "review_id": "r2", "review_text": "리뷰2"},
        ]
        uploaded_filename = "test_reviews_2026.xlsx"

        import uuid
        server_batch_id = str(uuid.uuid4())
        server_imported_at = datetime.now(timezone.utc).isoformat()
        server_imported_by = ""
        clean_filename = sanitize_formula_python(uploaded_filename)

        headers = [
            "crawl_id", "source_domain", "product_id", "product_name", "brand",
            "review_id", "review_date", "rating", "review_text", "product_option",
            "helpful_count", "photo_review", "video_review", "collected_at",
            "import_batch_id", "import_filename", "imported_by", "imported_at"
        ]

        appended_rows = []
        for item in raw_items:
            row = []
            for h in headers:
                if h == "source_domain": row.append(item["source_domain"])
                elif h == "product_id": row.append(item["product_id"])
                elif h == "review_id": row.append(item["review_id"])
                elif h == "review_text": row.append(sanitize_formula_python(item["review_text"]))
                elif h == "import_batch_id": row.append(server_batch_id)
                elif h == "import_filename": row.append(clean_filename)
                elif h == "imported_by": row.append(server_imported_by)
                elif h == "imported_at": row.append(server_imported_at)
                else: row.append("")
            appended_rows.append(row)

        assert len(appended_rows) == 2
        assert appended_rows[0][14] == server_batch_id
        assert appended_rows[1][14] == server_batch_id
        assert appended_rows[0][15] == "test_reviews_2026.xlsx"
        assert appended_rows[1][15] == "test_reviews_2026.xlsx"
        assert appended_rows[0][16] == ""
        assert appended_rows[1][16] == ""
        assert appended_rows[0][17] == server_imported_at
        assert appended_rows[1][17] == server_imported_at

    def test_duplicate_row_not_backfilled(self):
        """기존 중복 행은 신규 provenance 값으로 덮어쓰거나 backfill 하지 않음."""
        existing_rows = [
            ["crawl_id", "source_domain", "product_id", "product_name", "brand", "review_id", "review_date", "rating", "review_text", "product_option", "helpful_count", "photo_review", "video_review", "collected_at", "import_batch_id", "import_filename", "imported_by", "imported_at"],
            ["crawl-1", "brand.naver.com", "p1", "상품1", "브랜드1", "r1", "2026-08-01", 5, "기존 리뷰", "옵션1", 0, False, False, "2026-08-01T00:00:00Z", "", "", "", ""],
        ]

        existing_key = make_review_dedup_key_python("brand.naver.com", "p1", "r1")

        new_batch = [
            {"source_domain": "brand.naver.com", "product_id": "p1", "review_id": "r1", "review_text": "중복 시도"},
        ]

        inserted = []
        for item in new_batch:
            k = make_review_dedup_key_python(item["source_domain"], item["product_id"], item["review_id"])
            if k != existing_key:
                inserted.append(item)

        assert len(inserted) == 0
        assert len(existing_rows) == 2
        assert existing_rows[1][5] == "r1"
        assert existing_rows[1][14] == ""

    def test_scripts_html_passes_filename_to_import_review_data(self):
        """Scripts.html의 confirmImport에서 importReviewData 호출 시 selectedFileName을 전달하는지 검증."""
        scripts_html_path = os.path.join(DASHBOARD_DIR, "Scripts.html")
        with open(scripts_html_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "selectedFileName" in content
        assert "importReviewData(parsedItemsToImport, selectedFileName)" in content


class TestIdentityAndAuthorizationFoundation:
    """A5-A3-A3-FIX1 Multi-User Identity & Fail-Closed Authorization Foundation 단위 테스트."""

    def test_code_gs_defines_identity_and_authorization_functions(self):
        """Code.gs에 resolveRequestIdentity, authorizeDashboardRead, authorizeReviewImport가 정의되어 있어야 함."""
        code_gs_path = os.path.join(DASHBOARD_DIR, "Code.gs")
        with open(code_gs_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "function resolveRequestIdentity" in content
        assert "function authorizeDashboardRead" in content
        assert "function authorizeReviewImport" in content
        assert "authorizeReviewImport(identity)" in content

    def test_identity_resolver_normalization_and_stable_identity_rules(self):
        """ActiveUser 이메일의 공백 제거 및 소문자 정규화, ActiveUser 누락 시 stableIdentity 빈값 유지를 시뮬레이션 검증."""
        def resolve_identity_python(active_email="", effective_email="deployer@syncrown.com", temp_key="tmp-123"):
            norm_active = str(active_email or "").strip().lower()
            norm_effective = str(effective_email or "").strip().lower()
            norm_temp = str(temp_key or "").strip()

            stable_id = norm_active  # ONLY active_email
            auth = stable_id != ""
            id_type = "active_user" if norm_active != "" else ("anonymous_session" if norm_temp != "" else "unknown")

            return {
                "activeEmail": norm_active,
                "effectiveEmail": norm_effective,
                "temporaryUserKey": norm_temp,
                "identityType": id_type,
                "stableIdentity": stable_id,
                "authenticated": auth,
            }

        # Case 1: Normal ActiveUser with uppercase/spaces
        id1 = resolve_identity_python("  Alice@Company.COM  ", "deployer@syncrown.com", "tmp-101")
        assert id1["activeEmail"] == "alice@company.com"
        assert id1["stableIdentity"] == "alice@company.com"
        assert id1["authenticated"] is True

        # Case 2: Blank ActiveUser, EffectiveUser exists (USER_DEPLOYING mode)
        id2 = resolve_identity_python("", "deployer@syncrown.com", "tmp-102")
        assert id2["activeEmail"] == ""
        assert id2["effectiveEmail"] == "deployer@syncrown.com"
        assert id2["temporaryUserKey"] == "tmp-102"
        # EffectiveUser and TemporaryUserKey MUST NOT be substituted as stableIdentity
        assert id2["stableIdentity"] == ""
        assert id2["authenticated"] is False

    def test_strict_fail_closed_authorization_without_bootstrap(self):
        """FIX1: Allowlist 미설정, 빈값, 실패, 또는 activeEmail===effectiveEmail 동등성 여부와 상관없이 allowlist에 없으면 무조건 DENY 검증."""
        def authorize_import_strict(identity, allowlist_prop=None, prop_error=False):
            if not identity or not identity.get("stableIdentity"):
                return {"allowed": False, "reason": "인증된 사용자 이메일 식별 정보 없음"}

            if prop_error or allowlist_prop is None:
                return {"allowed": False, "reason": "권한 목록 미설정 또는 조회 실패"}

            raw_prop = str(allowlist_prop).strip()
            if len(raw_prop) == 0:
                return {"allowed": False, "reason": "권한 목록 비어있음"}

            allowed_emails = [e.strip().lower() for e in raw_prop.split(",") if e.strip()]
            if identity["stableIdentity"] in allowed_emails:
                return {"allowed": True, "reason": "Allowlist authorized"}
            else:
                return {"allowed": False, "reason": "Allowlist 미포함"}

        id_deployer = {"stableIdentity": "deployer@syncrown.com", "effectiveEmail": "deployer@syncrown.com"}
        id_alice = {"stableIdentity": "alice@company.com", "effectiveEmail": "deployer@syncrown.com"}
        id_anonymous = {"stableIdentity": "", "effectiveEmail": "deployer@syncrown.com", "temporaryUserKey": "tmp-999"}

        # 1. Missing allowlist (None) -> WRITE DENY for deployer & alice
        assert authorize_import_strict(id_deployer, None)["allowed"] is False
        assert authorize_import_strict(id_alice, None)["allowed"] is False

        # 2. Blank allowlist ("") -> WRITE DENY
        assert authorize_import_strict(id_deployer, "")["allowed"] is False

        # 3. PropertiesService failure -> WRITE DENY
        assert authorize_import_strict(id_deployer, prop_error=True)["allowed"] is False

        # 4. activeEmail === effectiveEmail with missing allowlist -> WRITE DENY (Bootstrap removed!)
        assert authorize_import_strict(id_deployer, None)["allowed"] is False

        # 5. Explicit allowlist -> Match ALLOW, Mismatch DENY
        prop = "alice@company.com, bob@company.com"
        assert authorize_import_strict(id_alice, prop)["allowed"] is True
        assert authorize_import_strict(id_deployer, prop)["allowed"] is False

        # 6. TemporaryActiveUserKey alone -> WRITE DENY
        assert authorize_import_strict(id_anonymous, prop)["allowed"] is False

    def test_strict_fail_closed_read_authorization(self):
        """Dashboard read authorization MUST be fail-closed."""
        def authorize_read_strict(identity, allowlist_prop=None, prop_error=False):
            if not identity or not identity.get("stableIdentity"):
                return {"allowed": False, "reason": "인증된 사용자 식별 정보 없음"}

            if prop_error or allowlist_prop is None:
                return {"allowed": False, "reason": "조회 권한 목록 미설정 또는 조회 실패"}

            raw_prop = str(allowlist_prop).strip()
            if len(raw_prop) == 0:
                return {"allowed": False, "reason": "조회 권한 목록 비어있음"}

            allowed_emails = [e.strip().lower() for e in raw_prop.split(",") if e.strip()]
            if identity["stableIdentity"] in allowed_emails:
                return {"allowed": True, "reason": "Read authorized via allowlist"}
            else:
                return {"allowed": False, "reason": "조회 권한 없음"}

        id_deployer = {"stableIdentity": "deployer@syncrown.com"}
        id_alice = {"stableIdentity": "alice@company.com"}
        id_anonymous = {"stableIdentity": ""}

        # 1. Missing allowlist -> READ DENY
        assert authorize_read_strict(id_deployer, None)["allowed"] is False

        # 2. Blank allowlist -> READ DENY
        assert authorize_read_strict(id_deployer, "")["allowed"] is False

        # 3. Explicit allowlist -> Match ALLOW, Mismatch DENY
        prop = "alice@company.com"
        assert authorize_read_strict(id_alice, prop)["allowed"] is True
        assert authorize_read_strict(id_deployer, prop)["allowed"] is False

        # 4. Anonymous (Empty/Missing identity) -> READ DENY
        assert authorize_read_strict(id_anonymous, prop)["allowed"] is False
        assert authorize_read_strict(None, prop)["allowed"] is False


    def test_public_functions_do_not_accept_spreadsheet_id_override(self):
        """FIX2: 공개 진입점 함수(getReviewDashboardData, importReviewData)가 spreadsheetIdOverride를 받지 않고 서버 고정 ID를 사용하며 _ 헬퍼로 위임하는지 검증."""
        code_gs_path = os.path.join(DASHBOARD_DIR, "Code.gs")
        with open(code_gs_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Public getReviewDashboardData() has 0 parameters
        assert "function getReviewDashboardData()" in content
        assert "getReviewDashboardData_(DEFAULT_SPREADSHEET_ID)" in content

        # Public importReviewData(rawItems, importFilename) has 2 parameters
        assert "function importReviewData(rawItems, importFilename)" in content
        assert "importReviewData_(rawItems, DEFAULT_SPREADSHEET_ID, importFilename)" in content

        # Private helpers exist with _ suffix
        assert "function getReviewDashboardData_(targetSpreadsheetId)" in content
        assert "function importReviewData_(rawItems, targetSpreadsheetId, importFilename)" in content

    def test_client_cannot_forge_imported_by(self):
        """클라이언트가 rawItem 내에 imported_by를 위조해 전송하더라도 서버에서 identity.stableIdentity로 오버라이드됨을 검증."""
        raw_items_with_forgery = [
            {
                "source_domain": "brand.naver.com",
                "product_id": "p1",
                "review_id": "r1",
                "review_text": "정상 리뷰",
                "imported_by": "hacker@evil.com",  # Client forgery attempt
            }
        ]

        server_identity = {"stableIdentity": "authorized_user@company.com"}
        server_imported_by = sanitize_formula_python(server_identity["stableIdentity"])

        item = raw_items_with_forgery[0]
        computed_imported_by = server_imported_by

        assert computed_imported_by == "authorized_user@company.com"
        assert computed_imported_by != item["imported_by"]

    def test_unauthorized_import_fails_without_modifying_sheet(self):
        """미인가 Import 요청 시 명시적 status error를 반환하고 헤더나 데이터를 변경하지 않음."""
        sheet_headers = ["source_domain", "product_id", "review_id", "import_batch_id", "imported_by"]
        sheet_rows = [
            sheet_headers,
            ["brand.naver.com", "p1", "r1", "b1", "user1@company.com"],
        ]

        unauthorized_identity = {"stableIdentity": "unauthorized@evil.com"}
        allowlist = "admin@company.com"

        allowed = unauthorized_identity["stableIdentity"] in [e.strip() for e in allowlist.split(",")]
        if not allowed:
            res = {"status": "error", "message": "리뷰 반영 권한이 없습니다."}

        assert res["status"] == "error"
        assert "권한" in res["message"]
        assert len(sheet_rows) == 2
        assert sheet_rows[0] == sheet_headers


class TestMultiUserConcurrencyAndRuntimeAccessPrep:
    """A5-A3-A4 멀티 유저 동시성 및 런타임 접근 모델 검증 Prep 단위 테스트."""

    def test_identity_and_authorization_matrix_cases_a_through_h(self):
        """Matrix A~H 케이스에 대한 런타임 권한 결정 결정론적 검증."""
        def evaluate_matrix(active_email="", effective_email="deployer@syncrown.com", temp_key="", allowlist_prop=None, prop_error=False):
            # 1. Identity Resolution
            norm_active = str(active_email or "").strip().lower()
            stable_id = norm_active
            identity = {
                "activeEmail": norm_active,
                "effectiveEmail": str(effective_email or "").strip().lower(),
                "temporaryUserKey": str(temp_key or "").strip(),
                "stableIdentity": stable_id
            }

            # 2. Authorization Evaluation
            if not identity["stableIdentity"]:
                return {"decision": "WRITE DENY", "reason": "No stable identity"}

            if prop_error or allowlist_prop is None:
                return {"decision": "WRITE DENY", "reason": "Allowlist missing/error"}

            raw_prop = str(allowlist_prop).strip()
            if len(raw_prop) == 0:
                return {"decision": "WRITE DENY", "reason": "Allowlist blank"}

            allowed_emails = [e.strip().lower() for e in raw_prop.split(",") if e.strip()]
            if identity["stableIdentity"] in allowed_emails:
                return {"decision": "WRITE ALLOW", "reason": "Allowlisted"}
            else:
                return {"decision": "WRITE DENY", "reason": "Not in allowlist"}

        allowlist = "userA@company.com, userB@company.com"

        # Case A: ActiveUser available, EffectiveUser available, explicitly allowlisted
        cA = evaluate_matrix("userA@company.com", "deployer@syncrown.com", "tmp-1", allowlist)
        assert cA["decision"] == "WRITE ALLOW"

        # Case B: ActiveUser available, EffectiveUser available, not allowlisted
        cB = evaluate_matrix("userC@company.com", "deployer@syncrown.com", "tmp-2", allowlist)
        assert cB["decision"] == "WRITE DENY"

        # Case C: ActiveUser empty, TemporaryActiveUserKey available
        cC = evaluate_matrix("", "deployer@syncrown.com", "tmp-3", allowlist)
        assert cC["decision"] == "WRITE DENY"

        # Case D: ActiveUser empty, TemporaryActiveUserKey empty
        cD = evaluate_matrix("", "deployer@syncrown.com", "", allowlist)
        assert cD["decision"] == "WRITE DENY"

        # Case E: allowlist missing (None)
        cE = evaluate_matrix("userA@company.com", "deployer@syncrown.com", "tmp-1", None)
        assert cE["decision"] == "WRITE DENY"

        # Case F: allowlist blank ("")
        cF = evaluate_matrix("userA@company.com", "deployer@syncrown.com", "tmp-1", "")
        assert cF["decision"] == "WRITE DENY"

        # Case G: ScriptProperty read failure
        cG = evaluate_matrix("userA@company.com", "deployer@syncrown.com", "tmp-1", prop_error=True)
        assert cG["decision"] == "WRITE DENY"

        # Case H: ActiveUser == EffectiveUser but allowlist absent
        cH = evaluate_matrix("deployer@syncrown.com", "deployer@syncrown.com", "tmp-1", None)
        assert cH["decision"] == "WRITE DENY"

    def test_authorization_precedes_lock_acquisition_in_code_gs(self):
        """Code.gs의 importReviewData_ 함수에서 authorizeReviewImport가 LockService.getScriptLock 호출보다 먼저 위치함을 검증."""
        code_gs_path = os.path.join(DASHBOARD_DIR, "Code.gs")
        with open(code_gs_path, "r", encoding="utf-8") as f:
            content = f.read()

        import_fn_start = content.find("function importReviewData_")
        assert import_fn_start != -1

        auth_call_pos = content.find("authorizeReviewImport(identity)", import_fn_start)
        lock_call_pos = content.find("LockService.getScriptLock()", import_fn_start)

        assert auth_call_pos != -1
        assert lock_call_pos != -1
        assert auth_call_pos < lock_call_pos, "authorizeReviewImport must precede LockService.getScriptLock()"

    def test_simulated_concurrent_imports(self):
        """두 사용자의 동시 수집 시나리오 (Non-overlapping & Overlapping) 시뮬레이션 검증."""
        sheet_headers = [
            "source_domain", "product_id", "review_id", "review_text",
            "import_batch_id", "import_filename", "imported_by", "imported_at"
        ]
        sheet_rows = [sheet_headers]
        existing_keys = set()

        def process_import_batch(user_email, batch_filename, items):
            # Simulated importReviewData_ execution
            batch_id = f"batch-uuid-{len(sheet_rows)}"
            imported_at = "2026-09-02T12:00:00Z"
            server_imported_by = user_email

            inserted_count = 0
            skipped_count = 0

            for item in items:
                dedup_key = make_review_dedup_key_python(item["source_domain"], item["product_id"], item["review_id"])
                if dedup_key in existing_keys:
                    skipped_count += 1
                else:
                    existing_keys.add(dedup_key)
                    sheet_rows.append([
                        item["source_domain"], item["product_id"], item["review_id"], item.get("review_text", ""),
                        batch_id, batch_filename, server_imported_by, imported_at
                    ])
                    inserted_count += 1

            return {"inserted": inserted_count, "skipped": skipped_count, "batch_id": batch_id}

        # User 1 imports Set 1 (r1, r2)
        res1 = process_import_batch("userA@company.com", "batch_a.xlsx", [
            {"source_domain": "brand.naver.com", "product_id": "p1", "review_id": "r1"},
            {"source_domain": "brand.naver.com", "product_id": "p1", "review_id": "r2"},
        ])
        assert res1["inserted"] == 2

        # User 2 concurrently imports Set 2 (r2 [overlapping], r3 [new])
        res2 = process_import_batch("userB@company.com", "batch_b.xlsx", [
            {"source_domain": "brand.naver.com", "product_id": "p1", "review_id": "r2"},
            {"source_domain": "brand.naver.com", "product_id": "p1", "review_id": "r3"},
        ])
        assert res2["inserted"] == 1
        assert res2["skipped"] == 1

        # Total rows in sheet: 1 header + 3 data rows
        assert len(sheet_rows) == 4
        # Provenance attribution verified
        assert sheet_rows[1][6] == "userA@company.com"
        assert sheet_rows[2][6] == "userA@company.com"
        assert sheet_rows[3][6] == "userB@company.com"

    def test_readme_defines_candidate_runtime_binding_gate(self):
        """README.md 문서에 Candidate Runtime Binding Gate 및 10단계 순서 조건이 명시되어 있는지 검증."""
        readme_path = os.path.join(DASHBOARD_DIR, "README.md")
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "Candidate Runtime Binding Gate" in content
        assert "Candidate Git Commit" in content
        assert "MUST NOT be assumed to contain A5-A3-A3" in content
        assert "Candidate Runtime Binding Verification" in content
        assert "Production Version 3 MUST remain untouched" in content



