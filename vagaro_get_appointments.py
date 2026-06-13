import re
from curl_cffi import requests


def _extract_from_cookie(cookie_str, key):
    """Extract a value from a cookie string."""
    pattern = rf'{key}=([^;]+)'
    match = re.search(pattern, cookie_str)
    return match.group(1) if match else None


def _parse_rpt_data(cookie_str):
    """Extract and parse rpt_data JSON from cookie string."""
    import urllib.parse
    import json

    raw = _extract_from_cookie(cookie_str, 'rpt_data')
    if not raw:
        return {}
    decoded = urllib.parse.unquote(raw)
    cleaned = decoded.replace('\\"', '"')
    try:
        return json.loads(cleaned)
    except Exception:
        return {}


def run(headers, user_input):
    """Get appointments for specified employee(s) within a date range."""
    calendar_ids = user_input.get('calendarIds')
    from_date = user_input.get('fromDate')
    to_date = user_input.get('toDate')

    if not calendar_ids:
        return {'status_code': 400, 'body': {'error': 'calendarIds is required'}}
    if not from_date:
        return {'status_code': 400, 'body': {'error': 'fromDate is required'}}
    if not to_date:
        return {'status_code': 400, 'body': {'error': 'toDate is required'}}

    if isinstance(calendar_ids, str):
        calendar_ids = [calendar_ids]

    resource_ids = user_input.get('resourceIds', [])
    class_calendar_ids = user_input.get('classCalendarIds', [''])

    payload = {
        'calendarIds': calendar_ids,
        'fromDate': from_date,
        'toDate': to_date,
        'resourceIds': resource_ids,
        'classCalendarIds': class_calendar_ids
    }

    cookie = headers.get('Cookie', '')
    s_utkn = _extract_from_cookie(cookie, 's_utkn')
    s_encuid = _extract_from_cookie(cookie, 's_encuid')

    rpt = _parse_rpt_data(cookie)
    grouptoken = rpt.get('grouptoken', 'US03')
    merchant_id = rpt.get('MerchantId', '')

    if not s_utkn:
        return {'status_code': 401, 'body': {'error': 's_utkn token not found in cookies'}}

    request_headers = {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "device": "Website",
        "grouptoken": grouptoken,
        "s_utkn": s_utkn,
        "merchantid": merchant_id,
        "userid": s_encuid or "",
        "origin": f"https://{grouptoken.lower()}.vagaro.com",
        "referer": f"https://{grouptoken.lower()}.vagaro.com/",
    }

    response = requests.post(
        f"https://api.vagaro.com/{grouptoken}/api/v3/merchants/calendar/appointments/retrieve",
        json=payload,
        headers=request_headers,
        impersonate="chrome131",
        timeout=30,
    )

    if response.status_code == 204:
        return {
            'status_code': 200,
            'body': {'appointments': [], 'count': 0}
        }

    if response.status_code != 200:
        try:
            body = response.json()
        except Exception:
            body = {'raw': response.text[:500]}
        return {
            'status_code': response.status_code,
            'body': body,
        }

    result = response.json()

    if result.get('responseCode') == 1001 or result.get('status') == 401:
        return {'status_code': 401, 'body': {'error': 'Authentication failed'}}

    if result.get('responseCode') != 1000:
        return {'status_code': response.status_code, 'body': {'error': result.get('message', 'Unknown error')}}

    appointments = []
    for appt in result.get('data', []):
        appointments.append({
            'id': appt.get('id'),
            'confirmationId': appt.get('appConfirmUniqueId'),
            'date': appt.get('date'),
            'startTime': appt.get('startTime'),
            'endTime': appt.get('endTime'),
            'duration': appt.get('duration'),
            'status': appt.get('status'),
            'customer': {
                'id': appt.get('custId'),
                'name': appt.get('custName'),
                'hashId': appt.get('custHashId')
            },
            'serviceProvider': {
                'id': appt.get('serviceProviderId'),
                'name': appt.get('spName'),
                'calendarId': appt.get('calId')
            },
            'service': {
                'id': appt.get('serviceId'),
                'color': appt.get('color')
            },
            'eventType': appt.get('event'),
            'isPaid': appt.get('prepaid'),
            'isRecurring': appt.get('recurring'),
            'isMembership': appt.get('membership'),
            'isPackage': appt.get('package'),
            'comment': appt.get('poComments'),
            'ptoText': appt.get('ptoText'),
            'hasNote': appt.get('note'),
            'hasPopupNote': appt.get('popupNote'),
            'formsCount': appt.get('formsCount'),
            'addonCount': appt.get('addonCount'),
            'checkIn': appt.get('checkIn'),
            'approved': appt.get('approved'),
            'resourceId': appt.get('resourceId'),
            'priceLabel': appt.get('priceLabel')
        })

    return {
        'status_code': 200,
        'body': {'appointments': appointments, 'count': len(appointments)}
    }
