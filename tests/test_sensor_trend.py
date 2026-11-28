from datetime import datetime, timedelta, timezone

from terrariumTrend import summarize_sensor_trend


START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_trend_keeps_extremes_in_timestamp_order_with_exact_statistics():
    readings = [(START + timedelta(minutes=index), float(index % 8)) for index in range(1000)]
    readings[303] = (readings[303][0], 86.0)
    readings[309] = (readings[309][0], -7.0)
    result = summarize_sensor_trend(readings, START, START + timedelta(minutes=999))

    points = result["points"]
    assert len(points) <= 202
    assert points[0]["timestamp"] == readings[0][0].timestamp()
    assert points[-1]["timestamp"] == readings[-1][0].timestamp()
    assert [point["timestamp"] for point in points] == sorted({point["timestamp"] for point in points})
    assert {86.0, -7.0} <= {point["value"] for point in points}
    assert result["summary"] == {
        "min": -7.0,
        "max": 86.0,
        "mean": sum(value for _, value in readings) / 1000,
        "count": 1000,
    }


def test_empty_and_single_point_trends():
    end = START + timedelta(hours=1)
    assert summarize_sensor_trend([], START, end)["summary"] is None
    result = summarize_sensor_trend([(START, float("inf")), (end, 0.0)], START, end)
    assert result["points"] == [{"timestamp": end.timestamp(), "value": 0.0}]
    assert result["summary"] == {"min": 0.0, "max": 0.0, "mean": 0.0, "count": 1}
