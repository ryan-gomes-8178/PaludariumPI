from math import isfinite


def summarize_sensor_trend(readings, start, end, buckets=100):
    """Summarize ordered readings and retain each time bucket's low and high."""
    start_timestamp = start.timestamp()
    end_timestamp = end.timestamp()
    bucket_width = (end_timestamp - start_timestamp) / buckets
    points = []
    first = last = low = high = None
    current_bucket = -1
    count = total = 0
    minimum, maximum = float("inf"), float("-inf")

    def append(point):
        if point is not None and (not points or point != points[-1]):
            points.append(point)

    for timestamp, value in readings:
        if not isfinite(value):
            continue

        point = {"timestamp": timestamp.timestamp(), "value": value}
        if first is None:
            first = point
            append(first)
        last = point
        index = min(buckets - 1, int((point["timestamp"] - start_timestamp) / bucket_width))
        if index != current_bucket:
            if low is not None:
                for sample in sorted((low, high), key=lambda item: item["timestamp"]):
                    append(sample)
            current_bucket = index
            low = high = point

        if value < low["value"]:
            low = point
        if value > high["value"]:
            high = point
        minimum, maximum = min(minimum, value), max(maximum, value)
        count += 1
        total += value

    if low is not None:
        for sample in sorted((low, high), key=lambda item: item["timestamp"]):
            append(sample)
        append(last)

    return {
        "points": points,
        "summary": {"min": minimum, "max": maximum, "mean": total / count, "count": count} if count else None,
        "start": start_timestamp,
        "end": end_timestamp,
    }
