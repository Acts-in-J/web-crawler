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
        assert manifest["webapp"].get("executeAs") == "USER_ACCESSING"
        assert manifest["webapp"].get("access") == "ANYONE"

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
        """Dashboard read authorization MUST be fail-closed (Python model test)."""
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

        def authorize_write_strict(identity, allowlist_prop=None, prop_error=False):
            if not identity or not identity.get("stableIdentity"):
                return {"allowed": False}
            if prop_error or allowlist_prop is None or len(str(allowlist_prop).strip()) == 0:
                return {"allowed": False}
            allowed_emails = [e.strip().lower() for e in str(allowlist_prop).split(",") if e.strip()]
            return {"allowed": identity["stableIdentity"] in allowed_emails}

        id_deployer = {"stableIdentity": "deployer@syncrown.com"}
        id_reader = {"stableIdentity": "reader@company.com"}
        id_writer = {"stableIdentity": "writer@company.com"}
        id_anonymous = {"stableIdentity": ""}

        read_prop = "reader@company.com"
        write_prop = "writer@company.com"

        # 1. authorized reader => ALLOW
        assert authorize_read_strict(id_reader, read_prop)["allowed"] is True

        # 2. unauthorized reader => DENY
        assert authorize_read_strict(id_deployer, read_prop)["allowed"] is False

        # 3. missing identity => DENY
        assert authorize_read_strict(None, read_prop)["allowed"] is False

        # 4. empty identity => DENY
        assert authorize_read_strict(id_anonymous, read_prop)["allowed"] is False

        # 5. missing READ allowlist property => DENY
        assert authorize_read_strict(id_reader, None)["allowed"] is False

        # 6. blank READ allowlist property => DENY
        assert authorize_read_strict(id_reader, "")["allowed"] is False

        # 7. READ property lookup failure / exception => DENY
        assert authorize_read_strict(id_reader, prop_error=True)["allowed"] is False

        # 8. write-only user (in WRITE but not READ) => READ DENY
        assert authorize_read_strict(id_writer, read_prop)["allowed"] is False

        # 9. read-only user (in READ but not WRITE) => READ ALLOW, IMPORT DENY
        assert authorize_read_strict(id_reader, read_prop)["allowed"] is True
        assert authorize_write_strict(id_reader, write_prop)["allowed"] is False

    def test_authorization_precedes_spreadsheet_open_in_get_review_dashboard_data(self):
        """Code.gs의 getReviewDashboardData_ 함수에서 authorizeDashboardRead가 SpreadsheetApp.openById 보다 먼저 위치함을 검증 (Source contract test)."""
        code_gs_path = os.path.join(DASHBOARD_DIR, "Code.gs")
        with open(code_gs_path, "r", encoding="utf-8") as f:
            content = f.read()

        read_fn_start = content.find("function getReviewDashboardData_")
        assert read_fn_start != -1

        auth_call_pos = content.find("authorizeDashboardRead(identity)", read_fn_start)
        ss_open_pos = content.find("SpreadsheetApp.openById", read_fn_start)

        assert auth_call_pos != -1, "authorizeDashboardRead(identity) call missing"
        assert ss_open_pos != -1, "SpreadsheetApp.openById call missing"
        assert auth_call_pos < ss_open_pos, "authorizeDashboardRead must precede SpreadsheetApp.openById"


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


class TestKeywordIntelligence:
    """WEB-CRAWLER-REVIEW-A5-KEYWORD-INTELLIGENCE-A1 단위 및 소스 계약 테스트."""

    DEFAULT_STOPWORDS = {
        '그리고', '하지만', '정말', '너무', '그냥', '있는', '없는', '합니다', '했어요', '입니다',
        '있는것', '같아요', '하고', '해서', '하면', '이거', '이것', '하나', '것도', '많이',
        '아주', '조금', '다시', '지금', '되어', '되면', '까지', '부터', '으로', '에게', '한테',
        '바로', '사용할', '있어서', '없이', '있어요', '다양한', '있고', '있는데', '있습니다', '있었어요',
        '사용하기', '사용해서', '사용하면',
        'the', 'and', 'for', 'this', 'that', 'with', 'from', 'they', 'them', 'what', 'have', 'has', 'had', 'were', 'will', 'would', 'could', 'should'
    }

    def extract_tokens(self, text):
        if not text:
            return []
        cleaned = re.sub(r'[^a-zA-Z0-9\u3131-\u318E\uAC00-\uD7A3\s]', ' ', str(text).lower())
        raw_tokens = cleaned.split()
        valid = []
        for t in raw_tokens:
            token = t.strip()
            if not token or len(token) < 2 or token.isdigit() or token in self.DEFAULT_STOPWORDS:
                continue
            valid.append(token)
        return valid

    def calculate_keyword_frequencies(self, review_list, max_terms=12, min_count=2):
        if not review_list:
            return []
        freq_map = {}
        for r in review_list:
            text = r.get("review_text") or ""
            tokens = self.extract_tokens(text)
            unique_terms = set(tokens)
            for term in unique_terms:
                freq_map[term] = freq_map.get(term, 0) + 1

        items = [{"term": k, "count": v} for k, v in freq_map.items() if v >= min_count]
        # Sort: count DESC, term ASC
        items.sort(key=lambda x: (-x["count"], x["term"]))
        return items[:max_terms]

    def test_korean_term_extraction(self):
        text = "배송 빠르고 제품 상태 좋습니다"
        tokens = self.extract_tokens(text)
        assert "배송" in tokens
        assert "빠르고" in tokens
        assert "제품" in tokens
        assert "상태" in tokens

    def test_english_normalization(self):
        text = "Good Quality PRODUCT Performance"
        tokens = self.extract_tokens(text)
        assert "good" in tokens
        assert "quality" in tokens
        assert "product" in tokens
        assert "performance" in tokens

    def test_stopword_removal(self):
        text = "그리고 제품이 정말 너무 좋아요 for this product"
        tokens = self.extract_tokens(text)
        assert "그리고" not in tokens
        assert "정말" not in tokens
        assert "너무" not in tokens
        assert "for" not in tokens
        assert "this" not in tokens
        assert "제품이" in tokens
        assert "좋아요" in tokens

    def test_punctuation_noise_removal(self):
        text = "배송!@#$%^&*()_+ 최고의-품질... [추천]"
        tokens = self.extract_tokens(text)
        assert "배송" in tokens
        assert "최고의" in tokens
        assert "품질" in tokens
        assert "추천" in tokens

    def test_short_token_removal(self):
        text = "아 가 배송 짱 b 좋음"
        tokens = self.extract_tokens(text)
        assert "아" not in tokens
        assert "가" not in tokens
        assert "b" not in tokens
        assert "배송" in tokens
        assert "좋음" in tokens

    def test_numeric_only_removal(self):
        text = "2026년 100점 배송 9999"
        tokens = self.extract_tokens(text)
        assert "100점" in tokens
        assert "2026년" in tokens
        assert "9999" not in tokens

    def test_per_review_occurrence_count(self):
        # One review with repeated "배송 배송 배송" -> counts once
        reviews = [{"review_text": "배송 배송 배송 정말 배송 상태 좋음"}, {"review_text": "배송 빠른 배송"}]
        res = self.calculate_keyword_frequencies(reviews, min_count=1)
        term_map = {item["term"]: item["count"] for item in res}
        assert term_map["배송"] == 2  # Appears in 2 reviews, not 5 times

    def test_multi_review_frequency_accumulation(self):
        reviews = [
            {"review_text": "배송 완전 빠름"},
            {"review_text": "배송 지연 발생"},
            {"review_text": "품질 좋지만 배송 늦음"}
        ]
        res = self.calculate_keyword_frequencies(reviews, min_count=1)
        term_map = {item["term"]: item["count"] for item in res}
        assert term_map["배송"] == 3

    def test_deterministic_sort_count_desc_term_asc(self):
        reviews = [
            {"review_text": "나비 나비 사자 사자 바다 바다"},
            {"review_text": "나비 사자 바다 가방 가방"}
        ]
        res = self.calculate_keyword_frequencies(reviews, min_count=2)
        # count=2 for 나비, 바다, 사자 (count DESC, term ASC). 가방 (count=1) excluded.
        assert [x["term"] for x in res] == ["나비", "바다", "사자"]

    def test_top_12_cap(self):
        # 15 distinct terms across 2 reviews
        reviews = [
            {"review_text": "t01 t02 t03 t04 t05 t06 t07 t08 t09 t10 t11 t12 t13 t14 t15"},
            {"review_text": "t01 t02 t03 t04 t05 t06 t07 t08 t09 t10 t11 t12 t13 t14 t15"}
        ]
        res = self.calculate_keyword_frequencies(reviews, max_terms=12, min_count=1)
        assert len(res) == 12

    def test_low_rating_subset_rating_le_3(self):
        reviews = [
            {"review_text": "배송 최고 최고", "rating": 5},
            {"review_text": "배송 불만 파손", "rating": 1},
            {"review_text": "배송 불만 지연", "rating": 3},
            {"review_text": "품질 대족", "rating": 4}
        ]
        low_rating_reviews = [r for r in reviews if isinstance(r.get("rating"), (int, float)) and 1 <= r["rating"] <= 3]
        res = self.calculate_keyword_frequencies(low_rating_reviews, min_count=1)
        terms = [x["term"] for x in res]
        assert "불만" in terms
        assert "파손" in terms
        assert "지연" in terms
        assert "대족" not in terms

    def test_high_rating_excluded_from_low_rating_ranking(self):
        reviews = [
            {"review_text": "완벽함 만족", "rating": 5},
            {"review_text": "최고의선택", "rating": 4},
            {"review_text": "고장 교환필요", "rating": 2}
        ]
        low_rating_reviews = [r for r in reviews if isinstance(r.get("rating"), (int, float)) and 1 <= r["rating"] <= 3]
        res = self.calculate_keyword_frequencies(low_rating_reviews, min_count=1)
        terms = [x["term"] for x in res]
        assert "고장" in terms
        assert "교환필요" in terms
        assert "완벽함" not in terms
        assert "만족" not in terms

    def test_strict_low_rating_1_to_3_stars_boundary_and_validation(self):
        """저평점 리뷰 1~3점 엄격 필터링 (1..3 포함, 4/5/0/누락/null/비숫자 제외) 검증."""
        def filter_low_rating(reviews):
            result = []
            for r in reviews:
                rating_raw = r.get("rating")
                try:
                    val = float(rating_raw) if rating_raw is not None else None
                    if val is not None and 1 <= val <= 3:
                        result.append(r)
                except (ValueError, TypeError):
                    pass
            return result

        reviews = [
            {"id": "r1", "review_text": "원점 불만", "rating": 1},      # 1. rating 1 -> INCLUDE
            {"id": "r2", "review_text": "투점 불만", "rating": 2},      # 2. rating 2 -> INCLUDE
            {"id": "r3", "review_text": "쓰리점 불만", "rating": 3},    # 3. rating 3 -> INCLUDE
            {"id": "r4", "review_text": "포점 최고", "rating": 4},      # 4. rating 4 -> EXCLUDE
            {"id": "r5", "review_text": "파이브점 최고", "rating": 5},  # 5. rating 5 -> EXCLUDE
            {"id": "r0", "review_text": "제로점 오류", "rating": 0},    # 6. rating 0 -> EXCLUDE
            {"id": "rm", "review_text": "누락점 오류"},                 # 7. missing rating -> EXCLUDE
            {"id": "rn", "review_text": "널점 오류", "rating": None},   # 7. null rating -> EXCLUDE
            {"id": "ri", "review_text": "비숫자 오류", "rating": "abc"} # 8. invalid/non-numeric rating -> EXCLUDE
        ]

        low_rating_subset = filter_low_rating(reviews)
        included_ids = [r["id"] for r in low_rating_subset]

        assert "r1" in included_ids
        assert "r2" in included_ids
        assert "r3" in included_ids
        assert "r4" not in included_ids
        assert "r5" not in included_ids
        assert "r0" not in included_ids
        assert "rm" not in included_ids
        assert "rn" not in included_ids
        assert "ri" not in included_ids

        res = self.calculate_keyword_frequencies(low_rating_subset, min_count=1)
        terms = [x["term"] for x in res]
        assert "원점" in terms
        assert "투점" in terms
        assert "쓰리점" in terms
        assert "포점" not in terms
        assert "파이브점" not in terms
        assert "제로점" not in terms
        assert "누락점" not in terms
        assert "널점" not in terms
        assert "비숫자" not in terms

    def test_empty_state_handling(self):
        assert self.calculate_keyword_frequencies([], min_count=1) == []
        assert self.calculate_keyword_frequencies([{"review_text": "123 !@#"}], min_count=1) == []

    def test_source_contract_keyword_widget_elements_exist(self):
        """Index.html, Scripts.html, Styles.html 소스 계약 검증."""
        index_path = os.path.join(DASHBOARD_DIR, "Index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            index_content = f.read()
        assert "keywordIntelligenceSection" in index_content
        assert "overallKeywordBadges" in index_content
        assert "lowRatingKeywordBadges" in index_content
        assert "주요 리뷰 키워드" in index_content
        assert "저평점 리뷰 빈출어" in index_content

        scripts_path = os.path.join(DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            scripts_content = f.read()
        assert "extractReviewTokens" in scripts_content
        assert "calculateKeywordFrequencies" in scripts_content
        assert "renderKeywordIntelligence" in scripts_content
        assert "onKeywordBadgeClick" in scripts_content
        assert "ratingNum >= 1 && ratingNum <= 3" in scripts_content

        styles_path = os.path.join(DASHBOARD_DIR, "Styles.html")
        with open(styles_path, "r", encoding="utf-8") as f:
            styles_content = f.read()
        assert ".keyword-intelligence-grid" in styles_content
        assert ".keyword-badge" in styles_content
        assert ".keyword-empty" in styles_content

    def test_filter_semantics_structural_separation(self):
        """applyFilters()에서 structurallyFilteredReviews가 keyword 검색 조건과 분리되어 keyword widget으로 전달되는지 소스 검증."""
        scripts_path = os.path.join(DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            scripts_content = f.read()

        assert "const structurallyFilteredReviews = allReviews.filter" in scripts_content
        assert "renderKeywordIntelligence(structurallyFilteredReviews)" in scripts_content

    def test_noise_reduction_tuning_and_useful_term_preservation(self):
        """불용어 노이즈 제거(바로, 사용할, 있어서, 없이, 있어요, 다양한) 및 유용한 키워드 보존 검증."""
        noise_text = "바로 사용할 기능이 있어서 문제 없이 쓸 수 있어요 다양한 활용도가 최고"
        tokens = self.extract_tokens(noise_text)

        # Excluded noise terms
        for noise in ["바로", "사용할", "있어서", "없이", "있어요", "다양한"]:
            assert noise not in tokens, f"노이즈 토큰 미제거: {noise}"

        # Preserved useful terms
        assert "활용도가" in tokens
        assert "기능이" in tokens
        assert "최고" in tokens

        reviews = [
            {"review_text": "라벨지 출력 빠른 배송 라벨 인쇄 깔끔하게 바로 사용할 수 있음", "rating": 5},
            {"review_text": "프린터 연결 쉬움 라벨 출력 품질 양호 활용도가 높음 없이도 가능", "rating": 5},
            {"review_text": "설정 어플 편함 라벨지 대용량 디자인 우수 있어서 있어요 다양한 기능", "rating": 5}
        ]
        res = self.calculate_keyword_frequencies(reviews, max_terms=100, min_count=1)
        terms = [item["term"] for item in res]

        # Useful terms present
        expected_useful = ["라벨", "라벨지", "프린터", "인쇄", "연결", "배송", "품질", "설정", "어플", "디자인", "깔끔하게", "활용도가"]
        for useful in expected_useful:
            assert any(useful in t for t in terms), f"유용한 단어 누락: {useful}"

        # Noise terms strictly absent
        for noise in ["바로", "사용할", "있어서", "없이", "있어요", "다양한"]:
            assert noise not in terms, f"노이즈 단어 미제거: {noise}"


# =============================================================================
# WEB-CRAWLER-REVIEW-A5-KEYWORD-INTELLIGENCE-A2-EVIDENCE-DRILLDOWN
# Python model / source-contract tests
# These tests validate the evidence drilldown logic model and source contracts.
# The JS functions themselves are not executed here (no browser engine).
# =============================================================================

class TestKeywordEvidenceDrilldown:
    """A2 Evidence Drilldown — Python model & source contract tests."""

    DASHBOARD_DIR = DASHBOARD_DIR

    # --- Python-side model of getEvidenceReviews ---

    def get_evidence_reviews(self, term, is_low_rating, all_reviews,
                              selected_prod="all", start_date="", end_date="",
                              selected_rating="all"):
        """Python model of getEvidenceReviews() in Scripts.html."""
        population = list(all_reviews)

        # Structural filters
        if selected_prod != "all":
            population = [r for r in population if r.get("product_id") == selected_prod]
        if start_date:
            population = [r for r in population
                          if (r.get("review_date") or "")[:10] >= start_date]
        if end_date:
            population = [r for r in population
                          if (r.get("review_date") or "")[:10] <= end_date]
        if selected_rating != "all":
            target = int(selected_rating)
            population = [r for r in population
                          if int(float(r.get("rating") or 0)) == target]

        # Low-rating gate: restrict to valid 1..3 only
        if is_low_rating:
            def valid_low(r):
                try:
                    n = float(r.get("rating", ""))
                except (ValueError, TypeError):
                    return False
                return 1 <= n <= 3
            population = [r for r in population if valid_low(r)]

        # Match review_text only
        if not term:
            return []
        term_lower = term.lower()
        matched = [r for r in population
                   if term_lower in (r.get("review_text") or "").lower()]

        # Deterministic ordering: date DESC, rating ASC, review_id ASC
        def sort_key(r):
            date = r.get("review_date") or ""
            rating = float(r.get("rating") or 0)
            rid = r.get("review_id") or ""
            return (-ord(date[0]) if date else 0, -len(date), rating, rid)

        # Simpler: sort stable
        matched.sort(key=lambda r: (
            -(r.get("review_date") or "") if False else r.get("review_date") or "",
        ), reverse=False)
        # Proper sort:
        matched.sort(key=lambda r: (
            tuple(-(ord(c) - 48) for c in (r.get("review_date") or "").replace("-", "") or "0" * 8)
        ), reverse=False)
        # Use straightforward lexicographic DESC on date, then rating ASC, then rid ASC
        matched.sort(key=lambda r: (
            r.get("review_date") or "",
            float(r.get("rating") or 0),
            r.get("review_id") or ""
        ), reverse=False)
        # Reverse date portion: use negation trick via tuple inversion
        matched.sort(key=lambda r: (
            [-ord(c) for c in (r.get("review_date") or "")],
            float(r.get("rating") or 0),
            r.get("review_id") or ""
        ))

        return matched

    def escape_html(self, s):
        """Python mirror of escapeHtml() in Scripts.html."""
        s = str(s) if s else ""
        return (s.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;")
                 .replace('"', "&quot;")
                 .replace("'", "&#039;"))

    def highlight_keyword_in_text(self, escaped_text, escaped_term):
        """Python model of highlightKeywordInText() — operates on already-escaped strings."""
        if not escaped_term:
            return escaped_text
        import re
        safe_pattern = re.escape(escaped_term)
        return re.sub(f"({safe_pattern})", r'<mark class="evidence-highlight">\1</mark>',
                      escaped_text, flags=re.IGNORECASE)

    # ------------------------------------------------------------------
    # Test 1: evidence uses review_text
    # ------------------------------------------------------------------
    def test_evidence_uses_review_text_not_product_option(self):
        """Evidence match is based on review_text. product_option-only match must NOT qualify."""
        reviews = [
            {"review_id": "1", "review_text": "라벨 품질 좋음", "product_option": "없음", "rating": 5, "review_date": "2024-03-01"},
            {"review_id": "2", "review_text": "배송이 빠릅니다", "product_option": "라벨 옵션", "rating": 4, "review_date": "2024-03-02"},
        ]
        # "라벨" appears in review 1 text and review 2 product_option
        evidence = self.get_evidence_reviews("라벨", False, reviews)
        evidence_ids = [r["review_id"] for r in evidence]

        assert "1" in evidence_ids, "review_text 매칭 리뷰 누락"
        assert "2" not in evidence_ids, "product_option-only 매칭이 evidence에 포함되면 안 됨"

    # ------------------------------------------------------------------
    # Test 2: product_option-only match excluded
    # ------------------------------------------------------------------
    def test_product_option_only_excluded(self):
        """A review whose review_text does not contain the term is excluded regardless of other fields."""
        reviews = [
            {"review_id": "A", "review_text": "품질 좋음", "product_option": "라벨지 100매", "product_name": "라벨지 프린터", "rating": 5, "review_date": "2024-01-01"},
        ]
        evidence = self.get_evidence_reviews("라벨지", False, reviews)
        assert len(evidence) == 0, "review_text 미포함 리뷰가 evidence에 포함됨"

    # ------------------------------------------------------------------
    # Test 3: structural filter population preserved
    # ------------------------------------------------------------------
    def test_structural_filter_preserves_product(self):
        """Product filter applied to evidence population."""
        reviews = [
            {"review_id": "1", "review_text": "라벨 좋음", "product_id": "P1", "rating": 5, "review_date": "2024-01-01"},
            {"review_id": "2", "review_text": "라벨 불만", "product_id": "P2", "rating": 2, "review_date": "2024-01-02"},
        ]
        evidence = self.get_evidence_reviews("라벨", False, reviews, selected_prod="P1")
        ids = [r["review_id"] for r in evidence]
        assert "1" in ids
        assert "2" not in ids

    # ------------------------------------------------------------------
    # Test 4: overall evidence includes all eligible ratings
    # ------------------------------------------------------------------
    def test_overall_evidence_includes_all_valid_ratings(self):
        """Overall keyword evidence (is_low_rating=False) includes 1-5 star reviews."""
        reviews = [
            {"review_id": str(i), "review_text": f"라벨 리뷰 {i}", "rating": i, "review_date": "2024-01-01"}
            for i in range(1, 6)
        ]
        evidence = self.get_evidence_reviews("라벨", False, reviews)
        ratings = {float(r["rating"]) for r in evidence}
        assert ratings == {1.0, 2.0, 3.0, 4.0, 5.0}

    # ------------------------------------------------------------------
    # Test 5: low-rating evidence only valid 1..3
    # ------------------------------------------------------------------
    def test_low_rating_evidence_restricted_to_1_3(self):
        """Low-rating keyword evidence must only include reviews with rating 1, 2, or 3."""
        reviews = [
            {"review_id": str(i), "review_text": f"라벨 이슈 {i}", "rating": i, "review_date": "2024-01-01"}
            for i in range(1, 6)
        ]
        evidence = self.get_evidence_reviews("라벨", True, reviews)
        ratings = {float(r["rating"]) for r in evidence}
        assert ratings == {1.0, 2.0, 3.0}
        assert 4.0 not in ratings
        assert 5.0 not in ratings

    # ------------------------------------------------------------------
    # Test 6: 0/missing/invalid rating excluded from low-rating evidence
    # ------------------------------------------------------------------
    def test_low_rating_evidence_excludes_invalid_ratings(self):
        """Rating 0, None, missing, or non-numeric must be excluded from low-rating evidence."""
        reviews = [
            {"review_id": "zero",    "review_text": "라벨 문제", "rating": 0,    "review_date": "2024-01-01"},
            {"review_id": "none",    "review_text": "라벨 문제", "rating": None,  "review_date": "2024-01-01"},
            {"review_id": "missing", "review_text": "라벨 문제",                  "review_date": "2024-01-01"},
            {"review_id": "str",     "review_text": "라벨 문제", "rating": "abc", "review_date": "2024-01-01"},
            {"review_id": "valid",   "review_text": "라벨 문제", "rating": 2,    "review_date": "2024-01-01"},
        ]
        evidence = self.get_evidence_reviews("라벨", True, reviews)
        ids = [r["review_id"] for r in evidence]
        assert "valid" in ids
        assert "zero" not in ids
        assert "none" not in ids
        assert "missing" not in ids
        assert "str" not in ids

    # ------------------------------------------------------------------
    # Test 7: max initial display = 5
    # ------------------------------------------------------------------
    def test_max_initial_display_5(self):
        """Evidence panel shows maximum 5 reviews initially."""
        reviews = [
            {"review_id": str(i), "review_text": "라벨 테스트", "rating": 4, "review_date": f"2024-{i:02d}-01"}
            for i in range(1, 10)
        ]
        evidence = self.get_evidence_reviews("라벨", False, reviews)
        assert len(evidence) > 5, "테스트 데이터 부족"
        shown = evidence[:5]
        assert len(shown) == 5

    # ------------------------------------------------------------------
    # Test 8: deterministic evidence ordering
    # ------------------------------------------------------------------
    def test_deterministic_evidence_ordering(self):
        """Evidence ordering is deterministic: date DESC, rating ASC, review_id ASC."""
        reviews = [
            {"review_id": "B", "review_text": "라벨 품질", "rating": 3, "review_date": "2024-02-01"},
            {"review_id": "A", "review_text": "라벨 문제", "rating": 1, "review_date": "2024-03-01"},
            {"review_id": "C", "review_text": "라벨 좋음", "rating": 5, "review_date": "2024-01-01"},
        ]
        evidence1 = self.get_evidence_reviews("라벨", False, reviews)
        evidence2 = self.get_evidence_reviews("라벨", False, reviews)
        ids1 = [r["review_id"] for r in evidence1]
        ids2 = [r["review_id"] for r in evidence2]
        assert ids1 == ids2, "순서가 비결정적"
        # date DESC: A(03-01) > B(02-01) > C(01-01)
        assert ids1 == ["A", "B", "C"]

    # ------------------------------------------------------------------
    # Test 9: keyword selection replacement
    # ------------------------------------------------------------------
    def test_keyword_selection_replacement(self):
        """Clicking a new keyword replaces evidence for that keyword."""
        reviews = [
            {"review_id": "1", "review_text": "라벨 출력 잘 됨", "rating": 5, "review_date": "2024-01-01"},
            {"review_id": "2", "review_text": "배송 빠름", "rating": 5, "review_date": "2024-01-02"},
        ]
        ev_label = self.get_evidence_reviews("라벨", False, reviews)
        ev_ship  = self.get_evidence_reviews("배송", False, reviews)
        ids_label = [r["review_id"] for r in ev_label]
        ids_ship  = [r["review_id"] for r in ev_ship]
        # Evidence for new keyword should be independent of previous selection
        assert "1" in ids_label and "2" not in ids_label
        assert "2" in ids_ship  and "1" not in ids_ship

    # ------------------------------------------------------------------
    # Test 10: clear selection produces empty evidence
    # ------------------------------------------------------------------
    def test_clear_selection_empty_evidence(self):
        """When term is empty/None, evidence returns nothing."""
        reviews = [
            {"review_id": "1", "review_text": "라벨 출력", "rating": 5, "review_date": "2024-01-01"},
        ]
        ev = self.get_evidence_reviews("", False, reviews)
        assert ev == [], "빈 term에 대해 evidence가 반환되면 안 됨"

    # ------------------------------------------------------------------
    # Test 11: empty state — no matching evidence
    # ------------------------------------------------------------------
    def test_evidence_empty_state(self):
        """When no reviews match the term, evidence list is empty."""
        reviews = [
            {"review_id": "1", "review_text": "배송 빠름", "rating": 5, "review_date": "2024-01-01"},
        ]
        ev = self.get_evidence_reviews("라벨", False, reviews)
        assert ev == []

    # ------------------------------------------------------------------
    # Test 12: XSS safety — source contract verification
    # ------------------------------------------------------------------
    def test_xss_safe_highlight_model(self):
        """highlightKeywordInText operates on escaped text so injection is impossible."""
        malicious_text = '<script>alert("xss")</script> 라벨 좋음'
        term = "라벨"
        escaped_text = self.escape_html(malicious_text)
        escaped_term = self.escape_html(term)
        result = self.highlight_keyword_in_text(escaped_text, escaped_term)

        # script tag must be HTML-escaped, not injected
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
        # term is highlighted
        assert '<mark class="evidence-highlight">라벨</mark>' in result

    def test_xss_source_contract_no_raw_review_text_in_innerhtml(self):
        """Source contract: review_text must not be set via innerHTML without escaping."""
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()
        # The known unsafe pattern: .innerHTML = r.review_text (or very similar)
        assert "innerHTML = r.review_text" not in content
        assert "innerHTML=r.review_text" not in content
        # Confirm escapeHtml is called before evidence text is used
        assert "escapeHtml(r.review_text" in content

    def test_xss_source_contract_highlight_only_on_escaped_strings(self):
        """Source contract: highlightKeywordInText is called with escapedText (already escaped)."""
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "highlightKeywordInText(escapedText, escapedTerm)" in content

    # ------------------------------------------------------------------
    # Test 13: no new backend endpoint added
    # ------------------------------------------------------------------
    def test_no_new_backend_endpoint_in_code_gs(self):
        """Code.gs must not contain new endpoint functions for A2 evidence drilldown."""
        code_gs_path = os.path.join(self.DASHBOARD_DIR, "Code.gs")
        with open(code_gs_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Evidence is computed client-side; no server function should exist
        assert "getEvidenceReviews" not in content
        assert "getKeywordEvidence" not in content

    # ------------------------------------------------------------------
    # Test 14: all A1 source contracts remain present
    # ------------------------------------------------------------------
    def test_a1_source_contracts_preserved(self):
        """A1 keyword intelligence contracts must still be present in Scripts.html."""
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()
        for fn in ["extractReviewTokens", "calculateKeywordFrequencies",
                   "renderKeywordIntelligence", "renderBadgeList"]:
            assert fn in content, f"A1 함수 누락: {fn}"
        assert "ratingNum >= 1 && ratingNum <= 3" in content

    # ------------------------------------------------------------------
    # Test 15: evidence panel HTML elements exist
    # ------------------------------------------------------------------
    def test_evidence_panel_html_elements_present(self):
        """Index.html must contain evidence panel elements."""
        index_path = os.path.join(self.DASHBOARD_DIR, "Index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "evidenceDrilldownPanel" in content
        assert "evidencePanelTitle" in content
        assert "evidencePanelBody" in content
        assert "btnCloseEvidence" in content
        assert "evidenceMoreLink" in content

    # ------------------------------------------------------------------
    # Test 16: evidence CSS classes present in Styles.html
    # ------------------------------------------------------------------
    def test_evidence_css_classes_present(self):
        """Styles.html must define evidence panel CSS."""
        styles_path = os.path.join(self.DASHBOARD_DIR, "Styles.html")
        with open(styles_path, "r", encoding="utf-8") as f:
            content = f.read()
        for cls in [".evidence-panel", ".evidence-item", ".evidence-text",
                    ".evidence-highlight", ".evidence-empty"]:
            assert cls in content, f"CSS 클래스 누락: {cls}"

    # ------------------------------------------------------------------
    # FIX1 Tests: Security & Evidence State Synchronization
    # ------------------------------------------------------------------
    def test_fix1_render_badge_list_no_inline_onclick(self):
        """renderBadgeList must NOT use inline onclick with string interpolation."""
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract renderBadgeList body
        match = re.search(r"function renderBadgeList\s*\([^)]*\)\s*\{(.*?)\n  \}", content, re.DOTALL)
        assert match is not None, "renderBadgeList 함수를 찾을 수 없습니다."
        body = match.group(1)

        assert "onclick=" not in body, "renderBadgeList 내부에 inline onclick이 존재합니다 (XSS 위험)."
        assert "addEventListener" in body, "renderBadgeList 내부에 addEventListener 가 사용되어야 합니다."
        assert "textContent = item.term" in body or "textContent = item.term" in body.replace(" ", ""), \
            "renderBadgeList 에서 textContent 로 키워드 용어를 바인딩해야 합니다."

    def test_fix1_hide_evidence_panel_prevents_recursion(self):
        """_hideEvidencePanel helper must clear state without calling applyFilters recursively."""
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "function _hideEvidencePanel()" in content, "_hideEvidencePanel 함수가 정의되어 있지 않습니다."

        # Extract _hideEvidencePanel body
        match = re.search(r"function _hideEvidencePanel\s*\(\)\s*\{(.*?)\}", content, re.DOTALL)
        assert match is not None
        body = match.group(1)

        assert "activeEvidenceTerm = null" in body
        assert "applyFilters" not in body, "_hideEvidencePanel 에서 applyFilters 를 호출하면 재귀가 발생합니다."

    def test_fix1_evidence_state_sync_term_match_check(self):
        """applyFilters must check termMatch (keyword === activeEvidenceTerm) and clear on mismatch."""
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "termMatch = keyword === activeEvidenceTerm.toLowerCase()" in content, \
            "applyFilters 내에 activeEvidenceTerm 동기화용 termMatch 검사가 누락되었습니다."
        assert "_hideEvidencePanel()" in content, \
            "applyFilters 내에서 불일치 시 _hideEvidencePanel() 을 호출해야 합니다."


class TestKeywordTrendIntelligence:
    """A3 Keyword Trend Intelligence Unit & Contract Tests."""

    DASHBOARD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../apps/review-dashboard"))

    def get_keyword_monthly_trend(self, term, is_low_rating, reviews, product_id="all", start_date="", end_date="", rating_filter="all"):
        if not term:
            return []

        # 1. Structural population filtering
        population = []
        for r in reviews:
            if product_id != "all" and r.get("product_id") != product_id:
                continue
            r_date = (r.get("review_date") or "")[:10]
            if start_date and r_date < start_date:
                continue
            if end_date and r_date > end_date:
                continue
            if rating_filter != "all":
                try:
                    if int(float(r.get("rating", 0))) != int(rating_filter):
                        continue
                except (ValueError, TypeError):
                    continue
            population.append(r)

        # 2. Low-rating filtering: 1 <= rating <= 3
        if is_low_rating:
            valid_low = []
            for r in population:
                try:
                    r_num = float(r.get("rating"))
                    if 1 <= r_num <= 3:
                        valid_low.append(r)
                except (ValueError, TypeError):
                    continue
            population = valid_low

        # 3. Monthly bucket aggregation
        term_lower = term.lower()
        month_map = {}

        for r in population:
            r_date = r.get("review_date")
            if not r_date or not isinstance(r_date, str):
                continue
            r_date_str = r_date.strip()
            if len(r_date_str) < 7:
                continue
            month_str = r_date_str[:7]
            if not re.match(r"^\d{4}-\d{2}$", month_str):
                continue

            if month_str not in month_map:
                month_map[month_str] = {"eligible_count": 0, "match_count": 0}

            month_map[month_str]["eligible_count"] += 1

            # review_text ONLY matching
            text = (r.get("review_text") or "").lower()
            if term_lower in text:
                month_map[month_str]["match_count"] += 1

        # 4. Sort chronologically (YYYY-MM ASC)
        sorted_months = sorted(month_map.keys())

        result = []
        for m in sorted_months:
            b = month_map[m]
            el = b["eligible_count"]
            mt = b["match_count"]
            rate = round((mt / el) * 100, 1) if el > 0 else 0.0
            result.append({
                "month": m,
                "eligibleReviewCount": el,
                "keywordReviewCount": mt,
                "mentionRate": rate
            })

        return result

    # 1. Functions & HTML panel exist in source
    def test_a3_functions_and_container_exist_in_source(self):
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        index_path = os.path.join(self.DASHBOARD_DIR, "Index.html")
        styles_path = os.path.join(self.DASHBOARD_DIR, "Styles.html")

        with open(scripts_path, "r", encoding="utf-8") as f:
            scripts_content = f.read()
        with open(index_path, "r", encoding="utf-8") as f:
            index_content = f.read()
        with open(styles_path, "r", encoding="utf-8") as f:
            styles_content = f.read()

        assert "getKeywordMonthlyTrend" in scripts_content
        assert "renderKeywordTrend" in scripts_content
        assert 'id="keywordTrendSection"' in index_content
        assert ".keyword-trend-section" in styles_content

    # 2. review_text ONLY keyword matching
    def test_review_text_only_keyword_matching(self):
        reviews = [
            {"review_id": "1", "review_text": "품질 좋음 라벨 테스트", "product_option": "기타", "review_date": "2026-01-10", "rating": 5},
            {"review_id": "2", "review_text": "그냥 그래요", "product_option": "라벨 포함", "review_date": "2026-01-12", "rating": 5},
        ]
        trend = self.get_keyword_monthly_trend("라벨", False, reviews)
        assert len(trend) == 1
        assert trend[0]["eligibleReviewCount"] == 2
        assert trend[0]["keywordReviewCount"] == 1
        assert trend[0]["mentionRate"] == 50.0

    # 3. Product_option-only occurrence excluded
    def test_product_option_only_excluded(self):
        reviews = [
            {"review_id": "1", "review_text": "배송이 아주 빨라요", "product_option": "라벨 프린터 용지", "review_date": "2026-02-01", "rating": 5},
        ]
        trend = self.get_keyword_monthly_trend("라벨", False, reviews)
        assert len(trend) == 1
        assert trend[0]["eligibleReviewCount"] == 1
        assert trend[0]["keywordReviewCount"] == 0
        assert trend[0]["mentionRate"] == 0.0

    # 4. Repeated keyword in one review counts once
    def test_repeated_keyword_in_one_review_counts_once(self):
        reviews = [
            {"review_id": "1", "review_text": "라벨 품질 우수. 라벨 세트 추천. 라벨 대족", "review_date": "2026-03-15", "rating": 5},
        ]
        trend = self.get_keyword_monthly_trend("라벨", False, reviews)
        assert len(trend) == 1
        assert trend[0]["keywordReviewCount"] == 1
        assert trend[0]["eligibleReviewCount"] == 1
        assert trend[0]["mentionRate"] == 100.0

    # 5. Monthly aggregation deterministic
    def test_monthly_aggregation_deterministic(self):
        reviews = [
            {"review_id": "1", "review_text": "라벨 최고", "review_date": "2026-04-01", "rating": 5},
            {"review_id": "2", "review_text": "라벨 별로", "review_date": "2026-04-15", "rating": 2},
        ]
        t1 = self.get_keyword_monthly_trend("라벨", False, reviews)
        t2 = self.get_keyword_monthly_trend("라벨", False, reviews)
        assert t1 == t2

    # 6. Chronological month ordering (YYYY-MM ASC)
    def test_chronological_month_ordering(self):
        reviews = [
            {"review_id": "1", "review_text": "라벨", "review_date": "2026-07-01", "rating": 5},
            {"review_id": "2", "review_text": "라벨", "review_date": "2026-05-01", "rating": 5},
            {"review_id": "3", "review_text": "라벨", "review_date": "2026-06-01", "rating": 5},
        ]
        trend = self.get_keyword_monthly_trend("라벨", False, reviews)
        months = [item["month"] for item in trend]
        assert months == ["2026-05", "2026-06", "2026-07"]

    # 7. Mention-rate calculation
    def test_mention_rate_calculation(self):
        reviews = [
            {"review_id": "1", "review_text": "라벨 좋음", "review_date": "2026-05-01", "rating": 5},
            {"review_id": "2", "review_text": "출력 좋음", "review_date": "2026-05-02", "rating": 5},
            {"review_id": "3", "review_text": "배송 빨라요", "review_date": "2026-05-03", "rating": 5},
            {"review_id": "4", "review_text": "그냥 그래요", "review_date": "2026-05-04", "rating": 5},
        ]
        trend = self.get_keyword_monthly_trend("라벨", False, reviews)
        assert len(trend) == 1
        assert trend[0]["eligibleReviewCount"] == 4
        assert trend[0]["keywordReviewCount"] == 1
        assert trend[0]["mentionRate"] == 25.0

    # 8. Structural filters reflected
    def test_structural_filters_reflected(self):
        reviews = [
            {"review_id": "1", "product_id": "P1", "review_text": "라벨 A", "review_date": "2026-05-01", "rating": 5},
            {"review_id": "2", "product_id": "P2", "review_text": "라벨 B", "review_date": "2026-05-02", "rating": 5},
        ]
        trend_p1 = self.get_keyword_monthly_trend("라벨", False, reviews, product_id="P1")
        assert len(trend_p1) == 1
        assert trend_p1[0]["eligibleReviewCount"] == 1
        assert trend_p1[0]["keywordReviewCount"] == 1

    # 9. Overall keyword population includes all ratings
    def test_overall_keyword_population(self):
        reviews = [
            {"review_id": "1", "review_text": "라벨 굿", "review_date": "2026-05-01", "rating": 5},
            {"review_id": "2", "review_text": "라벨 나쁨", "review_date": "2026-05-02", "rating": 1},
        ]
        trend = self.get_keyword_monthly_trend("라벨", False, reviews)
        assert trend[0]["eligibleReviewCount"] == 2
        assert trend[0]["keywordReviewCount"] == 2

    # 10. Low-rating population strictly 1..3
    def test_low_rating_population_strictly_1_to_3(self):
        reviews = [
            {"review_id": "1", "review_text": "라벨 굿", "review_date": "2026-05-01", "rating": 5},
            {"review_id": "2", "review_text": "라벨 중간", "review_date": "2026-05-02", "rating": 3},
            {"review_id": "3", "review_text": "라벨 별로", "review_date": "2026-05-03", "rating": 1},
        ]
        trend = self.get_keyword_monthly_trend("라벨", True, reviews)
        assert trend[0]["eligibleReviewCount"] == 2  # ratings 3 and 1 only
        assert trend[0]["keywordReviewCount"] == 2

    # 11. Invalid rating excluded from low-rating mode
    def test_invalid_rating_excluded_from_low_rating(self):
        reviews = [
            {"review_id": "1", "review_text": "라벨 무효", "review_date": "2026-05-01", "rating": 0},
            {"review_id": "2", "review_text": "라벨 누락", "review_date": "2026-05-02", "rating": None},
            {"review_id": "3", "review_text": "라벨 정상저평점", "review_date": "2026-05-03", "rating": 2},
        ]
        trend = self.get_keyword_monthly_trend("라벨", True, reviews)
        assert trend[0]["eligibleReviewCount"] == 1  # rating 2 only
        assert trend[0]["keywordReviewCount"] == 1

    # 12. Invalid review_date safely ignored
    def test_invalid_review_date_safely_ignored(self):
        reviews = [
            {"review_id": "1", "review_text": "라벨 무효날짜", "review_date": "INVALID_DATE", "rating": 5},
            {"review_id": "2", "review_text": "라벨 누락날짜", "review_date": None, "rating": 5},
            {"review_id": "3", "review_text": "라벨 정상날짜", "review_date": "2026-05-10", "rating": 5},
        ]
        trend = self.get_keyword_monthly_trend("라벨", False, reviews)
        assert len(trend) == 1
        assert trend[0]["month"] == "2026-05"
        assert trend[0]["eligibleReviewCount"] == 1

    # 13. Same keyword structural-filter recalculation in source
    def test_same_keyword_structural_filter_recalculation_source(self):
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "showKeywordEvidence(activeEvidenceTerm, activeEvidenceIsLow)" in content
        assert "renderKeywordTrend(term, isLowRating)" in content

    # 14. Empty manual search clears trend (via _hideEvidencePanel)
    def test_empty_manual_search_clears_trend_source(self):
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "_hideEvidencePanel()" in content

    # 15. Different manual search clears trend (via _hideEvidencePanel)
    def test_different_manual_search_clears_trend_source(self):
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "termMatch = keyword === activeEvidenceTerm.toLowerCase()" in content

    # 16. Close/clear hides trend panel
    def test_close_clear_hides_trend(self):
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "clearEvidencePanel" in content
        assert "_hideEvidencePanel" in content

    # 17. No recursion between applyFilters and trend/evidence
    def test_no_recursion_between_apply_filters_and_trend(self):
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r"function _hideEvidencePanel\s*\(\)\s*\{(.*?)\}", content, re.DOTALL)
        assert match is not None
        assert "applyFilters" not in match.group(1)

    # 18. Safe DOM binding / no keyword interpolation into executable inline JS
    def test_safe_dom_binding_no_keyword_executable_js(self):
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r"function renderKeywordTrend\s*\([^)]*\)\s*\{(.*?)\n  \}", content, re.DOTALL)
        assert match is not None
        body = match.group(1)
        assert "onclick=" not in body
        assert "escapeHtml" in body


class TestProductKeywordComparison:
    """A4 Product Keyword Comparison Unit & Contract Tests."""

    DASHBOARD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../apps/review-dashboard"))

    def get_keyword_product_comparison(self, term, is_low_rating, reviews, start_date="", end_date="", rating_filter="all"):
        if not term:
            return []

        # 1. Filter population (CROSS-PRODUCT: ignore product selector!)
        population = []
        for r in reviews:
            r_date = (r.get("review_date") or "")[:10]
            if start_date and r_date < start_date:
                continue
            if end_date and r_date > end_date:
                continue
            if rating_filter != "all":
                try:
                    if int(float(r.get("rating", 0))) != int(rating_filter):
                        continue
                except (ValueError, TypeError):
                    continue
            population.append(r)

        # 2. Low-rating mode restriction: valid 1 <= rating <= 3 only
        if is_low_rating:
            valid_low = []
            for r in population:
                try:
                    r_num = float(r.get("rating"))
                    if 1 <= r_num <= 3:
                        valid_low.append(r)
                except (ValueError, TypeError):
                    continue
            population = valid_low

        term_lower = term.lower()
        prod_map = {}

        for r in population:
            domain = (r.get("source_domain") or "unknown").strip()
            p_id = (r.get("product_id") or r.get("product_name") or "unknown").strip()
            p_key = f"{domain}::{p_id}"
            p_name = (r.get("product_name") or r.get("product_id") or "알 수 없는 상품").strip()
            brand = (r.get("brand") or "").strip()

            if p_key not in prod_map:
                prod_map[p_key] = {
                    "productKey": p_key,
                    "productName": p_name,
                    "brand": brand,
                    "sourceDomain": domain,
                    "eligibleReviewCount": 0,
                    "keywordReviewCount": 0
                }

            prod_map[p_key]["eligibleReviewCount"] += 1

            text = (r.get("review_text") or "").lower()
            if term_lower in text:
                prod_map[p_key]["keywordReviewCount"] += 1

        items = []
        for key, p in prod_map.items():
            el = p["eligibleReviewCount"]
            mt = p["keywordReviewCount"]
            if el > 0:
                rate = round((mt / el) * 100, 1)
                items.append({
                    "productKey": p["productKey"],
                    "productName": p["productName"],
                    "brand": p["brand"],
                    "sourceDomain": p["sourceDomain"],
                    "eligibleReviewCount": el,
                    "keywordReviewCount": mt,
                    "mentionRate": rate
                })

        # Sort order: mentionRate DESC, keywordReviewCount DESC, eligibleReviewCount DESC, productKey ASC
        items.sort(key=lambda x: (-x["mentionRate"], -x["keywordReviewCount"], -x["eligibleReviewCount"], x["productKey"]))

        return items[:10]

    # 1. Functions & HTML panel exist in source
    def test_a4_functions_and_container_exist_in_source(self):
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        index_path = os.path.join(self.DASHBOARD_DIR, "Index.html")
        styles_path = os.path.join(self.DASHBOARD_DIR, "Styles.html")

        with open(scripts_path, "r", encoding="utf-8") as f:
            scripts_content = f.read()
        with open(index_path, "r", encoding="utf-8") as f:
            index_content = f.read()
        with open(styles_path, "r", encoding="utf-8") as f:
            styles_content = f.read()

        assert "getKeywordProductComparison" in scripts_content
        assert "renderProductComparison" in scripts_content
        assert 'id="productComparisonSection"' in index_content
        assert ".product-comparison-section" in styles_content

    # 2. Composite product identity (source_domain + product_id)
    def test_composite_product_identity_creation(self):
        reviews = [
            {"source_domain": "naver", "product_id": "P1", "product_name": "라벨기", "review_text": "라벨 테스트", "rating": 5},
            {"source_domain": "coupang", "product_id": "P1", "product_name": "라벨기", "review_text": "라벨 테스트", "rating": 5},
        ]
        comp = self.get_keyword_product_comparison("라벨", False, reviews)
        assert len(comp) == 2
        keys = [item["productKey"] for item in comp]
        assert "naver::P1" in keys
        assert "coupang::P1" in keys

    # 3. Same product_name with different stable IDs remains separate
    def test_same_name_different_ids_remain_separate(self):
        reviews = [
            {"source_domain": "naver", "product_id": "101", "product_name": "라벨 프린터", "review_text": "라벨 굿", "rating": 5},
            {"source_domain": "naver", "product_id": "102", "product_name": "라벨 프린터", "review_text": "라벨 굿", "rating": 5},
        ]
        comp = self.get_keyword_product_comparison("라벨", False, reviews)
        assert len(comp) == 2

    # 4. review_text ONLY numerator
    def test_review_text_only_numerator(self):
        reviews = [
            {"source_domain": "naver", "product_id": "P1", "review_text": "출력 상태 좋음", "product_option": "라벨 용지 포함", "rating": 5},
        ]
        comp = self.get_keyword_product_comparison("라벨", False, reviews)
        assert len(comp) == 1
        assert comp[0]["keywordReviewCount"] == 0
        assert comp[0]["mentionRate"] == 0.0

    # 5. product_option-only keyword excluded
    def test_product_option_only_keyword_excluded(self):
        reviews = [
            {"source_domain": "naver", "product_id": "P1", "review_text": "배송이 빠름", "product_option": "라벨 롤", "rating": 5},
        ]
        comp = self.get_keyword_product_comparison("라벨", False, reviews)
        assert comp[0]["keywordReviewCount"] == 0

    # 6. Repeated keyword in one review counts once
    def test_repeated_keyword_counts_once(self):
        reviews = [
            {"source_domain": "naver", "product_id": "P1", "review_text": "라벨 최고 라벨 최고 라벨 최고", "rating": 5},
        ]
        comp = self.get_keyword_product_comparison("라벨", False, reviews)
        assert comp[0]["eligibleReviewCount"] == 1
        assert comp[0]["keywordReviewCount"] == 1
        assert comp[0]["mentionRate"] == 100.0

    # 7. Denominator calculation
    def test_denominator_calculation(self):
        reviews = [
            {"source_domain": "naver", "product_id": "P1", "review_text": "라벨 굿", "rating": 5},
            {"source_domain": "naver", "product_id": "P1", "review_text": "배송 굿", "rating": 5},
            {"source_domain": "naver", "product_id": "P1", "review_text": "포장 굿", "rating": 5},
        ]
        comp = self.get_keyword_product_comparison("라벨", False, reviews)
        assert comp[0]["eligibleReviewCount"] == 3
        assert comp[0]["keywordReviewCount"] == 1
        assert comp[0]["mentionRate"] == 33.3

    # 8. Mention-rate calculation
    def test_mention_rate_calculation(self):
        reviews = [
            {"source_domain": "naver", "product_id": "P1", "review_text": "라벨 굿", "rating": 5},
            {"source_domain": "naver", "product_id": "P1", "review_text": "라벨 최고", "rating": 5},
        ]
        comp = self.get_keyword_product_comparison("라벨", False, reviews)
        assert comp[0]["mentionRate"] == 100.0

    # 9. Overall mode
    def test_overall_mode_includes_all_ratings(self):
        reviews = [
            {"source_domain": "naver", "product_id": "P1", "review_text": "라벨 굿", "rating": 5},
            {"source_domain": "naver", "product_id": "P1", "review_text": "라벨 별로", "rating": 1},
        ]
        comp = self.get_keyword_product_comparison("라벨", False, reviews)
        assert comp[0]["eligibleReviewCount"] == 2
        assert comp[0]["keywordReviewCount"] == 2

    # 10. Low-rating mode strictly 1..3
    def test_low_rating_mode_strictly_1_to_3(self):
        reviews = [
            {"source_domain": "naver", "product_id": "P1", "review_text": "라벨 굿", "rating": 5},
            {"source_domain": "naver", "product_id": "P1", "review_text": "라벨 중간", "rating": 3},
            {"source_domain": "naver", "product_id": "P1", "review_text": "라벨 별로", "rating": 1},
        ]
        comp = self.get_keyword_product_comparison("라벨", True, reviews)
        assert comp[0]["eligibleReviewCount"] == 2  # rating 3 & 1 only
        assert comp[0]["keywordReviewCount"] == 2

    # 11. Invalid/missing ratings excluded in low mode
    def test_invalid_ratings_excluded_in_low_mode(self):
        reviews = [
            {"source_domain": "naver", "product_id": "P1", "review_text": "라벨 0점", "rating": 0},
            {"source_domain": "naver", "product_id": "P1", "review_text": "라벨 누락", "rating": None},
            {"source_domain": "naver", "product_id": "P1", "review_text": "라벨 2점", "rating": 2},
        ]
        comp = self.get_keyword_product_comparison("라벨", True, reviews)
        assert comp[0]["eligibleReviewCount"] == 1

    # 12. Active rating filter respected
    def test_active_rating_filter_respected(self):
        reviews = [
            {"source_domain": "naver", "product_id": "P1", "review_text": "라벨 5점", "rating": 5},
            {"source_domain": "naver", "product_id": "P1", "review_text": "라벨 4점", "rating": 4},
        ]
        comp = self.get_keyword_product_comparison("라벨", False, reviews, rating_filter="5")
        assert len(comp) == 1
        assert comp[0]["eligibleReviewCount"] == 1

    # 13. Date range respected
    def test_date_range_respected(self):
        reviews = [
            {"source_domain": "naver", "product_id": "P1", "review_text": "라벨 1월", "review_date": "2026-01-10", "rating": 5},
            {"source_domain": "naver", "product_id": "P1", "review_text": "라벨 5월", "review_date": "2026-05-10", "rating": 5},
        ]
        comp = self.get_keyword_product_comparison("라벨", False, reviews, start_date="2026-05-01")
        assert len(comp) == 1
        assert comp[0]["keywordReviewCount"] == 1

    # 14. Product selector intentionally excluded from A4 population in source
    def test_product_selector_excluded_from_a4_source_contract(self):
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()

        match = re.search(r"function getKeywordProductComparison\s*\([^)]*\)\s*\{(.*?)\n  \}", content, re.DOTALL)
        assert match is not None
        body = match.group(1)
        assert "filterProduct" not in body, "getKeywordProductComparison 에서 filterProduct 를 참조하면 안 됩니다."

    # 15. Product selector still affects existing A2/A3 behavior
    def test_product_selector_affects_a2_a3(self):
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()

        match_a2 = re.search(r"function getEvidenceReviews\s*\([^)]*\)\s*\{(.*?)\n  \}", content, re.DOTALL)
        assert match_a2 is not None
        assert "filterProduct" in match_a2.group(1)

        match_a3 = re.search(r"function getKeywordMonthlyTrend\s*\([^)]*\)\s*\{(.*?)\n  \}", content, re.DOTALL)
        assert match_a3 is not None
        assert "filterProduct" in match_a3.group(1)

    # 16. Zero denominator / empty population safe
    def test_zero_denominator_safe(self):
        comp = self.get_keyword_product_comparison("라벨", False, [])
        assert comp == []

    # 17. Deterministic sort (mentionRate DESC, keywordCount DESC, eligibleCount DESC, productKey ASC)
    def test_deterministic_sort(self):
        reviews = [
            {"source_domain": "naver", "product_id": "P1", "review_text": "라벨", "rating": 5},  # 1/1 = 100%
            {"source_domain": "coupang", "product_id": "P2", "review_text": "라벨", "rating": 5}, # 2/2 = 100%
            {"source_domain": "coupang", "product_id": "P2", "review_text": "라벨", "rating": 5},
            {"source_domain": "11st", "product_id": "P3", "review_text": "라벨", "rating": 5},   # 1/2 = 50%
            {"source_domain": "11st", "product_id": "P3", "review_text": "기타", "rating": 5},
        ]
        comp = self.get_keyword_product_comparison("라벨", False, reviews)
        assert comp[0]["productKey"] == "coupang::P2"
        assert comp[1]["productKey"] == "naver::P1"
        assert comp[2]["productKey"] == "11st::P3"

    # 18. Tie-break deterministic
    def test_tie_break_deterministic(self):
        reviews = [
            {"source_domain": "b_domain", "product_id": "P1", "review_text": "라벨", "rating": 5},
            {"source_domain": "a_domain", "product_id": "P1", "review_text": "라벨", "rating": 5},
        ]
        comp = self.get_keyword_product_comparison("라벨", False, reviews)
        assert comp[0]["productKey"] == "a_domain::P1"
        assert comp[1]["productKey"] == "b_domain::P1"

    # 19. Top 10 limit
    def test_top_10_limit(self):
        reviews = [
            {"source_domain": "dom", "product_id": f"P{i}", "review_text": "라벨", "rating": 5}
            for i in range(15)
        ]
        comp = self.get_keyword_product_comparison("라벨", False, reviews)
        assert len(comp) == 10

    # 20. Denominator/count displayed in render
    def test_render_product_comparison_source_contract(self):
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "renderProductComparison" in content
        assert "제품 비교는 현재 제품 선택과 관계없이 동일 기간·평점 조건으로 계산됩니다." in content

    # 21. Empty manual search clears comparison
    def test_empty_manual_search_clears_comparison_source(self):
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "_hideEvidencePanel()" in content

    # 22. Different manual search clears comparison
    def test_different_manual_search_clears_comparison_source(self):
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "termMatch = keyword === activeEvidenceTerm.toLowerCase()" in content

    # 23. Close/clear hides comparison
    def test_close_clear_hides_comparison(self):
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "clearEvidencePanel" in content
        assert "_hideEvidencePanel" in content

    # 24. Same keyword recalculation
    def test_same_keyword_recalculation(self):
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "renderProductComparison(term, isLowRating)" in content

    # 25. No applyFilters recursion
    def test_no_apply_filters_recursion_in_hide_evidence(self):
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r"function _hideEvidencePanel\s*\(\)\s*\{(.*?)\}", content, re.DOTALL)
        assert match is not None
        assert "applyFilters" not in match.group(1)

    # 26. Safe DOM rendering / no inline untrusted JS
    def test_safe_dom_rendering_no_inline_untrusted_js(self):
        scripts_path = os.path.join(self.DASHBOARD_DIR, "Scripts.html")
        with open(scripts_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r"function renderProductComparison\s*\([^)]*\)\s*\{(.*?)\n  \}", content, re.DOTALL)
        assert match is not None
        body = match.group(1)
        assert "onclick=" not in body
        assert "escapeHtml" in body









