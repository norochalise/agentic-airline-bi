from agentic_bi.api.charts import build_charts

PERFORMANCE_RESULT = {
    "dataset": "Delta-marketed domestic flights, July 2026",
    "metric": "on_time_arrival_rate",
    "unit": "percent",
    "group_by": "route",
    "order": "lowest",
    "filters": {"origin": "ATL", "destination": None, "only": None},
    "minimum_flights": 100,
    "results": [
        {"group": "ATL-EWR", "flights": 256, "value": 48.44},
        {"group": "ATL-DCA", "flights": 330, "value": 51.52},
    ],
}


def test_performance_result_becomes_a_titled_bar_chart():
    (chart,) = build_charts(
        [{"tool": "rank_flight_performance", "result": PERFORMANCE_RESULT}]
    )

    assert chart.title == "On-time arrival rate by route"
    # Airport codes keep their case in the subtitle.
    assert chart.subtitle == "From ATL, at least 100 flights"
    assert chart.unit == "percent"
    assert [(row.label, row.value, row.detail) for row in chart.rows] == [
        ("ATL-EWR", 48.44, "256 flights"),
        ("ATL-DCA", 51.52, "330 flights"),
    ]


def test_origin_cancellation_result_is_charted():
    result = {
        "dataset": "Delta-marketed domestic flights, July 2026",
        "minimum_flights": 1000,
        "top_n": 2,
        "results": [
            {
                "Origin": "LGA",
                "total_flights": 7378,
                "cancelled_flights": 843.0,
                "cancellation_rate": 11.4258,
            },
            {
                "Origin": "JFK",
                "total_flights": 5027,
                "cancelled_flights": 542.0,
                "cancellation_rate": 10.7817,
            },
        ],
    }

    (chart,) = build_charts(
        [{"tool": "analyze_top_origin_cancellation_rates", "result": result}]
    )

    assert chart.rows[0].value == 11.43
    assert chart.rows[0].detail == "843 of 7,378 flights cancelled"


def test_delay_causes_give_two_charts():
    result = {
        "dataset": "Delta-marketed domestic flights, July 2026",
        "filters": {"origin": None, "destination": None, "operating_carrier": None},
        "flights": 10,
        "delayed_flights_with_causes": 4,
        "delay_causes": [
            {"cause": "carrier", "minutes": 300.0, "share_percent": 75.0},
            {"cause": "weather", "minutes": 100.0, "share_percent": 25.0},
        ],
        "cancelled_flights": 2,
        "cancellation_reasons": [
            {"reason": "weather", "flights": 1, "share_percent": 50.0},
            {"reason": "carrier", "flights": 1, "share_percent": 50.0},
        ],
    }

    charts = build_charts([{"tool": "analyze_delay_causes", "result": result}])

    assert [chart.title for chart in charts] == [
        "Share of delay minutes by cause",
        "Cancellations by reason",
    ]
    assert charts[0].rows[0].label == "Carrier"


def test_single_rows_and_non_data_tools_are_not_charted():
    single = dict(PERFORMANCE_RESULT, results=PERFORMANCE_RESULT["results"][:1])

    assert build_charts([{"tool": "rank_flight_performance", "result": single}]) == []
    assert build_charts([{"tool": "search_private_knowledge", "result": {}}]) == []
