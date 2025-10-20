"""MCP metadata: resources and prompt templates for AI agents.

This module exposes a small catalog of available resources and prompt
templates to help agents discover and use the MCP tools safely.
"""

from typing import Dict, List

TOOLS = [
    {
        "name": "trigger_property_scrape",
        "description": "Trigger the Data Capture service to scrape a property URL.",
        "params": ["property_url", "super_id (optional)"],
        "required_scope": "mcp:tools:data-capture",
    },
    {
        "name": "trigger_floorplan_analysis_tool",
        "description": "Start floorplan analysis for a single floorplan.",
        "params": [
            "floorplan_key",
            "floorplan_url",
            "super_id (optional)",
            "property_id",
        ],
        "required_scope": "mcp:tools:floorplan",
    },
    {
        "name": "create_super_id_tool",
        "description": "Generate a new super_id for tracing workflows.",
        "params": ["prefix"],
        "required_scope": "mcp:tools:super-id",
    },
    {
        "name": "list_properties_tool",
        "description": "List recent properties captured by the data capture service.",
        "params": [
            "on_date",
            "from_time",
            "to_time",
            "min_bedrooms",
            "max_bedrooms",
            "min_bathrooms",
            "max_bathrooms",
        ],
        "required_scope": "mcp:tools:data-capture:read",
    },
]


PROMPT_TEMPLATES: Dict[str, str] = {
    "start_property_scrape": (
        "Use the trigger_property_scrape tool to start scraping the property. "
        "Provide property_url and optionally supply or omit super_id to auto-generate one."
    ),
    "start_floorplan_analysis": (
        "Use the trigger_floorplan_analysis_tool to initiate floorplan analysis. "
        "Provide floorplan_key, floorplan_url and property_id. If super_id is omitted, the system will create one."
    ),
}


def resources() -> List[Dict]:
    """Return the tool catalog for discovery by clients or agents."""
    return TOOLS


def prompts() -> Dict[str, str]:
    """Return prompt templates to guide agent behaviour."""
    return PROMPT_TEMPLATES
