/**
 * Syncrown Competitor Review Intelligence Dashboard
 * Apps Script Backend Code
 */

const DEFAULT_SPREADSHEET_ID = "1nJpBbys3qlaP28RgvJgdMj7TpyYxJpGgxiT6ofqosjY";
const DEFAULT_SHEET_NAME = "01_REVIEW_RAW";

function doGet(e) {
  const template = HtmlService.createTemplateFromFile("Index");
  return template.evaluate()
    .setTitle("경쟁사 리뷰 인텔리전스 | Syncrown Review Intelligence")
    .addMetaTag("viewport", "width=device-width, initial-scale=1.0");
}

function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}

/**
 * Google Sheet 01_REVIEW_RAW 데이터 조회 및 Object 변환
 *
 * @param {string} [spreadsheetIdOverride]
 * @return {object} { status: "success"|"error", data: Array, count: number, fetchedAt: string }
 */
function getReviewDashboardData(spreadsheetIdOverride) {
  try {
    const targetSpreadsheetId = spreadsheetIdOverride || DEFAULT_SPREADSHEET_ID;
    const ss = SpreadsheetApp.openById(targetSpreadsheetId);
    if (!ss) {
      return {
        status: "error",
        message: "Spreadsheet를 찾을 수 없습니다."
      };
    }

    const sheet = ss.getSheetByName(DEFAULT_SHEET_NAME);
    if (!sheet) {
      return {
        status: "error",
        message: `'${DEFAULT_SHEET_NAME}' 시트를 찾을 수 없습니다.`
      };
    }

    const values = sheet.getDataRange().getValues();
    if (!values || values.length <= 1) {
      return {
        status: "success",
        data: [],
        count: 0,
        fetchedAt: new Date().toISOString()
      };
    }

    const headers = values[0].map(h => String(h).trim().toLowerCase());

    const requiredHeaders = [
      "source_domain",
      "product_id",
      "product_name",
      "brand",
      "review_id",
      "review_date",
      "rating",
      "review_text",
      "product_option",
      "helpful_count",
      "photo_review",
      "video_review",
      "collected_at"
    ];

    const missingHeaders = requiredHeaders.filter(h => headers.indexOf(h) === -1);
    if (missingHeaders.length > 0) {
      Logger.log("Missing required headers in 01_REVIEW_RAW: " + missingHeaders.join(", "));
      return {
        status: "error",
        message: "리뷰 데이터 형식이 올바르지 않습니다. 필요한 컬럼을 확인해 주세요."
      };
    }
    
    // Header name to index mapping
    const colIndex = {
      crawl_id: headers.indexOf("crawl_id"),
      source_domain: headers.indexOf("source_domain"),
      product_id: headers.indexOf("product_id"),
      product_name: headers.indexOf("product_name"),
      brand: headers.indexOf("brand"),
      review_id: headers.indexOf("review_id"),
      review_date: headers.indexOf("review_date"),
      rating: headers.indexOf("rating"),
      review_text: headers.indexOf("review_text"),
      product_option: headers.indexOf("product_option"),
      helpful_count: headers.indexOf("helpful_count"),
      photo_review: headers.indexOf("photo_review"),
      video_review: headers.indexOf("video_review"),
      collected_at: headers.indexOf("collected_at")
    };

    const reviews = [];
    for (let i = 1; i < values.length; i++) {
      const row = values[i];
      if (!row || row.length === 0) continue;

      const getValue = (key, defaultVal = "") => {
        const idx = colIndex[key];
        if (idx !== -1 && idx < row.length && row[idx] !== undefined && row[idx] !== null) {
          return row[idx];
        }
        return defaultVal;
      };

      const rawRating = parseFloat(getValue("rating", 0));
      const rating = isNaN(rawRating) ? 0 : rawRating;

      const rawHelpful = parseInt(getValue("helpful_count", 0), 10);
      const helpfulCount = isNaN(rawHelpful) ? 0 : rawHelpful;

      const parseBool = (val) => {
        if (typeof val === "boolean") return val;
        const str = String(val).trim().toLowerCase();
        return str === "true" || str === "1" || str === "yes" || str === "y";
      };

      const reviewDateVal = getValue("review_date", "");
      let reviewDateStr = "";
      if (reviewDateVal instanceof Date) {
        reviewDateStr = reviewDateVal.toISOString();
      } else {
        reviewDateStr = String(reviewDateVal);
      }

      const collectedAtVal = getValue("collected_at", "");
      let collectedAtStr = "";
      if (collectedAtVal instanceof Date) {
        collectedAtStr = collectedAtVal.toISOString();
      } else {
        collectedAtStr = String(collectedAtVal);
      }

      reviews.push({
        source_domain: String(getValue("source_domain", "")),
        product_id: String(getValue("product_id", "")),
        product_name: String(getValue("product_name", "")),
        brand: String(getValue("brand", "")),
        review_id: String(getValue("review_id", "")),
        review_date: reviewDateStr,
        rating: rating,
        review_text: String(getValue("review_text", "")),
        product_option: String(getValue("product_option", "")),
        helpful_count: helpfulCount,
        photo_review: parseBool(getValue("photo_review", false)),
        video_review: parseBool(getValue("video_review", false)),
        collected_at: collectedAtStr
      });
    }

    return {
      status: "success",
      data: reviews,
      count: reviews.length,
      fetchedAt: new Date().toISOString()
    };
  } catch (err) {
    return {
      status: "error",
      message: "리뷰 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요."
    };
  }
}

/**
 * Review Dedup Key 생성을 위한 Helper
 * source_domain, product_id, review_id 3개 필드의 경계(boundary)를 보존하여
 * 값 내에 언더스코어(_)가 포함되더라도 충돌이 발생하지 않도록 JSON 배열 형태의 문자열로 변환
 */
function makeReviewDedupKey(sourceDomain, productId, reviewId) {
  return JSON.stringify([
    String(sourceDomain || "").trim(),
    String(productId || "").trim(),
    String(reviewId || "").trim()
  ]);
}

/**
 * Formula Injection 방어:
 * 텍스트가 =, +, -, @, \t, \r 등으로 시작할 경우 Google Sheets 수식 실행 방지를 위해 ' 접두어 추가
 */
function sanitizeFormula(val) {
  if (val === null || val === undefined) return "";
  const str = String(val);
  if (/^[=\+\-@\t\r]/.test(str)) {
    return "'" + str;
  }
  return str;
}

/**
 * 엑셀 Import 데이터 수신, LockService 동시성 보호, 서버 측 검증, 중복 제거 및 Append Only 처리
 *
 * @param {Array<Object>} rawItems Client에서 파싱된 JSON 리뷰 데이터 배열
 * @param {string} [spreadsheetIdOverride]
 * @return {Object} { status: "success"|"error", received: number, inserted: number, skipped_duplicate: number, invalid: number, fetchedAt: string }
 */
function importReviewData(rawItems, spreadsheetIdOverride) {
  const lock = LockService.getScriptLock();
  // 동시 접근 시 최대 10초 대기
  const acquired = lock.tryLock(10000);
  if (!acquired) {
    return {
      status: "error",
      message: "다른 담당자가 데이터를 반영 중입니다. 잠시 후 다시 시도해 주세요."
    };
  }

  try {
    if (!rawItems || !Array.isArray(rawItems)) {
      return {
        status: "error",
        message: "반영할 데이터가 올바르지 않습니다."
      };
    }

    const targetSpreadsheetId = spreadsheetIdOverride || DEFAULT_SPREADSHEET_ID;
    const ss = SpreadsheetApp.openById(targetSpreadsheetId);
    if (!ss) {
      return { status: "error", message: "Spreadsheet를 찾을 수 없습니다." };
    }

    const sheet = ss.getSheetByName(DEFAULT_SHEET_NAME);
    if (!sheet) {
      return { status: "error", message: `'${DEFAULT_SHEET_NAME}' 시트를 찾을 수 없습니다.` };
    }

    const data = sheet.getDataRange().getValues();
    if (!data || data.length === 0) {
      return { status: "error", message: "시트 헤더를 읽을 수 없습니다." };
    }

    const headers = data[0].map(h => String(h).trim().toLowerCase());

    const requiredHeaders = [
      "source_domain", "product_id", "product_name", "brand",
      "review_id", "review_date", "rating", "review_text",
      "product_option", "helpful_count", "photo_review",
      "video_review", "collected_at"
    ];

    const missingHeaders = requiredHeaders.filter(h => headers.indexOf(h) === -1);
    if (missingHeaders.length > 0) {
      return {
        status: "error",
        message: "리뷰 데이터 형식이 올바르지 않습니다. 필요한 컬럼을 확인해 주세요."
      };
    }

    // 기존 01_REVIEW_RAW의 Dedup Key (source_domain + product_id + review_id) Set 구성 (Collision-safe)
    const colSource = headers.indexOf("source_domain");
    const colProduct = headers.indexOf("product_id");
    const colReviewId = headers.indexOf("review_id");

    const existingKeys = new Set();
    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      if (row && row.length > Math.max(colSource, colProduct, colReviewId)) {
        const sDom = String(row[colSource] || "").trim();
        const pId = String(row[colProduct] || "").trim();
        const rId = String(row[colReviewId] || "").trim();
        if (sDom && pId && rId) {
          existingKeys.add(makeReviewDedupKey(sDom, pId, rId));
        }
      }
    }

    let insertedCount = 0;
    let skippedDuplicateCount = 0;
    let invalidCount = 0;

    const rowsToAppend = [];
    const batchKeys = new Set();

    const parseBool = (val) => {
      if (typeof val === "boolean") return val;
      const str = String(val).trim().toLowerCase();
      return str === "true" || str === "1" || str === "yes" || str === "y";
    };

    for (let i = 0; i < rawItems.length; i++) {
      const item = rawItems[i];
      if (!item || typeof item !== "object") {
        invalidCount++;
        continue;
      }

      const sourceDomain = String(item.source_domain || "").trim();
      const productId = String(item.product_id || "").trim();
      const reviewId = String(item.review_id || "").trim();

      // Row Validation: 필수 수집 키 누락 시 invalid
      if (!sourceDomain || !productId || !reviewId) {
        invalidCount++;
        continue;
      }

      const key = makeReviewDedupKey(sourceDomain, productId, reviewId);
      if (existingKeys.has(key) || batchKeys.has(key)) {
        skippedDuplicateCount++;
        continue;
      }

      batchKeys.add(key);

      // Sheet Header 순서에 맞춰 Data row 구성 및 Formula injection 방어
      const row = headers.map(header => {
        if (header === "crawl_id") return sanitizeFormula(item.crawl_id || "");
        if (header === "source_domain") return sanitizeFormula(sourceDomain);
        if (header === "product_id") return sanitizeFormula(productId);
        if (header === "product_name") return sanitizeFormula(item.product_name || "");
        if (header === "brand") return sanitizeFormula(item.brand || "");
        if (header === "review_id") return sanitizeFormula(reviewId);
        if (header === "review_date") {
          const val = item.review_date;
          if (val instanceof Date) return val.toISOString();
          return sanitizeFormula(val || "");
        }
        if (header === "rating") {
          const r = parseFloat(item.rating);
          return isNaN(r) ? 0 : r;
        }
        if (header === "review_text") return sanitizeFormula(item.review_text || "");
        if (header === "product_option") return sanitizeFormula(item.product_option || "");
        if (header === "helpful_count") {
          const h = parseInt(item.helpful_count, 10);
          return isNaN(h) ? 0 : h;
        }
        if (header === "photo_review") return parseBool(item.photo_review);
        if (header === "video_review") return parseBool(item.video_review);
        if (header === "collected_at") {
          const val = item.collected_at;
          if (val instanceof Date) return val.toISOString();
          return sanitizeFormula(val || new Date().toISOString());
        }
        return sanitizeFormula(item[header] || "");
      });

      rowsToAppend.push(row);
      insertedCount++;
    }

    if (rowsToAppend.length > 0) {
      const lastRow = sheet.getLastRow();
      sheet.getRange(lastRow + 1, 1, rowsToAppend.length, headers.length).setValues(rowsToAppend);
    }

    return {
      status: "success",
      received: rawItems.length,
      inserted: insertedCount,
      skipped_duplicate: skippedDuplicateCount,
      invalid: invalidCount,
      fetchedAt: new Date().toISOString()
    };
  } catch (err) {
    return {
      status: "error",
      message: "데이터 반영 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
    };
  } finally {
    lock.releaseLock();
  }
}
