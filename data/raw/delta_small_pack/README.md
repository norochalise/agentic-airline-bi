# Delta Agentic BI: small source pack

Collected 2026-09-25. This pack has four documents and one flight-level CSV. It is a snapshot for a learning and portfolio project, not a live policy reference.

| File | Original source | Use |
| --- | --- | --- |
| `documents/delta_2025_form_10k.pdf` | [Delta Investor Relations, 2025 annual Form 10-K](https://s2.q4cdn.com/181345880/files/doc_downloads/annual/2026/DAL-12-31-2025-10K.pdf) | Company strategy, financials, business and operational risks; document retrieval. |
| `documents/delta_domestic_contract_plain_language_2026-08-18.pdf` | [Delta U.S. Contract of Carriage page](https://www.delta.com/us/en/legal/contract-of-carriage-dgr) and its [linked PDF](https://www.delta.com/content/dam/delta-www/pdfs/dl-dgr-master-18aug26.pdf) | Domestic carriage rules; policy retrieval and comparison. This is Delta's linked plain-language PDF, last modified August 18, 2026. |
| `documents/delta_customer_service_plan_2026-09-25.txt` | [Delta Customer Service Plan](https://www.delta.com/us/en/legal/customer-commitment) | Customer commitments; retrieval. Text of the official web page captured September 25, 2026; the page itself states effective October 24, 2024. |
| `documents/dot_september_2026_atcr_july_data.pdf` | [U.S. DOT September 2026 Air Travel Consumer Report](https://www.transportation.gov/sites/dot.gov/files/2026-09/September%202026%20ATCR%20revised%209-22-2026.pdf) | Government service-quality and complaint tables; evidence retrieval. The report includes July 2026 data, but some quarterly tables cover a different period. |
| `flights/delta_marketing_flights_2026_07.csv` | [BTS TranStats Marketing Carrier On-Time Performance](https://www.transtats.bts.gov/DL_SelectFields.aspx?QO_fu146_anzr=&gnoyr_VQ=FGK), July 2026 [official monthly ZIP](https://transtats.bts.gov/PREZIP/On_Time_Marketing_Carrier_On_Time_Performance_Beginning_January_2018_2026_7.zip) | Python and pandas tools; delays, cancellations, airports and routes. |

## Flight extract

The official monthly BTS ZIP contained 697,754 flights. We kept all 149,051 rows where `IATA_Code_Marketing_Airline == "DL"`, for July 1–31, 2026, and only these 17 source columns:

`FlightDate`, `IATA_Code_Marketing_Airline`, `IATA_Code_Operating_Airline`, `Flight_Number_Marketing_Airline`, `Origin`, `Dest`, `DepDelayMinutes`, `ArrDelayMinutes`, `Cancelled`, `CancellationCode`, `Diverted`, `CarrierDelay`, `WeatherDelay`, `NASDelay`, `SecurityDelay`, `LateAircraftDelay`, `Distance`.

These are **Delta-marketed domestic flights**, including flights operated by partner airlines; `IATA_Code_Operating_Airline` distinguishes them. Delay-cause fields may be empty for flights where BTS does not report a cause. Keep cancelled and diverted flights in the denominator only when appropriate for the metric. One month supports a cross-sectional case study, not claims about trends or causal effects. The DOT report's tables need to be matched by their stated period and carrier definition before comparison.

The large all-airline monthly ZIP was used only to prepare the extract and is deliberately excluded from this pack. Preserve the CSV as the reproducible working extract; the URL above identifies the original source.
