"""k-startup.go.kr 모집중 사업공고 크롤러"""
import json
import os
import re
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from utils import RateLimiter, setup_logger
from export_excel import export_to_excel
from scrapling.fetchers import Fetcher

logger = setup_logger("kstartup")
rate = RateLimiter(delay=1.5)

BASE_URL = "https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do"


def fetch_list_page(page_no: int) -> list[dict]:
    """리스트 페이지에서 공고 기본 정보를 추출."""
    url = f"{BASE_URL}?page={page_no}" if page_no > 1 else BASE_URL
    rate.wait()
    logger.info(f"리스트 페이지 {page_no} 수집중...")

    fetcher = Fetcher()
    resp = fetcher.get(url)

    items = []
    list_el = resp.css("#bizPbancList > ul > li")
    for li in list_el:
        title = li.css(".tit::text").get("").replace("새로운게시글", "").strip()
        if not title or "등록된 데이터가 없습니다" in title:
            continue

        # 상세 링크 ID
        href = li.css("a[href*='go_view']::attr(href)").get("")
        pbanc_sn = ""
        m = re.search(r"go_view\((\d+)\)", href)
        if m:
            pbanc_sn = m.group(1)

        # 지원분야
        flags = li.css(".flag")
        category = ""
        for flag in flags:
            cls = flag.attrib.get("class", "")
            if "day" not in cls and "flag_agency" not in cls:
                category = flag.css("::text").get("").strip()
                break

        # 하단 정보
        bottom_spans = li.css(".bottom .list")
        info = {}
        for span in bottom_spans:
            parts = span.css("::text").getall()
            text = " ".join(t.strip() for t in parts if t.strip())
            if "시작일자" in text:
                info["start_date"] = text.split("시작일자")[-1].strip()
            elif "마감일자" in text:
                info["end_date"] = text.split("마감일자")[-1].strip()

        detail_url = f"{BASE_URL}?schM=view&pbancSn={pbanc_sn}" if pbanc_sn else ""

        items.append({
            "pbancSn": pbanc_sn,
            "제목": title,
            "상세페이지URL": detail_url,
            "지원분야": category,
            "시작일자": info.get("start_date", ""),
            "마감일자": info.get("end_date", ""),
        })

    return items


def fetch_detail(pbanc_sn: str) -> dict:
    """상세 페이지에서 지역, 접수기간 추출."""
    url = f"{BASE_URL}?schM=view&pbancSn={pbanc_sn}"
    rate.wait()

    fetcher = Fetcher()
    resp = fetcher.get(url)

    fields = {}
    dot_items = resp.css(".dot_list")
    for item in dot_items:
        tit = item.css(".tit::text").get("").strip()
        txt_parts = item.css(".txt::text").getall()
        txt = " ".join(t.strip() for t in txt_parts if t.strip())
        if tit:
            fields[tit] = txt

    return {
        "지역": fields.get("지역", ""),
        "접수기간": fields.get("접수기간", ""),
    }


def get_total_pages(resp) -> int:
    """마지막 페이지 번호를 추출."""
    links = resp.css("a[onclick*='fn_egov_link_page']")
    max_page = 1
    for link in links:
        onclick = link.attrib.get("onclick", "")
        m = re.search(r"fn_egov_link_page\((\d+)\)", onclick)
        if m:
            max_page = max(max_page, int(m.group(1)))
    return max_page


def main():
    now = datetime.now()
    run_id = f"모집중사업공고_{now.strftime('%Y%m%d_%H%M%S')}"
    out_dir = os.path.join(
        os.path.dirname(__file__), "..", "output", "k-startup.go.kr", run_id
    )
    os.makedirs(out_dir, exist_ok=True)

    logger.info("=== K-Startup 모집중 사업공고 크롤링 시작 ===")

    # 1단계: 첫 페이지에서 총 페이지 수 파악
    fetcher = Fetcher()
    resp = fetcher.get(BASE_URL)
    total_pages = get_total_pages(resp)
    logger.info(f"총 {total_pages} 페이지 감지")

    # 2단계: 전체 리스트 수집
    all_items = []
    for page in range(1, total_pages + 1):
        items = fetch_list_page(page)
        all_items.extend(items)
        logger.info(f"페이지 {page}/{total_pages}: {len(items)}건 (누적 {len(all_items)}건)")

    logger.info(f"리스트 수집 완료: 총 {len(all_items)}건")

    # 3단계: 상세 페이지에서 지역, 접수기간 수집
    logger.info("상세 페이지에서 지역/접수기간 수집 시작...")
    for i, item in enumerate(all_items):
        pbanc_sn = item["pbancSn"]
        if not pbanc_sn:
            continue
        try:
            detail = fetch_detail(pbanc_sn)
            item["지역"] = detail["지역"]
            item["접수기간"] = detail["접수기간"]
            logger.info(
                f"  [{i+1}/{len(all_items)}] {item['제목'][:30]}... "
                f"→ 지역: {detail['지역'] or '(없음)'}"
            )
        except Exception as e:
            logger.warning(f"  [{i+1}/{len(all_items)}] 상세 수집 실패 ({pbanc_sn}): {e}")
            item["지역"] = ""
            item["접수기간"] = ""

    # 4단계: 엑셀 출력
    export_data = [
        {
            "이름": item["제목"],
            "상세페이지 URL": item["상세페이지URL"],
            "지원분야": item["지원분야"],
            "지역": item.get("지역", ""),
            "접수기간": item.get("접수기간", ""),
        }
        for item in all_items
    ]

    # raw data 저장
    raw_path = os.path.join(out_dir, "raw_data.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)
    logger.info(f"원시 데이터 저장: {raw_path}")

    # 엑셀 저장
    excel_path = os.path.join(out_dir, "crawl_result.xlsx")
    export_to_excel(export_data, excel_path, sheet_name="모집중 사업공고")
    logger.info(f"엑셀 저장: {excel_path}")

    logger.info(f"=== 완료: {len(export_data)}건 수집 ===")
    return excel_path


if __name__ == "__main__":
    main()
