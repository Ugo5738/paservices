import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from firecrawl import FirecrawlApp

# ----------------------------
# Utilities
# ----------------------------


def read_json(path: str) -> Any:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def looks_like_uk_postcode(text: str) -> bool:
    # Not perfect, but good enough for validating extracted field shapes.
    # Example: SW1A 1AA, M1 1AE, B33 8TH
    pattern = r"\b([A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2})\b"
    return re.search(pattern, (text or "").upper()) is not None


def normalize_price_obj(price: Any) -> Any:
    """
    Ensure price is either null or an object with keys:
    raw, value, currency, frequency.
    Attempt to parse value if raw exists.
    """
    if price is None:
        return None
    if isinstance(price, str):
        # If LLM gave just a string, convert to {raw: ...}
        price = {"raw": price}

    if not isinstance(price, dict):
        return None

    raw = price.get("raw")
    value = price.get("value")

    if value is None and isinstance(raw, str):
        # Extract number-ish from raw (e.g. "£650,000" or "£2,500 pcm")
        m = re.search(r"([0-9][0-9,\.]*)", raw.replace(",", ""))
        if m:
            try:
                value = float(m.group(1))
            except ValueError:
                value = None

    out = {
        "raw": raw if isinstance(raw, str) else None,
        "value": value,
        "currency": (
            price.get("currency") if isinstance(price.get("currency"), str) else None
        ),
        "frequency": (
            price.get("frequency") if isinstance(price.get("frequency"), str) else None
        ),
    }

    # If everything is null, return null
    if all(v is None for v in out.values()):
        return None

    return out


def clean_features(features: Any) -> Optional[List[str]]:
    if features is None:
        return None
    if isinstance(features, str):
        # Sometimes the model returns a newline string
        parts = [x.strip("-• \t") for x in features.splitlines() if x.strip()]
        return parts or None
    if isinstance(features, list):
        cleaned = []
        for item in features:
            if isinstance(item, str) and item.strip():
                cleaned.append(item.strip())
        return cleaned or None
    return None


def normalize_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize one extracted property object to match the schema shape.
    """
    out = dict(rec)

    # Ensure url is present
    if not out.get("url") and isinstance(out.get("source_url"), str):
        out["url"] = out["source_url"]

    # Normalize price object
    out["price"] = normalize_price_obj(out.get("price"))

    # Normalize features
    out["features"] = clean_features(out.get("features"))

    # Postcode sanity check: keep if it looks like a UK postcode else null
    pc = out.get("postcode")
    if isinstance(pc, str) and pc.strip():
        out["postcode"] = pc.strip()
        if not looks_like_uk_postcode(out["postcode"]):
            # Don’t delete it blindly; but if it's clearly not a postcode, null it.
            # If you want to keep it anyway, remove this block.
            out["postcode"] = None
    else:
        out["postcode"] = None

    # Coerce ints when possible
    for k in ("bedrooms", "bathrooms"):
        v = out.get(k)
        if isinstance(v, float) and v.is_integer():
            out[k] = int(v)
        elif isinstance(v, str):
            try:
                out[k] = int(re.search(r"\d+", v).group(0))  # type: ignore
            except Exception:
                out[k] = None

    return out


@dataclass
class JobConfig:
    mode: str
    output: str
    prompt: str
    schema_path: str
    urls: Optional[List[str]] = None
    only_main_content: bool = True
    agent: Optional[Dict[str, Any]] = None


def load_job_config(path: str) -> JobConfig:
    raw = read_json(path)

    mode = raw.get("mode")
    if mode not in ("extract", "agent"):
        raise ValueError("job config 'mode' must be 'extract' or 'agent'")

    output = raw.get("output") or "output/result.json"
    prompt = raw.get("prompt")
    schema_path = raw.get("schema_path")

    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("job config must include a non-empty 'prompt' string")
    if not isinstance(schema_path, str) or not schema_path.strip():
        raise ValueError("job config must include 'schema_path'")

    urls = raw.get("urls")
    if mode == "extract":
        if not isinstance(urls, list) or not urls:
            raise ValueError("extract mode requires a non-empty 'urls' list")

    only_main_content = bool(raw.get("only_main_content", True))
    agent = raw.get("agent") if mode == "agent" else None

    return JobConfig(
        mode=mode,
        output=output,
        prompt=prompt,
        schema_path=schema_path,
        urls=urls,
        only_main_content=only_main_content,
        agent=agent,
    )


# ----------------------------
# Firecrawl runners
# ----------------------------


def run_extract(
    app: FirecrawlApp, job: JobConfig, schema: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Batch extract mode: you provide the listing URLs, Firecrawl extracts JSON per schema.
    """
    assert job.urls is not None

    # firecrawl-py extract signature may differ by version; this follows common usage.
    # If your installed SDK uses different parameter names, adjust here only.
    res = app.extract(urls=job.urls, prompt=job.prompt, schema=schema)

    return {"mode": "extract", "input_urls": job.urls, "raw_response": res}


def run_agent(
    app: FirecrawlApp, job: JobConfig, schema: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Agent mode: Firecrawl navigates/searches and returns extracted JSON.
    You can constrain it via job.agent.urls and strictConstrainToUrls.
    """
    agent_cfg = job.agent or {}

    # Normalize agent options
    max_credits = agent_cfg.get("maxCredits")
    urls = agent_cfg.get("urls")
    strict = agent_cfg.get("strictConstrainToUrls")

    # firecrawl-py agent signature can vary; this is a typical pattern.
    # If your SDK uses different structure, adjust here only.
    res = app.agent(
        prompt=job.prompt,
        schema=schema,
        max_credits=max_credits,
        urls=urls,
        strict_constrain_to_urls=strict,
    )

    return {"mode": "agent", "agent_config": agent_cfg, "raw_response": res}


def extract_records_from_response(raw_response: Any) -> List[Dict[str, Any]]:
    """
    Tries to find extracted JSON objects from the SDK response.
    Firecrawl responses can vary by endpoint/SDK version:
    - sometimes data is at res["data"]
    - sometimes at res["json"] or res["data"]["json"]
    - sometimes agent returns array directly
    """
    if raw_response is None:
        return []

    # If response is already list of dicts
    if isinstance(raw_response, list):
        return [x for x in raw_response if isinstance(x, dict)]

    if not isinstance(raw_response, dict):
        return []

    # Common patterns
    candidates: List[Any] = []

    # Direct "data"
    if "data" in raw_response:
        candidates.append(raw_response["data"])

    # Some SDKs nest under "data" then "json"
    if isinstance(raw_response.get("data"), dict) and "json" in raw_response["data"]:
        candidates.append(raw_response["data"]["json"])

    # Direct "json"
    if "json" in raw_response:
        candidates.append(raw_response["json"])

    # Agent sometimes returns "results" or "output"
    for key in ("results", "output", "extracted", "items"):
        if key in raw_response:
            candidates.append(raw_response[key])

    # Flatten candidates to a list of dicts
    records: List[Dict[str, Any]] = []
    for c in candidates:
        if isinstance(c, dict):
            # Could be one record or a map containing list
            # If it looks like a property record (has url/address/price), keep it
            if any(k in c for k in ("url", "address", "price", "bedrooms")):
                records.append(c)
            # Or it might contain list under a common key
            for k in ("properties", "listings", "items", "data"):
                if isinstance(c.get(k), list):
                    records.extend([x for x in c[k] if isinstance(x, dict)])
        elif isinstance(c, list):
            records.extend([x for x in c if isinstance(x, dict)])

    # De-dup by url if present
    seen = set()
    out = []
    for r in records:
        u = r.get("url")
        key = u if isinstance(u, str) else json.dumps(r, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(r)

    return out


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Config-driven Firecrawl extraction")
    parser.add_argument(
        "--job",
        required=True,
        help="Path to job config JSON (e.g. configs/job.example.json)",
    )
    args = parser.parse_args()

    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing FIRECRAWL_API_KEY. Create a .env from .env.example."
        )

    job = load_job_config(args.job)
    schema = read_json(job.schema_path)

    app = FirecrawlApp(api_key=api_key)

    if job.mode == "extract":
        run = run_extract(app, job, schema)
    else:
        run = run_agent(app, job, schema)

    raw_response = run.get("raw_response")
    try:
        run["raw_response"] = json.loads(json.dumps(raw_response, default=str))
    except Exception:
        run["raw_response"] = str(raw_response)

    records = extract_records_from_response(raw_response)
    normalized = [normalize_record(r) for r in records]

    final = {
        "job": {
            "mode": job.mode,
            "output": job.output,
            "schema_path": job.schema_path,
            "only_main_content": job.only_main_content,
        },
        "run": run,
        "extracted_count": len(normalized),
        "properties": normalized,
    }

    write_json(job.output, final)
    print(json.dumps(final, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
