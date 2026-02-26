import csv
import json
import os
import re
import unicodedata
from typing import Any, Dict, List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


STATIC_DATA_URLS = [
    "https://cdn.tsetmc.com/api/StaticData/GetStaticData",
    "http://cdn.tsetmc.com/api/StaticData/GetStaticData",
]

RELATED_COMPANY_URLS = [
    "https://cdn.tsetmc.com/api/ClosingPrice/GetRelatedCompany/{code}",
    "http://cdn.tsetmc.com/api/ClosingPrice/GetRelatedCompany/{code}",
]


def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("\u200c", " ").replace("\u200f", " ").replace("\u200e", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def slugify(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"[^\w\s\-]+", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", "_", text)
    return text[:120] if text else "unknown"


def first_key(d: Dict[str, Any], keys: List[str], default=None):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def make_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s


def get_json(session: requests.Session, urls: List[str], timeout: int = 30) -> Dict[str, Any]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }
    last_err = None
    for url in urls:
        try:
            r = session.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            try:
                return r.json()
            except Exception:
                return json.loads(r.text)
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"Failed to fetch JSON from all urls. Last error: {last_err}")


def load_industries(session: requests.Session) -> List[Dict[str, str]]:
    data = get_json(session, STATIC_DATA_URLS)
    items = data.get("staticData") or data.get("StaticData") or []

    industries: List[Dict[str, str]] = []
    for it in items:
        if not isinstance(it, dict):
            continue

        typ = first_key(it, ["type", "Type"], "")
        if typ != "IndustrialGroup":
            continue

        code = first_key(it, ["code", "Code"])
        if code is None:
            continue

        code_str = str(code).strip()
        if code_str.isdigit():
            code_str = code_str.zfill(2)

        name = first_key(
            it,
            ["name", "Name", "title", "Title", "lVal", "lval", "lTitle", "value", "Value"],
            f"IndustrialGroup_{code_str}",
        )
        name = normalize_text(str(name))

        industries.append({"code": code_str, "name": name})

    seen = set()
    out = []
    for x in industries:
        if x["code"] in seen:
            continue
        seen.add(x["code"])
        out.append(x)

    return out


def load_companies_for_industry(session: requests.Session, industry_code: str) -> List[Dict[str, str]]:
    urls = [u.format(code=industry_code) for u in RELATED_COMPANY_URLS]
    data = get_json(session, urls)

    rows = data.get("relatedCompany") or data.get("RelatedCompany") or []
    companies: List[Dict[str, str]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        instr = row.get("instrument") or row.get("Instrument") or row
        if not isinstance(instr, dict):
            continue

        ins_code = first_key(instr, ["insCode", "InsCode", "i", "Id", "id"])
        symbol = first_key(instr, ["lVal18AFC", "lVal18", "symbol", "Symbol"])
        name = first_key(instr, ["lVal30", "lSoc30", "lVal30AFC", "name", "Name"])

        if ins_code is None or symbol is None:
            continue

        ins_code = str(ins_code).strip()
        symbol = normalize_text(str(symbol))
        name = normalize_text(str(name)) if name is not None else ""

        companies.append({"id": ins_code, "symbol": symbol, "name": name})

    seen = set()
    out = []
    for c in companies:
        if c["id"] in seen:
            continue
        seen.add(c["id"])
        out.append(c)

    return out


def ensure_unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 2
    while True:
        p = f"{base}_{i}{ext}"
        if not os.path.exists(p):
            return p
        i += 1


def write_industry_csv(industry_name: str, companies: List[Dict[str, str]], out_dir: str = "industries") -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{slugify(industry_name)}.csv")
    path = ensure_unique_path(path)

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "symbol", "name"])
        for c in companies:
            w.writerow([c["id"], c["symbol"], c["name"]])

    return path


def write_all_csv(rows: List[Dict[str, str]], path: str = "all_companies_with_industry.csv") -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["industry", "id", "symbol", "name"])
        for r in rows:
            w.writerow([r["industry"], r["id"], r["symbol"], r["name"]])


def main():
    session = make_session()
    industries = load_industries(session)

    if not industries:
        print("No industries found.")
        return

    all_rows: List[Dict[str, str]] = []

    for idx, ind in enumerate(industries, start=1):
        code = ind["code"]
        name = ind["name"]

        companies = load_companies_for_industry(session, code)
        if not companies:
            continue

        out_path = write_industry_csv(name, companies, out_dir="industries")

        for c in companies:
            all_rows.append({"industry": name, "id": c["id"], "symbol": c["symbol"], "name": c["name"]})

        print(f"[{idx}/{len(industries)}] {name} ({code}) -> {len(companies)} | {out_path}")

    if all_rows:
        write_all_csv(all_rows, "all_companies_with_industry.csv")
        print(f"ALL -> all_companies_with_industry.csv | total: {len(all_rows)}")
    else:
        print("No companies collected.")


if __name__ == "__main__":
    main()