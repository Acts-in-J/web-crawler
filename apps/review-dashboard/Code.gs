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
 * 서버 측 요청 자격증명(Identity) 정보 수집 및 객체화
 * ActiveUser, EffectiveUser, TemporaryActiveUserKey 정보를 비구조화하여 통합 반환.
 * ActiveUser 이메일이 존재하면 stableIdentity로 확정하고, 없으면 빈값("")을 유지한다.
 * EffectiveUser나 TemporaryActiveUserKey를 방문자의 stableIdentity로 대체하지 않는다.
 *
 * @return {Object} { activeEmail: string, effectiveEmail: string, temporaryUserKey: string, identityType: string, stableIdentity: string, authenticated: boolean }
 */
function resolveRequestIdentity() {
  let activeEmail = "";
  try {
    const user = Session.getActiveUser();
    if (user && typeof user.getEmail === "function") {
      activeEmail = String(user.getEmail() || "").trim().toLowerCase();
    }
  } catch (err) {
    activeEmail = "";
  }

  let effectiveEmail = "";
  try {
    const eff = Session.getEffectiveUser();
    if (eff && typeof eff.getEmail === "function") {
      effectiveEmail = String(eff.getEmail() || "").trim().toLowerCase();
    }
  } catch (err) {
    effectiveEmail = "";
  }

  let temporaryUserKey = "";
  try {
    if (typeof Session.getTemporaryActiveUserKey === "function") {
      temporaryUserKey = String(Session.getTemporaryActiveUserKey() || "").trim();
    }
  } catch (err) {
    temporaryUserKey = "";
  }

  const stableIdentity = activeEmail; // Non-empty activeEmail ONLY
  const authenticated = stableIdentity !== "";
  const identityType = activeEmail !== "" ? "active_user" : (temporaryUserKey !== "" ? "anonymous_session" : "unknown");

  return {
    activeEmail: activeEmail,
    effectiveEmail: effectiveEmail,
    temporaryUserKey: temporaryUserKey,
    identityType: identityType,
    stableIdentity: stableIdentity,
    authenticated: authenticated
  };
}

/**
 * 리뷰 Dashboard Read 요청 권한 검증 (확장 가능한 구조 설계)
 * Fail-Closed 원칙에 따라 검증한다.
 *
 * @param {Object} [identity]
 * @return {Object} { allowed: boolean, reason: string }
 */
function authorizeDashboardRead(identity) {
  const reqIdentity = identity || resolveRequestIdentity();

  if (!reqIdentity || !reqIdentity.stableIdentity) {
    return {
      allowed: false,
      reason: "인증된 사용자 식별 정보가 없어 대시보드 조회 권한이 거부되었습니다."
    };
  }

  let rawAllowedProp = "";
  try {
    const props = PropertiesService.getScriptProperties();
    if (!props || typeof props.getProperty !== "function") {
      return {
        allowed: false,
        reason: "권한 목록 설정을 읽을 수 없어 조회 권한이 거부되었습니다."
      };
    }
    // We can use the same allowlist or a specific read allowlist.
    // Let's use REVIEW_DASHBOARD_READ_ALLOWED_USERS as the canonical source.
    rawAllowedProp = props.getProperty("REVIEW_DASHBOARD_READ_ALLOWED_USERS");
    if (rawAllowedProp === null || rawAllowedProp === undefined) {
      return {
        allowed: false,
        reason: "대시보드 조회 권한 목록이 설정되어 있지 않습니다."
      };
    }
  } catch (err) {
    return {
      allowed: false,
      reason: "권한 목록 설정 조회 중 오류가 발생하여 조회 권한이 거부되었습니다."
    };
  }

  const allowedListStr = String(rawAllowedProp).trim();
  if (allowedListStr.length === 0) {
    return {
      allowed: false,
      reason: "대시보드 조회 권한 목록이 비어 있어 권한이 거부되었습니다."
    };
  }

  const allowedEmails = allowedListStr.split(",").map(e => e.trim().toLowerCase()).filter(e => e.length > 0);
  const isAllowed = allowedEmails.indexOf(reqIdentity.stableIdentity) !== -1;

  if (isAllowed) {
    return { allowed: true, reason: "Read authorized via allowlist" };
  } else {
    return {
      allowed: false,
      reason: `'${reqIdentity.stableIdentity}' 계정은 대시보드 조회 권한이 없습니다.`
    };
  }
}

/**
 * 리뷰 Import (Write) 요청 서버 측 권한 검증
 * Fail-Closed 원칙:
 * 1. stableIdentity가 빈값("")이면 WRITE = DENY. (TemporaryActiveUserKey 단독으로는 절대 WRITE = ALLOW 불가)
 * 2. REVIEW_DASHBOARD_ALLOWED_USERS Property 조회 실패, missing, 빈값 시 무조건 WRITE = DENY.
 * 3. stableIdentity가 명시된 allowlist 목록에 포함되어 있으면 WRITE = ALLOW, 그렇지 않으면 WRITE = DENY.
 * 4. 암묵적인 deployer/owner bootstrap 허용 구문(effectiveEmail 비교 등)은 전면 제거한다.
 *
 * @param {Object} [identity]
 * @return {Object} { allowed: boolean, reason: string }
 */
function authorizeReviewImport(identity) {
  const reqIdentity = identity || resolveRequestIdentity();

  if (!reqIdentity || !reqIdentity.stableIdentity) {
    return {
      allowed: false,
      reason: "인증된 사용자 이메일 식별 정보가 없어 리뷰 데이터 반영 권한이 거부되었습니다."
    };
  }

  let rawAllowedProp = "";
  try {
    const props = PropertiesService.getScriptProperties();
    if (!props || typeof props.getProperty !== "function") {
      return {
        allowed: false,
        reason: "권한 목록 설정을 읽을 수 없어 반영 권한이 거부되었습니다."
      };
    }
    rawAllowedProp = props.getProperty("REVIEW_DASHBOARD_ALLOWED_USERS");
    if (rawAllowedProp === null || rawAllowedProp === undefined) {
      return {
        allowed: false,
        reason: "리뷰 반영 권한 목록이 설정되어 있지 않습니다."
      };
    }
  } catch (err) {
    return {
      allowed: false,
      reason: "권한 목록 설정 조회 중 오류가 발생하여 반영 권한이 거부되었습니다."
    };
  }

  const allowedListStr = String(rawAllowedProp).trim();
  if (allowedListStr.length === 0) {
    return {
      allowed: false,
      reason: "리뷰 반영 권한 목록이 비어 있어 반영 권한이 거부되었습니다."
    };
  }

  const allowedEmails = allowedListStr.split(",").map(e => e.trim().toLowerCase()).filter(e => e.length > 0);
  const isAllowed = allowedEmails.indexOf(reqIdentity.stableIdentity) !== -1;

  if (isAllowed) {
    return { allowed: true, reason: "Allowlist authorized" };
  } else {
    return {
      allowed: false,
      reason: `'${reqIdentity.stableIdentity}' 계정은 리뷰 데이터 반영 권한이 없습니다.`
    };
  }
}

/**
 * Google Sheet 01_REVIEW_RAW 데이터 조회 및 Object 변환 (Public Entry Point)
 * 브라우저 클라이언트 호출용. 서버 고정 DEFAULT_SPREADSHEET_ID만 사용한다.
 *
 * @return {object} { status: "success"|"error", data: Array, count: number, fetchedAt: string }
 */
function getReviewDashboardData() {
  return getReviewDashboardData_(DEFAULT_SPREADSHEET_ID);
}

/**
 * 엑셀 Import 데이터 수신 및 반영 (Public Entry Point)
 * 브라우저 클라이언트 호출용. 서버 고정 DEFAULT_SPREADSHEET_ID만 사용한다.
 *
 * @param {Array<Object>} rawItems Client에서 파싱된 JSON 리뷰 데이터 배열
 * @param {string} [importFilename] 업로드된 원본 엑셀 파일명
 * @return {Object} { status: "success"|"error", received: number, inserted: number, skipped_duplicate: number, invalid: number, fetchedAt: string }
 */
function importReviewData(rawItems, importFilename) {
  return importReviewData_(rawItems, DEFAULT_SPREADSHEET_ID, importFilename);
}

/**
 * 리뷰 Dashboard Read 내부 헬퍼 (Private Server Function - Browser 호출 불가)
 *
 * @param {string} targetSpreadsheetId
 * @return {object}
 */
function getReviewDashboardData_(targetSpreadsheetId) {
  const identity = resolveRequestIdentity();
  const authResult = authorizeDashboardRead(identity);
  if (!authResult.allowed) {
    return {
      status: "error",
      message: authResult.reason || "조회 권한이 없습니다."
    };
  }

  try {
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
      collected_at: headers.indexOf("collected_at"),
      import_batch_id: headers.indexOf("import_batch_id"),
      import_filename: headers.indexOf("import_filename"),
      imported_by: headers.indexOf("imported_by"),
      imported_at: headers.indexOf("imported_at")
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
        collected_at: collectedAtStr,
        import_batch_id: String(getValue("import_batch_id", "")),
        import_filename: String(getValue("import_filename", "")),
        imported_by: String(getValue("imported_by", "")),
        imported_at: String(getValue("imported_at", ""))
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
 * 01_REVIEW_RAW 시트 헤더에 선택적 Provenance 컬럼(import_batch_id, import_filename, imported_by, imported_at)이
 * 없으면 순서대로 기존 헤더 끝에 추가하는 Idempotent Helper.
 * 기존 헤더를 재배포하거나 삭제하거나 순서를 바꾸지 않는다.
 */
function ensureProvenanceHeaders(sheet, currentHeaders) {
  const provenanceHeaders = ["import_batch_id", "import_filename", "imported_by", "imported_at"];
  const missingProvenance = provenanceHeaders.filter(h => currentHeaders.indexOf(h) === -1);
  if (missingProvenance.length > 0) {
    const startCol = currentHeaders.length + 1;
    sheet.getRange(1, startCol, 1, missingProvenance.length).setValues([missingProvenance]);
    missingProvenance.forEach(h => currentHeaders.push(h));
  }
  return currentHeaders;
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
 * 엑셀 Import 내부 헬퍼 (Private Server Function - Browser 호출 불가)
 *
 * @param {Array<Object>} rawItems Client에서 파싱된 JSON 리뷰 데이터 배열
 * @param {string} targetSpreadsheetId 대상 Spreadsheet ID
 * @param {string} [importFilename] 업로드된 원본 엑셀 파일명
 * @return {Object} { status: "success"|"error", received: number, inserted: number, skipped_duplicate: number, invalid: number, fetchedAt: string }
 */
function importReviewData_(rawItems, targetSpreadsheetId, importFilename) {
  const identity = resolveRequestIdentity();
  const authResult = authorizeReviewImport(identity);
  if (!authResult.allowed) {
    return {
      status: "error",
      message: authResult.reason || "리뷰 반영 권한이 없습니다."
    };
  }

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

    let headers = data[0].map(h => String(h).trim().toLowerCase());

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

    // Header migration: 선택적 provenance 컬럼 idempotent 추가
    headers = ensureProvenanceHeaders(sheet, headers);

    // Server-authoritative batch metadata generation
    const serverBatchId = Utilities.getUuid();
    const serverImportedAt = new Date().toISOString();
    const serverImportedBy = sanitizeFormula(identity.stableIdentity || "");
    const cleanImportFilename = sanitizeFormula(importFilename || "");

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
        if (header === "import_batch_id") return sanitizeFormula(serverBatchId);
        if (header === "import_filename") return cleanImportFilename;
        if (header === "imported_by") return sanitizeFormula(serverImportedBy);
        if (header === "imported_at") return sanitizeFormula(serverImportedAt);
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
