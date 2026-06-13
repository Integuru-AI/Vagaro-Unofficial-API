# Vagaro Unofficial API

Unofficial Python integrations for Vagaro.

## Integrations

- `vagaro_get_customers.py` - `get_customers` (133,382 live events).
- `vagaro_get_appointments.py` - `get_appointments` (18,831 live events).
- `vagaro_get_customer_all_data.py` - `get_customer_all_data` (16,366 live events).
- `vagaro_get_transactions.py` - `get_transactions` (3,370 live events).

## Usage

Each file exposes a `run(input, context)` entrypoint. The runtime is expected to provide:

- `input`: integration-specific request fields.
- `context["headers"]`: authenticated request headers when required.
- `context["base_url"]`: the platform base URL when overriding the default.

Install dependencies:

```bash
pip install -r requirements.txt
```

## Info

This unofficial API is built by [Integuru.ai](https://integuru.ai/).

For custom requests or hosted authentication, contact richard@taiki.online.

See the [complete list of APIs by Integuru](https://github.com/Integuru-AI/APIs-by-Integuru).
