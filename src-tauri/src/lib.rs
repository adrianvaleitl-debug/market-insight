use serde::Serialize;

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct MarketQuote {
    symbol: String,
    current_price: f64,
    previous_close: f64,
    change_percent: f64,
    closes: Vec<f64>,
    highs: Vec<f64>,
    lows: Vec<f64>,
    volumes: Vec<f64>,
    currency: String,
    market_state: String,
}

#[tauri::command]
async fn get_market_quote(symbol: String) -> Result<MarketQuote, String> {
    let symbol = symbol.trim().to_uppercase();
    if symbol.is_empty() || symbol.len() > 20 || !symbol.chars().all(|c| c.is_ascii_alphanumeric() || ".-=^".contains(c)) {
        return Err("Enter a valid ticker symbol.".to_string());
    }
    let url = format!("https://query1.finance.yahoo.com/v8/finance/chart/{}?range=3mo&interval=1d", symbol);
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(15))
        .build().map_err(|_| "Market data client could not be initialised.".to_string())?;
    let response = client
        .get(url)
        .header("User-Agent", "Mozilla/5.0 AdrianValeMarketInsight/3.0")
        .send().await.map_err(|_| "Market data could not be reached. Check your internet connection.".to_string())?;
    if !response.status().is_success() {
        return Err(format!("Market data provider returned HTTP {}.", response.status()));
    }
    let payload: serde_json::Value = response.json().await.map_err(|_| "Market data response could not be read.".to_string())?;
    if let Some(error) = payload["chart"]["error"]["description"].as_str() {
        return Err(error.to_string());
    }
    let result = payload["chart"]["result"][0].clone();
    if result.is_null() { return Err("No market data was found for that symbol.".to_string()); }
    let meta = &result["meta"];
    let closes: Vec<f64> = result["indicators"]["quote"][0]["close"].as_array().into_iter().flatten().filter_map(|v| v.as_f64()).collect();
    let highs: Vec<f64> = result["indicators"]["quote"][0]["high"].as_array().into_iter().flatten().filter_map(|v| v.as_f64()).collect();
    let lows: Vec<f64> = result["indicators"]["quote"][0]["low"].as_array().into_iter().flatten().filter_map(|v| v.as_f64()).collect();
    let volumes: Vec<f64> = result["indicators"]["quote"][0]["volume"].as_array().into_iter().flatten().filter_map(|v| v.as_f64()).collect();
    let previous_close = meta["chartPreviousClose"].as_f64().or_else(|| meta["previousClose"].as_f64()).unwrap_or(0.0);
    let current_price = meta["regularMarketPrice"].as_f64().or_else(|| closes.last().copied()).unwrap_or(0.0);
    if current_price <= 0.0 { return Err("The provider did not return a usable price for this symbol.".to_string()); }
    let change_percent = if previous_close > 0.0 { (current_price - previous_close) / previous_close * 100.0 } else { 0.0 };
    Ok(MarketQuote {
        symbol,
        current_price,
        previous_close,
        change_percent,
        closes,
        highs,
        lows,
        volumes,
        currency: meta["currency"].as_str().unwrap_or("—").to_string(),
        market_state: meta["marketState"].as_str().unwrap_or("UNKNOWN").to_string(),
    })
}

#[tauri::command]
fn open_external_url(url: String) -> Result<(), String> {
    if url.len() > 2048 || !url.starts_with("https://") || url.chars().any(char::is_control) {
        return Err("Only valid HTTPS links can be opened.".to_string());
    }
    open::that(url).map_err(|error| format!("The system could not open the trading platform: {error}"))
}

#[cfg_attr(mobile,tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![get_market_quote, open_external_url])
        .run(tauri::generate_context!())
        .expect("error while running Market Insight");
}
