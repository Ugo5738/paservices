def analyze_response(raw_data: dict | None) -> tuple[int, int]:
    """
    Analyzes a raw API response to count total and null items.

    Returns:
        A tuple of (total_item_count, null_item_count).
    """
    if not isinstance(raw_data, dict) or "data" not in raw_data:
        return 0, 0

    data_content = raw_data.get("data")
    if data_content is None:
        # The entire 'data' object is null
        return 1, 1

    if isinstance(data_content, list):
        total_count = len(data_content)
        null_count = sum(1 for item in data_content if item is None)
        return total_count, null_count

    if isinstance(data_content, dict):
        total_count = len(data_content)
        null_count = sum(1 for value in data_content.values() if value is None)
        return total_count, null_count

    # If data is a single non-null, non-collection value
    return 1, 0
