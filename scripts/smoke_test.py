"""Scrapling Python 3.14 호환성 스모크 테스트"""
import sys
print(f"Python {sys.version}")

# 1. Fetcher (기본 HTTP)
from scrapling.fetchers import Fetcher
page = Fetcher().get("https://httpbin.org/html")
assert page.status == 200
title = page.css("h1::text").get()
assert title is not None
print(f"[PASS] Fetcher: title='{title}'")

# 2. StealthyFetcher (안티봇)
from scrapling.fetchers import StealthyFetcher
page = StealthyFetcher().fetch("https://httpbin.org/html")
assert page.status == 200
print(f"[PASS] StealthyFetcher: status={page.status}")

# 3. DynamicFetcher (브라우저 렌더링)
from scrapling.fetchers import DynamicFetcher
page = DynamicFetcher().fetch("https://httpbin.org/html")
assert page.status == 200
print(f"[PASS] DynamicFetcher: status={page.status}")

# 4. auto_save / adaptive 기본 동작
from scrapling.parser import Adaptor
html = "<div class='item'><h2>Product</h2><span class='price'>$10</span></div>"
adaptor = Adaptor(html, url="https://test.com", auto_save=True,
                  storage_args={"storage_file": "./fingerprints/elements_storage.db"})
items = adaptor.css(".item h2")
assert len(items) > 0
print(f"[PASS] Adaptor auto_save: found {len(items)} items")

# 5. Spider import (실행은 Phase 4)
from scrapling.spiders import Spider, Request, Response
print("[PASS] Spider import successful")

print("\n=== ALL SMOKE TESTS PASSED ===")
