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
