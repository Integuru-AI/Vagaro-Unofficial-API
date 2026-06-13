"""Get all customer data from Vagaro in one call."""

import json
import urllib.parse
from curl_cffi import requests as curl_requests


def run(headers, user_input):
    """Get all data for a customer: profile, appointments, products, notes, SOAP, forms, gift cards, packages, memberships, invoices.

    Args:
        headers: Auth headers with Cookie containing s_utkn
        user_input: dict with customer_id (encrypted customer ID)

    Returns:
        dict with status_code and body containing all customer data categories
    """
    customer_id = user_input.get("customer_id")
    if not customer_id:
        return {"status_code": 400, "body": {"error": "customer_id is required"}}

    # Extract session token from cookies
    cookie = headers.get("Cookie", "")
    s_utkn = None
    s_encuid = None
    merchant_id = None

    for part in cookie.split("; "):
        if part.startswith("s_utkn="):
            s_utkn = part[7:]
        elif part.startswith("s_encuid="):
            s_encuid = part[9:]
        elif part.startswith("rpt_data="):
            try:
                rpt_data = json.loads(urllib.parse.unquote(part[9:]))
                merchant_id = rpt_data.get("MerchantId")
            except:
                pass

    if not s_utkn:
        return {"status_code": 401, "body": {"error": "Session expired - s_utkn not found in cookies"}}

    employee_id = s_encuid or ""

    # Fetch all customer data categories
    result = _fetch_all_customer_data(customer_id, s_utkn, employee_id, merchant_id)

    # Check if any request indicated session expiry
    for key, value in result.items():
        if isinstance(value, dict) and value.get("error") == "Session expired":
            return {"status_code": 401, "body": {"error": "Session expired"}}

    return {"status_code": 200, "body": result}


# === PRIVATE ===


def _get_region():
    """Extract region code (e.g. 'US03') from the injected BASE_URL (e.g. 'https://us03.vagaro.com')."""
    import re
    m = re.search(r"(us\d+)", BASE_URL, re.IGNORECASE)
    return m.group(1).upper() if m else "US03"


def _get_api_base():
    """Build API base URL from account's BASE_URL."""
    region = _get_region()
    return f"https://api.vagaro.com/{region}"


def _make_request(method, endpoint, s_utkn, customer_id, payload=None, extra_headers=None):
    """Make API request to Vagaro."""
    api_base = _get_api_base()
    region = _get_region()
    base_headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "consumerid": customer_id,
        "device": "Website",
        "grouptoken": region,
        "module": "history/profile",
        "s_utkn": s_utkn,
    }
    if extra_headers:
        base_headers.update(extra_headers)

    try:
        if method == "GET":
            resp = curl_requests.get(
                f"{api_base}{endpoint}",
                headers=base_headers,
                impersonate="chrome131",
                timeout=30
            )
        else:
            resp = curl_requests.post(
                f"{api_base}{endpoint}",
                headers=base_headers,
                json=payload,
                impersonate="chrome131",
                timeout=30
            )

        if resp.status_code in [401, 403]:
            return {"error": "Session expired"}
        if resp.status_code == 204:
            return {"data": {"total": 0, "list": []}}
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def _fetch_all_customer_data(customer_id, s_utkn, employee_id, merchant_id):
    """Fetch all customer data categories from Vagaro API."""
    result = {}

    # 1. Profile
    result["profile"] = _make_request(
        "GET", "/api/v3/merchants/customers/profile/retrieve",
        s_utkn, customer_id
    )

    # 2. Appointments
    result["appointments"] = _make_request(
        "POST", "/api/v3/merchants/customers/appointments/retrieve",
        s_utkn, customer_id,
        {"page": 1, "pageSize": 1000, "sortBy": "sDatetime", "sortOrder": "DESC",
         "merchantId": None, "busSharingApply": True}
    )

    # 3. Products
    result["products"] = _make_request(
        "POST", "/api/v3/merchants/customers/products/retrieve",
        s_utkn, customer_id,
        {"page": 1, "pageSize": 1000, "sortBy": "sCreatedDate", "sortOrder": "DESC",
         "merchantId": None, "busFilterApply": True}
    )

    # 4. Notes
    result["notes"] = _make_request(
        "POST", "/api/v3/merchants/customers/notes/retrieve",
        s_utkn, customer_id,
        {"type": -1, "page": 1, "pageSize": 1000, "merchantId": None, "operationType": 1}
    )

    # 5. SOAP Notes
    result["soap"] = _make_request(
        "POST", "/api/v3/merchants/customers/notes/retrieve",
        s_utkn, customer_id,
        {"type": -1, "page": 1, "pageSize": 1000, "merchantId": None, "operationType": 2}
    )

    # 6. Forms (different header requirements)
    forms_headers = {
        "consumerid": None,  # Remove consumerid for forms
        "module": None,
    }
    if employee_id:
        forms_headers["employeeid"] = employee_id
        forms_headers["userid"] = employee_id
    if merchant_id:
        forms_headers["merchantid"] = merchant_id

    api_base = _get_api_base()
    region = _get_region()
    try:
        resp = curl_requests.post(
            f"{api_base}/api/v3/merchants/forms/customer/response/retrieve",
            headers={
                "accept": "*/*",
                "content-type": "application/json",
                "device": "Website",
                "grouptoken": region,
                "s_utkn": s_utkn,
                **({"employeeid": employee_id, "userid": employee_id} if employee_id else {}),
                **({"merchantid": merchant_id} if merchant_id else {}),
            },
            json={"customerID": customer_id, "formType": 2, "showDeleted": True},
            impersonate="chrome131",
            timeout=30
        )
        if resp.status_code == 204:
            result["forms"] = {"data": {"total": 0, "list": []}}
        elif resp.status_code in [401, 403]:
            result["forms"] = {"error": "Session expired"}
        else:
            result["forms"] = resp.json()
    except Exception as e:
        result["forms"] = {"error": str(e)}

    # 7. Gift Cards
    result["giftcards"] = _make_request(
        "POST", "/api/v3/merchants/customers/giftcards/retrieve",
        s_utkn, customer_id,
        {"page": 1, "pageSize": 1000, "sortBy": "screatedDate", "sortOrder": "DESC",
         "purchaseAt": "All Purchase Locations", "merchantId": None, "busFilterApply": False}
    )

    # 8. Packages
    result["packages"] = _make_request(
        "POST", "/api/v3/merchants/customers/packages/retrieve",
        s_utkn, customer_id,
        {"page": 1, "pageSize": 1000, "sortBy": "createdDate", "sortOrder": "DESC",
         "merchantId": None, "busFilterApply": True}
    )

    # 9. Memberships
    result["memberships"] = _make_request(
        "POST", "/api/v3/merchants/customers/memberships/retrieve",
        s_utkn, customer_id,
        {"page": 1, "pageSize": 1000, "sortBy": "CreatedDate", "sortOrder": "DESC",
         "isForMyAcc": False, "merchantId": None, "busFilterApply": False}
    )

    # 10. Invoices
    result["invoices"] = _make_request(
        "POST", "/api/v3/merchants/settings/thingswesell/invoices/retrieve",
        s_utkn, customer_id,
        {"page": 1, "customerId": customer_id, "pageSize": 1000,
         "sortBy": "CreatedDate", "sortOrder": "DESC"}
    )

    return result
