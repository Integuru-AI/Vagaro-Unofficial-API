"""Get all customers from Vagaro."""

import json
import urllib.parse
from curl_cffi import requests as curl_requests


def run(headers, user_input):
    """Get all customers from the Vagaro account.

    Args:
        headers: dict containing Cookie with s_utkn token
        user_input: dict with optional filtering parameters:
            - search_text: Filter customers by name/email/phone (optional)
            - page: Page number (default: 1)
            - page_size: Number of results per page (default: 1000)

    Returns:
        dict with status_code and body containing customer list
    """
    cookie_str = headers.get("Cookie", "")
    s_utkn = _extract_s_utkn(cookie_str)
    grouptoken = _extract_grouptoken(cookie_str)

    if not s_utkn:
        return {"status_code": 401, "body": {"error": "Missing s_utkn token in cookies"}}

    if not grouptoken:
        return {"status_code": 500, "body": {"error": "Could not determine grouptoken from cookies"}}

    # Get optional parameters
    search_text = user_input.get("search_text", "")
    page = user_input.get("page", 1)
    page_size = user_input.get("page_size", 1000)

    try:
        data = _call_api(s_utkn, grouptoken, search_text, page, page_size)

        # Check for API-level auth errors (Vagaro returns 200 with error in body)
        if isinstance(data, dict):
            if data.get("status") == 401 or data.get("responseCode") == 1034:
                return {"status_code": 401, "body": {"error": data.get("message", "Access denied")}}
            if data.get("error"):
                error_msg = str(data.get("error", ""))
                if "auth" in error_msg.lower() or "token" in error_msg.lower() or "denied" in error_msg.lower():
                    return {"status_code": 401, "body": {"error": error_msg}}

        return {"status_code": 200, "body": data}

    except Exception as e:
        return {"status_code": 500, "body": {"error": str(e)}}


# === PRIVATE ===


def _extract_s_utkn(cookie_header):
    """Extract the s_utkn JWT from the Cookie header."""
    for part in cookie_header.split("; "):
        if part.startswith("s_utkn="):
            return part.split("=", 1)[1]
    return ""


def _extract_grouptoken(cookie_header):
    """Extract the grouptoken from the rpt_data cookie."""
    for part in cookie_header.split("; "):
        if part.startswith("rpt_data="):
            try:
                rpt_value = urllib.parse.unquote(part.split("=", 1)[1])
                rpt_data = json.loads(rpt_value)
                return rpt_data.get("grouptoken", "")
            except (json.JSONDecodeError, IndexError):
                pass
    # Fallback: check tenant_group cookie
    for part in cookie_header.split("; "):
        if part.startswith("tenant_group="):
            return part.split("=", 1)[1].upper()
    return ""


def _call_api(s_utkn, grouptoken, search_text, page, page_size):
    """Call the Vagaro customers API."""
    api_url = f"https://api.vagaro.com/{grouptoken}/api/v3/merchants/customers/retrieve"

    # ForStorage=true returns ALL customers for local caching (ignores search)
    # ForStorage=false enables server-side filtering by searchtext
    for_storage = "false" if search_text else "true"

    params = {
        "searchtext": search_text,
        "Page": str(page),
        "PageSize": str(page_size),
        "ForStorage": for_storage,
        "LastSyncTime": "",
        "multiLocationBusinessIDs": ""
    }

    request_headers = {
        "accept": "application/json, text/plain, */*",
        "grouptoken": grouptoken,
        "s_utkn": s_utkn,
        "origin": f"https://{grouptoken.lower()}.vagaro.com",
        "referer": f"https://{grouptoken.lower()}.vagaro.com/"
    }

    session = curl_requests.Session(impersonate="chrome131")
    response = session.get(api_url, params=params, headers=request_headers, timeout=30)

    # Check for auth failure (redirects to login or returns error)
    if response.status_code == 401 or response.status_code == 403:
        raise Exception("Authentication failed")

    # Check for login page redirect
    if "login" in response.url.lower() or "<html" in response.text[:100].lower():
        raise Exception("Session expired")

    return response.json()
