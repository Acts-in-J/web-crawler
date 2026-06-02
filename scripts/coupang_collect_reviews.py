"""쿠팡 리뷰 전체 수집 - Playwright CDP 연결 (title + content 포함)"""
import json
import os
import sys
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

sys.path.insert(0, './scripts')
from utils import RateLimiter, setup_logger
from export_excel import export_to_excel

logger = setup_logger("coupang_reviews")

PRODUCT_ID = "5690564126"
TOTAL_REVIEWS = 1342
SIZE_PER_PAGE = 10
TOTAL_PAGES = (TOTAL_REVIEWS + SIZE_PER_PAGE - 1) // SIZE_PER_PAGE

DOMAIN = "coupang.com"
TOPIC = "미샤시트마스크_상품평"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = f"./output/{DOMAIN}/{TOPIC}_{TIMESTAMP}"
os.makedirs(OUTPUT_DIR, exist_ok=True)

RAW_DATA_PATH = os.path.join(OUTPUT_DIR, "raw_data.json")
EXCEL_PATH = os.path.join(OUTPUT_DIR, "crawl_result.xlsx")
PROGRESS_PATH = os.path.join(OUTPUT_DIR, "progress.json")

limiter = RateLimiter(delay=1.5)


def save_progress(collected, errors, status="running"):
    with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
        json.dump({"collected": collected, "total_estimate": TOTAL_REVIEWS,
                    "errors": errors, "status": status}, f)


def main():
    all_reviews = []
    error_count = 0
    consecutive_errors = 0

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0]

        logger.info(f"수집 시작: 총 {TOTAL_REVIEWS}건, {TOTAL_PAGES}페이지")
        start_time = time.time()

        for page_num in range(1, TOTAL_PAGES + 1):
            limiter.wait()

            try:
                result = page.evaluate(f"""
                    () => {{
                        var xhr = new XMLHttpRequest();
                        xhr.open('GET', '/next-api/review?productId={PRODUCT_ID}&page={page_num}&size={SIZE_PER_PAGE}&sortBy=ORDER_SCORE_ASC&ratingSummary=false&ratings=&market=', false);
                        xhr.setRequestHeader('Accept', 'application/json, text/plain, */*');
                        xhr.send();
                        return {{status: xhr.status, body: xhr.responseText}};
                    }}
                """)
            except Exception as e:
                error_count += 1
                consecutive_errors += 1
                logger.warning(f"  페이지 {page_num} 에러: {e}")
                if consecutive_errors >= 3:
                    break
                time.sleep(3)
                continue

            if result["status"] != 200:
                error_count += 1
                consecutive_errors += 1
                if consecutive_errors >= 3:
                    break
                time.sleep(3)
                continue

            try:
                resp = json.loads(result["body"])
            except json.JSONDecodeError:
                error_count += 1
                consecutive_errors += 1
                continue

            if resp.get("rCode") != "RET0000":
                error_count += 1
                consecutive_errors += 1
                continue

            consecutive_errors = 0
            contents = resp.get("rData", {}).get("paging", {}).get("contents", [])

            if not contents:
                break

            for review in contents:
                review_at = review.get("reviewAt")
                date_str = datetime.fromtimestamp(review_at / 1000).strftime("%Y-%m-%d") if review_at else ""

                title = (review.get("title") or "").strip()
                content = (review.get("content") or "").replace("\\n", "\n").strip()

                # title과 content 합치기
                if title and content:
                    review_text = f"[{title}] {content}"
                elif title:
                    review_text = title
                else:
                    review_text = content

                all_reviews.append({
                    "상품명": review.get("itemName", ""),
                    "작성자": review.get("member", {}).get("name", review.get("displayName", "")),
                    "리뷰 텍스트": review_text,
                    "별점": review.get("rating", ""),
                    "작성 날짜": date_str,
                })

            collected = len(all_reviews)
            if page_num % 10 == 0 or page_num == TOTAL_PAGES:
                elapsed = time.time() - start_time
                logger.info(f"  [{page_num}/{TOTAL_PAGES}] {collected}건 ({elapsed:.0f}초)")

            if collected % 50 < SIZE_PER_PAGE:
                with open(RAW_DATA_PATH, "w", encoding="utf-8") as f:
                    json.dump(all_reviews, f, ensure_ascii=False, indent=2)
                save_progress(collected, error_count)

        browser.close()

    elapsed = time.time() - start_time

    with open(RAW_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(all_reviews, f, ensure_ascii=False, indent=2)
    save_progress(len(all_reviews), error_count, "completed")

    if all_reviews:
        export_to_excel(all_reviews, EXCEL_PATH)

    # 통계
    has_text = sum(1 for r in all_reviews if r["리뷰 텍스트"])
    no_text = sum(1 for r in all_reviews if not r["리뷰 텍스트"])

    logger.info(f"\n=== 수집 완료 ===")
    logger.info(f"  수집: {len(all_reviews)}/{TOTAL_REVIEWS}건")
    logger.info(f"  텍스트 있음: {has_text}건, 별점만: {no_text}건")
    logger.info(f"  에러: {error_count}건")
    logger.info(f"  소요: {int(elapsed//60)}분 {int(elapsed%60)}초")
    logger.info(f"  엑셀: {EXCEL_PATH}")


if __name__ == "__main__":
    main()
