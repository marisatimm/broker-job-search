from flask import Flask, request, jsonify
from serpapi import GoogleSearch
from datetime import datetime, timedelta
import re
import os

app = Flask(__name__)

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "DEIN-SERPAPI-KEY-HIER")


def parse_date(posted_at):
    today = datetime.now()
    if not posted_at:
        return today.strftime("%Y-%m-%d")
    match = re.search(r"(\d+)\s*Tag", posted_at)
    if match:
        days = int(match.group(1))
        return (today - timedelta(days=days)).strftime("%Y-%m-%d")
    match = re.search(r"(\d+)\s*Stunde", posted_at)
    if match:
        return today.strftime("%Y-%m-%d")
    match = re.search(r"(\d+)\s*Woche", posted_at)
    if match:
        weeks = int(match.group(1))
        return (today - timedelta(weeks=weeks)).strftime("%Y-%m-%d")
    match = re.search(r"(\d+)\s*Monat", posted_at)
    if match:
        months = int(match.group(1))
        return (today - timedelta(days=months * 30)).strftime("%Y-%m-%d")
    return today.strftime("%Y-%m-%d")


def get_best_link(job):
    for option in job.get("apply_options", []):
        if "jobs.ch" in option.get("link", ""):
            return option["link"]
    if job.get("apply_options"):
        return job["apply_options"][0]["link"]
    return job.get("share_link", "")


def is_matching_company(company_name, broker_name):
    """Prueft ob der Firmenname zum gesuchten Broker passt."""
    company = company_name.lower().strip()
    broker = broker_name.lower().strip()

    suffixes = [" ag", " gmbh", " sa", " ltd", " inc", " co", " & co",
                " schweiz", " switzerland", " holding"]
    company_clean = company
    broker_clean = broker
    for suffix in suffixes:
        company_clean = company_clean.replace(suffix, "").strip()
        broker_clean = broker_clean.replace(suffix, "").strip()

    broker_core = broker_clean.split()[0] if broker_clean.split() else broker_clean

    if broker_clean in company_clean:
        return True
    if company_clean in broker_clean:
        return True
    if broker_core in company_clean and len(broker_core) > 3:
        return True

    return False


@app.route("/search", methods=["GET"])
def search_jobs():
    broker_name = request.args.get("broker_name", "")
    if not broker_name:
        return jsonify({"error": "broker_name is required"}), 400

    query = request.args.get("query", f"{broker_name} Schweiz")
    location = request.args.get("location", "Switzerland")
    language = request.args.get("hl", "de")
    filter_company = request.args.get("filter_company", "true").lower() == "true"

    params = {
        "engine": "google_jobs",
        "q": query,
        "location": location,
        "hl": language,
        "api_key": SERPAPI_KEY
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()

        jobs = []
        skipped = 0
        for job in results.get("jobs_results", []):
            company_name = job.get("company_name", "")

            if filter_company and not is_matching_company(company_name, broker_name):
                skipped += 1
                continue

            posted_at = job.get("detected_extensions", {}).get("posted_at", "")
            jobs.append({
                "search_date": datetime.now().strftime("%Y-%m-%d"),
                "broker": broker_name,
                "title": job.get("title", ""),
                "company_name": company_name,
                "location": job.get("location", ""),
                "published_date": parse_date(posted_at),
                "posted_at_raw": posted_at,
                "source": job.get("via", ""),
                "url": get_best_link(job),
                "schedule_type": job.get("detected_extensions", {}).get("schedule_type", "")
            })

        return jsonify({
            "broker": broker_name,
            "query": query,
            "total_results": len(jobs),
            "skipped_other_companies": skipped,
            "jobs": jobs
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
