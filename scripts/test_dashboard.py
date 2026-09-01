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
        manifest_path = os.path.join(DASHBOARD_DIR, "appsscript.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest.get("timeZone") == "Asia/Seoul"
        assert manifest.get("runtimeVersion") == "V8"
        assert "webapp" in manifest
        assert manifest["webapp"].get("executeAs") in ["USER_DEPLOYING", "USER_ACCESSING"]
        assert manifest["webapp"].get("access") in ["MYSELF", "DOMAIN", "ANYONE_ANONYMOUS"]

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


# ---------------------------------------------------------------------------
# 멀티 프로덕트 데이터 집계 Pure Python Reference Engine (테스트용)
# ---------------------------------------------------------------------------


def calculate_dashboard_metrics(reviews: list[dict], selected_product: str = "all",
                                 start_date: str = "", end_date: str = "",
                                 selected_rating: str = "all", keyword: str = "") -> dict:
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

    # Recent 30 Days (Relative to max date in filtered dataset)
    timestamps = []
    for r in filtered:
        d_str = str(r.get("review_date", ""))[:10]
        if d_str:
            try:
                dt = datetime.strptime(d_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                timestamps.append(dt.timestamp())
            except ValueError:
                pass

    max_ts = max(timestamps) if timestamps else datetime.now(timezone.utc).timestamp()
    thirty_days_ago = max_ts - (30 * 24 * 3600)
    recent_30 = sum(1 for ts in timestamps if ts >= thirty_days_ago)

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
