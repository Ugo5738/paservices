"""
Utility functions for mapping between API response data and database models
for Rightmove property data.
"""

import json
from typing import Any, Dict, List, Optional

from sqlalchemy import String, Text


def camel_to_snake(name: str) -> str:
    """Convert camelCase string to snake_case."""
    import re

    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def map_property_data(data: Dict[str, Any], model_class) -> Dict[str, Any]:
    """
    Map API response data to ORM model fields by checking the column attributes.

    Args:
        data: API response data (usually in camelCase)
        model_class: The SQLAlchemy model class

    Returns:
        Dict with keys matching the ORM model attributes
    """
    result = {}

    # Get model attributes and their corresponding column names
    # This maps python attribute names to SQL column names
    model_columns = {}
    column_types = {}
    for column_attr in model_class.__table__.columns:
        # If there's a specified name in the Column definition, use it
        # Otherwise use the attribute name
        attr_name = column_attr.name
        if hasattr(column_attr, "name") and getattr(column_attr, "name") != attr_name:
            sql_name = getattr(column_attr, "name")
        else:
            sql_name = attr_name
        model_columns[attr_name] = sql_name
        column_types[attr_name] = column_attr.type

    # Try different mappings for each field in data
    for key, value in data.items():
        target_key = None
        # First check if the key exists directly in model
        if key in model_columns:
            target_key = key
        # Then try snake_case version of camelCase key
        else:
            snake_key = camel_to_snake(key)
            if snake_key in model_columns:
                target_key = snake_key

        if target_key:
            # Check if we need to serialize a dict/list to JSON string
            if isinstance(value, (dict, list)) and isinstance(
                column_types[target_key], (String, Text)
            ):
                try:
                    result[target_key] = json.dumps(value)
                except (TypeError, ValueError):
                    # Fallback if serialization fails, though unlikely for API data
                    result[target_key] = str(value)
            else:
                result[target_key] = value

    return result


def map_nested_data(
    data: Dict[str, Any], model_mapping: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """
    Map nested API response data to ORM models for relationships.

    Args:
        data: API response data (usually in camelCase)
        model_mapping: Dict mapping from data keys to model classes

    Returns:
        Dict with keys matching the relationship names and values as mapped data
    """
    result = {}

    for data_key, model_class in model_mapping.items():
        if data_key in data and data[data_key] is not None:
            result[data_key] = map_property_data(data[data_key], model_class)

    return result
