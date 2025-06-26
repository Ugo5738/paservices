"""
Database utility functions to help bridge the gap between API responses and database models.
"""

from typing import Dict, Any, Optional, Type
import logging

logger = logging.getLogger(__name__)

def normalize_model_instance(model_class, data: dict) -> dict:
    """
    Normalizes data for a model instance by mapping API response field names to model attributes.
    Handles cases where SQLAlchemy model attributes differ from database column names
    due to the use of the 'name' parameter in Column definitions.
    
    Args:
        model_class: SQLAlchemy model class
        data: Dictionary of data to normalize
        
    Returns:
        Dict of normalized data that can be passed to the model constructor
    """
    # Create a copy to avoid modifying the original
    normalized_data = data.copy()
    
    # Extract column information directly from SQLAlchemy model
    # This includes the Python attribute name and the actual DB column name mapping
    model_columns = {}
    python_attr_to_db_column = {}
    db_column_to_python_attr = {}
    
    # Build a list of all valid attribute names from the model class
    model_attrs = set()
    
    # Create mappings between API fields and Python attributes
    # First create a mapping of both ways between Python attributes and DB column names
    for column in model_class.__table__.columns:
        python_attr = column.key  # Python attribute name as defined in the model (e.g., brand_name)
        db_column = column.name   # DB column name (e.g., brandName)
        
        # Add to our set of valid model attribute names
        model_attrs.add(python_attr)
        
        # Store info about each column
        model_columns[python_attr] = {
            'type': str(column.type),
            'db_column': db_column
        }
        
        # Create bidirectional maps (case-insensitive for easier matching)
        python_attr_to_db_column[python_attr.lower()] = db_column
        db_column_to_python_attr[db_column.lower()] = python_attr
    
    logger.debug(f"Model {model_class.__name__} has {len(model_columns)} columns")
    logger.debug(f"Python attributes for {model_class.__name__}: {sorted(model_attrs)[:5]}...")
    
    # Create a clean dictionary with the correct attribute names
    clean_values = {}
    unmapped_keys = []
    
    # Process all fields from the input data
    for api_field, value in normalized_data.items():
        # Don't process keys we've already mapped
        if api_field in clean_values:
            continue
            
        # 1. Direct exact match with model Python attribute
        if api_field in model_attrs:
            clean_values[api_field] = value
            logger.debug(f"Direct match: API field '{api_field}' -> model attr '{api_field}'")
            continue
            
        # 2. Try to match with DB column names (which may differ from Python attributes)
        api_field_lower = api_field.lower()
        if api_field_lower in db_column_to_python_attr:
            # Found a match where API field matches a DB column name
            attr_name = db_column_to_python_attr[api_field_lower]
            if attr_name not in clean_values:  # Don't overwrite direct matches
                logger.debug(f"DB column match: API field '{api_field}' -> model attr '{attr_name}'")
                clean_values[attr_name] = value
            continue
                
        # 3. Case-insensitive match with model attributes
        matching_attrs = [attr for attr in model_attrs if attr.lower() == api_field_lower]
        if matching_attrs:
            attr_name = matching_attrs[0]  # Use the first match
            if attr_name not in clean_values:
                logger.debug(f"Case-insensitive match: API field '{api_field}' -> model attr '{attr_name}'")
                clean_values[attr_name] = value
            continue
                
        # If we get here, we couldn't map this field at all
        unmapped_keys.append(api_field)
    
    # Log any unmapped keys
    if unmapped_keys:
        logger.debug(f"Unmapped keys for {model_class.__name__}: {unmapped_keys[:10]}...")
    
    # Special handling for known types
    for attr_name in list(clean_values.keys()):
        value = clean_values[attr_name]
        
        # Handle array fields
        if 'ARRAY' in model_columns.get(attr_name, {}).get('type', ''):
            if value is None:
                clean_values[attr_name] = []
            elif isinstance(value, str):
                clean_values[attr_name] = [value]
            elif not isinstance(value, list):
                try:
                    clean_values[attr_name] = list(value)
                except Exception as e:
                    logger.warning(f"Could not convert {attr_name} to list: {str(e)}, using empty list")
                    clean_values[attr_name] = []
        
        # Handle JSON/JSONB fields
        elif 'JSON' in model_columns.get(attr_name, {}).get('type', ''):
            if not isinstance(value, dict) and value is not None:
                try:
                    if isinstance(value, str):
                        import json
                        clean_values[attr_name] = json.loads(value)
                    else:
                        clean_values[attr_name] = dict(value)
                except Exception as e:
                    logger.warning(f"Could not convert {attr_name} to dict: {str(e)}, using empty dict")
                    clean_values[attr_name] = {}
    
    return clean_values
