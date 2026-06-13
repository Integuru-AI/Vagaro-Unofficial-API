"""Get transaction list from Vagaro sales reports."""

import json
import re
from urllib.parse import unquote

from curl_cffi import requests


def run(headers, user_input):
    """Fetch transaction list from Vagaro sales reports.

    Args:
        headers: dict with Cookie header for authentication
        user_input: dict with:
            - from_date: str (YYYY-MM-DD, required)
            - to_date: str (YYYY-MM-DD, required)
            - page: int (default 1)
            - page_size: int (default 50)
            - search_text: str (default "")
            - show_refunded: bool (default False)
            - transaction_type: int (default -1, meaning all)
    """
    from_date = user_input.get("from_date")
    to_date = user_input.get("to_date")
    if not from_date or not to_date:
        return {"status_code": 400, "body": {"error": "from_date and to_date are required (YYYY-MM-DD)"}}

    page = user_input.get("page", 1)
    page_size = user_input.get("page_size", 50)
    search_text = user_input.get("search_text", "")
    show_refunded = user_input.get("show_refunded", False)
    transaction_type = user_input.get("transaction_type", -1)

    cookie_str = headers.get("Cookie", "")
    auth = _extract_auth(cookie_str)

    # Step 1: Get BId (ClientId) and UId (ClientSecret) from report details
    details, err = _get_report_details(cookie_str, auth)
    if err:
        return err

    client_id = details.get("BId", "")
    client_secret = details.get("UId", "")
    service_providers = ",".join(
        str(sp["UserID"]) for sp in details.get("ServiceProviders", [])
        if sp.get("IsForReport")
    )
    business_id = str(details.get("businessId", ""))
    currency_symbol = details.get("CurrencySymbol", "$")

    # Step 2: Fetch transactions
    payload = {
        "ClientId": client_id,
        "ClientSecret": client_secret,
        "ServiceProviderID": service_providers,
        "FromDate": from_date,
        "ToDate": to_date,
        "CheckedOutBy": None,
        "ShowRefundedRecords": show_refunded,
        "DepositInMerchantAccountName": "",
        "TransactionType": str(transaction_type),
        "AppFromDate": None,
        "AppToDate": None,
        "CCTransactionMode": None,
        "SearchText": search_text,
        "PresetDailyDealIDs": None,
        "IsFromXeroQuickBooks": False,
        "DepositInMerchantAccount": None,
        "IsOldVersionForAPP": False,
        "CurrentPage": page,
        "PageSize": page_size,
        "ColumnName": "",
        "OrderBy": "ASC",
        "CustomerID": 0,
        "viewHisOwnReports": True,
        "viewOthersReports": True,
        "isPastEmployee": True,
        "isAdmin": False,
        "userType": int(details.get("UserType", 4)),
        "IncludeCustomerIds": "",
        "ExcludeCustomerIds": "",
        "currencySymbol": currency_symbol,
        "MultiLocationBusinessIDs": business_id,
        "CredentialsIds": None,
        "SourceTitle": "",
        "DepositStatusData": None,
        "InventoryType": None,
    }

    request_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Cookie": cookie_str,
        "grouptoken": auth["grouptoken"],
        "merchantid": auth["merchantid"],
        "userid": auth["userid"],
        "employeeid": auth["userid"],
        "s_utkn": auth["s_utkn"],
        "s_did": "",
        "s_mtkn": "",
        "Origin": f"https://{auth['grouptoken'].lower()}.vagaro.com",
        "Referer": f"https://{auth['grouptoken'].lower()}.vagaro.com/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    }

    response = requests.post(
        f"https://api.vagaro.com/{auth['grouptoken'].lower()}/api/v2/merchants/reports/sales/gettransactionlist",
        json=payload,
        headers=request_headers,
        impersonate="chrome131",
        timeout=30,
    )

    if response.status_code in (401, 403):
        return {"status_code": 401, "body": {"error": "Session expired"}}

    try:
        result = response.json()
    except Exception:
        if "login" in response.text.lower() or "sign in" in response.text.lower():
            return {"status_code": 401, "body": {"error": "Session expired"}}
        return {"status_code": response.status_code, "body": {"raw": response.text[:500]}}

    if isinstance(result, dict):
        if result.get("CustomCode") in (401, 1001) or result.get("ResponseCode") == 401:
            return {"status_code": 401, "body": {"error": "Session expired"}}

    return {"status_code": response.status_code, "body": result}


# === PRIVATE ===

def _extract_auth(cookie_str):
    """Extract auth tokens from cookie string."""
    auth = {"s_utkn": "", "merchantid": "", "userid": "", "grouptoken": "US03"}

    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        if k == "s_utkn":
            auth["s_utkn"] = v.strip()
        elif k == "tenant_group":
            auth["grouptoken"] = v.strip().upper()

    rpt_match = re.search(r"rpt_data=([^;]+)", cookie_str)
    if rpt_match:
        try:
            decoded = unquote(rpt_match.group(1)).replace('\\"', '"')
            rpt = json.loads(decoded)
            auth["merchantid"] = rpt.get("MerchantId", "")
            auth["userid"] = rpt.get("UserId", "")
            auth["grouptoken"] = rpt.get("grouptoken", auth["grouptoken"])
        except Exception:
            pass

    if not auth["userid"]:
        enc_match = re.search(r"s_encuid=([^;]+)", cookie_str)
        if enc_match:
            auth["userid"] = enc_match.group(1).strip()

    return auth


def _get_report_details(cookie_str, auth):
    """Call GetReportBasicDetails to get BId/UId and service provider list."""
    request_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Cookie": cookie_str,
        "grouptoken": auth["grouptoken"],
        "merchantid": auth["merchantid"],
        "userid": auth["userid"],
        "employeeid": auth["userid"],
        "s_utkn": auth["s_utkn"],
        "Origin": f"https://{auth['grouptoken'].lower()}.vagaro.com",
        "Referer": f"https://{auth['grouptoken'].lower()}.vagaro.com/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    }

    response = requests.post(
        f"https://api.vagaro.com/{auth['grouptoken'].lower()}/api/v2/merchants/reports/detailsNew",
        json={"ClientId": None, "ClientSecret": None, "Type": 1},
        headers=request_headers,
        impersonate="chrome131",
        timeout=30,
    )

    if response.status_code in (401, 403):
        return None, {"status_code": 401, "body": {"error": "Session expired"}}

    try:
        data = response.json()
    except Exception:
        return None, {"status_code": response.status_code, "body": {"error": "Failed to parse report details"}}

    if not data.get("Data"):
        return None, {"status_code": 401, "body": {"error": "No data returned from report details - session may be expired"}}

    return data["Data"], None
