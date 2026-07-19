# Supertri — Marketing Registration Dashboard

External, agency-shareable dashboard of **registration** insights — **no revenue or financial data**.
Deployed as a public Streamlit app protected by a shared password.

- **Main file:** `app_marketing.py`
- **Data:** reads BigQuery **only** through the revenue-free `supertri_marketing.*` views, via a service
  account (`marketing-dashboard@…`) scoped to that dataset alone — so this app physically cannot reach
  revenue, even with a bug. This repo therefore contains **no credentials and no financial logic**.
- **Access control:** a password gate (`app_password` secret) — the app blocks everyone until the correct
  password is entered, and **fails closed** if the secret is missing.

## Sections
Registrations vs plan · Registration ramps (plan vs last year) · Participant profile · Athlete mix ·
Event format mix · Returning rate.

## Deploy (Streamlit Community Cloud)
1. Deploy this **public** repo → main file `app_marketing.py`.
2. In **Settings → Secrets**, paste the `[gcp_service_account]` block (the marketing SA key) and add an
   `app_password = "…"` line at the top. See `.streamlit/secrets.toml.example`.

## Local dev
`streamlit run app_marketing.py` (uses your Google application-default credentials; the password gate is
skipped locally). Requires the deps in `requirements.txt`.

## Note
This is a snapshot of the marketing app. The `data.py` here is a **slim, revenue-free** subset of the
main analytics repo's data layer (constants + the BigQuery query helper only).
