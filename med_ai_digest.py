import os
import textwrap
import requests
import feedparser
from datetime import datetime, timezone, timedelta

NTFY_TOPIC = os.environ["NTFY_TOPIC"]
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

HEADERS = {
    "User-Agent": "med-ai-daily-digest/1.0"
}

TOP_JOURNAL_QUERY = """
(
  "artificial intelligence"[Title/Abstract]
  OR "machine learning"[Title/Abstract]
  OR "deep learning"[Title/Abstract]
  OR "large language model"[Title/Abstract]
  OR "large language models"[Title/Abstract]
  OR "foundation model"[Title/Abstract]
  OR "medical imaging"[Title/Abstract]
  OR "clinical decision support"[Title/Abstract]
  OR "digital health"[Title/Abstract]
)
AND
(
  "Nature Medicine"[Journal]
  OR "The Lancet Digital Health"[Journal]
  OR "JAMA"[Journal]
  OR "JAMA Network Open"[Journal]
  OR "BMJ"[Journal]
  OR "Science"[Journal]
  OR "Nature"[Journal]
  OR "Cell"[Journal]
  OR "NPJ Digital Medicine"[Journal]
  OR "Radiology"[Journal]
  OR "NEJM AI"[Journal]
)
"""

GENERAL_MED_AI_QUERY = """
(
  "medical artificial intelligence"[Title/Abstract]
  OR "healthcare artificial intelligence"[Title/Abstract]
  OR "large language model"[Title/Abstract]
  OR "foundation model"[Title/Abstract]
  OR "multimodal"[Title/Abstract]
  OR "clinical AI"[Title/Abstract]
)
"""


def pubmed_search(term, label, retmax=8, reldate=7):
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": term,
        "retmode": "json",
        "sort": "pub date",
        "retmax": retmax,
        "datetype": "pdat",
        "reldate": reldate,
    }

    r = requests.get(search_url, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    ids = r.json().get("esearchresult", {}).get("idlist", [])

    if not ids:
        return []

    summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    r = requests.get(
        summary_url,
        params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json().get("result", {})

    items = []
    for pmid in ids:
        article = data.get(pmid, {})
        title = article.get("title", "").strip().rstrip(".")
        journal = article.get("fulljournalname") or article.get("source", "")
        pubdate = article.get("pubdate", "")
        if title:
            items.append({
                "section": label,
                "title": title,
                "source": journal,
                "date": pubdate,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })

    return items


def arxiv_search():
    url = (
        "http://export.arxiv.org/api/query?"
        "search_query=all:%22large%20language%20model%22%20AND%20all:healthcare"
        "&start=0&max_results=8&sortBy=submittedDate&sortOrder=descending"
    )

    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:6]:
        title = entry.get("title", "").replace("\n", " ").strip()
        link = entry.get("link", "").strip()
        published = entry.get("published", "")[:10]
        summary = entry.get("summary", "").replace("\n", " ").strip()
        items.append({
            "section": "重要预印本",
            "title": title,
            "source": "arXiv",
            "date": published,
            "url": link,
            "summary": summary[:260],
        })
    return items


def format_digest(items):
    today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    sections = ["顶刊/高分论文", "近期医学 AI 论文", "重要预印本"]

    lines = [
        f"医学 AI 每日简报 | {today}",
        "",
        "筛选方向：医学大模型、影像 AI、临床决策支持、多模态医疗 AI、数字健康、药物研发相关 AI。",
        "",
    ]

    if not items:
        lines.append("今天没有检索到符合条件的新条目。")
        return "\n".join(lines)

    for section in sections:
        section_items = [x for x in items if x["section"] == section]
        if not section_items:
            continue

        lines.append(section)
        for i, item in enumerate(section_items, 1):
            lines.append(f"{i}. {item['title']}")
            lines.append(f"来源：{item.get('source', 'Unknown')}")
            if item.get("date"):
                lines.append(f"日期：{item['date']}")
            if item.get("summary"):
                lines.append(f"摘要：{item['summary']}")
            lines.append(item["url"])
            lines.append("")
    return "\n".join(lines)


def send_ntfy(message):
    chunks = textwrap.wrap(
        message,
        width=3800,
        replace_whitespace=False,
        drop_whitespace=False,
    )

    for idx, chunk in enumerate(chunks, 1):
        headers = {
            "Title": "医学 AI 每日简报" if idx == 1 else "医学 AI 每日简报（续）",
            "Tags": "microscope,robot",
            "Priority": "default",
        }
        r = requests.post(
            NTFY_URL,
            data=chunk.encode("utf-8"),
            headers=headers,
            timeout=30,
        )
        r.raise_for_status()


def main():
    items = []
    items.extend(pubmed_search(TOP_JOURNAL_QUERY, "顶刊/高分论文", retmax=10, reldate=14))
    items.extend(pubmed_search(GENERAL_MED_AI_QUERY, "近期医学 AI 论文", retmax=8, reldate=3))
    items.extend(arxiv_search())

    seen = set()
    deduped = []
    for item in items:
        key = item["title"].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    message = format_digest(deduped[:20])
    send_ntfy(message)


if __name__ == "__main__":
    main()
