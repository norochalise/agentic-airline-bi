# Data Analysis Skill

## Purpose

Analyze structured business data using deterministic computation and produce
evidence-based business insights.

## Use When

Use this skill when the user's request requires analysis of structured data
such as CSV, JSON, tabular files, operational datasets, or derived business
metrics.

Typical tasks include:

- calculating business metrics
- comparing groups, routes, airports, products, or time periods
- identifying high- and low-performing segments
- detecting unusual patterns or operational issues
- summarizing trends within the available dataset
- answering quantitative business questions

## Workflow

1. Clarify the business question and required output.
2. Inspect the available dataset and relevant schema.
3. Identify the fields required for the analysis.
4. Validate data types, missing values, and important data-quality constraints.
5. Select the appropriate analysis tool or deterministic Python operation.
6. Perform calculations using code rather than model-generated arithmetic.
7. Validate calculated results before interpretation.
8. Identify the most relevant patterns, comparisons, or exceptions.
9. Translate analytical results into concise business interpretation.
10. Report important limitations of the available data.

## Available Analyses

- `analyze_top_origin_cancellation_rates`: origin airports ranked by
  cancellation rate.
- `rank_flight_performance`: any other ranking or comparison. It covers
  origins, destinations, routes, operating carriers, dates and weekdays, and
  the metrics cancellation rate, on-time arrival rate, average arrival or
  departure delay, diversion rate and flight count. It can filter by origin
  or destination airport, and `only` compares named groups directly.
- `analyze_delay_causes`: why flights were late or cancelled, overall or for
  one airport or operating carrier.

Metric definitions follow the DOT Air Travel Consumer Report:

- A flight is on time when it is completed and arrives less than 15 minutes
  late; cancelled and diverted flights count as not on time.
- Average delays use completed flights, with early arrivals counted as zero.
- Delay causes are reported only for flights at least 15 minutes late.

The dataset covers Delta-marketed flights. The operating carrier codes are
DL (Delta mainline), OO (SkyWest), 9E (Endeavor Air) and YX (Republic).

## Analysis Principles

- Numerical results must come from tools or deterministic code.
- Do not invent values that are absent from the source data.
- Separate calculated facts from business interpretation.
- Use only fields relevant to the current question.
- Validate denominators and population definitions before calculating rates.
- Treat missing values explicitly rather than assuming zero.
- Avoid causal claims unless the available evidence supports them.
- Avoid long-term trend claims when the dataset covers only a limited period.
- Preserve important distinctions in the source data, such as marketing carrier
  versus operating carrier.

## Output Expectations

A completed analysis should normally contain:

1. the direct answer to the business question
2. the key calculated metrics
3. the most relevant supporting findings
4. a concise business interpretation
5. material data limitations or uncertainty

## Constraints

- Do not calculate business metrics mentally when an analysis tool is available.
- Do not modify source data unless the task explicitly requires transformation.
- Do not treat missing delay-cause values as confirmed zero delay contribution.
- Do not generalize beyond the population and time period represented by the data.
- Do not execute consequential write actions without explicit authorization.