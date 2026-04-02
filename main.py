#!/usr/bin/env python3
"""Daily English News Summary Generator using Gemini 2.5 Flash + Gmail SMTP"""

import os
import json
import re
import smtplib
import feedparser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from google import genai

# --- Configuration ---
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GMAIL_USER = os.environ["GMAIL_USER"]
# Strip non-ASCII/non-breaking spaces that can appear when copying app passwords
GMAIL_APP_PASSWORD = re.sub(r"[^\x20-\x7E]", " ", os.environ["GMAIL_APP_PASSWORD"]).strip()
RECIPIENT_EMAIL = "alsltar94@gmail.com"

# --- RSS Feeds by Category ---
RSS_FEEDS = {
    "IT/Tech": [
        "https://feeds.feedburner.com/TechCrunch/",
        "https://www.theverge.com/rss/index.xml",
        "https://www.wired.com/feed/rss",
    ],
    "Economy": [
        "https://www.cnbc.com/id/10001147/device/rss/rss.html",
        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "https://feeds.marketwatch.com/marketwatch/topstories/",
    ],
    "World": [
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://feeds.washingtonpost.com/rss/world",
    ],
}


def fetch_articles(feeds: list[str], count: int = 5) -> list[dict]:
    """Fetch recent articles from RSS feeds, returning up to `count` items."""
    articles = []
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                title = entry.get("title", "").strip()
                raw_summary = entry.get("summary", entry.get("description", "")).strip()
                # Strip HTML tags and truncate
                summary = re.sub(r"<[^>]+>", " ", raw_summary)
                summary = re.sub(r"\s+", " ", summary).strip()[:600]
                if title:
                    articles.append({"title": title, "summary": summary})
                if len(articles) >= count:
                    break
        except Exception as e:
            print(f"  Warning: could not fetch {feed_url}: {e}")
        if len(articles) >= count:
            break
    return articles


def generate_category_news(category: str, articles: list[dict]) -> dict:
    """Call Gemini to produce structured news summaries for a category."""
    client = genai.Client(api_key=GEMINI_API_KEY)

    if articles:
        articles_block = "\n\n".join(
            f"[{i+1}] Title: {a['title']}\n    Content: {a['summary']}"
            for i, a in enumerate(articles)
        )
        context = (
            f"Using the real news articles below as your source material:\n\n"
            f"{articles_block}\n\n"
            f"Select the 2-3 most newsworthy items and"
        )
    else:
        today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
        context = f"For today ({today}), generate"

    prompt = f"""{context} produce educational English news summaries for the "{category}" category.

Return ONLY a valid JSON object — no markdown fences, no extra text — with this exact schema:
{{
  "articles": [
    {{
      "title": "Clear and engaging English headline",
      "summary": "3-4 sentence summary in clear, natural English.",
      "vocabulary": [
        {{"word": "word1", "meaning": "part of speech: concise definition. Example: short usage sentence."}},
        {{"word": "word2", "meaning": "part of speech: concise definition. Example: short usage sentence."}},
        {{"word": "word3", "meaning": "part of speech: concise definition. Example: short usage sentence."}}
      ]
    }}
  ]
}}

Rules:
- Exactly 2-3 articles
- Each summary: 3-4 sentences, clear English
- Each article: exactly 3 vocabulary items
- Choose vocabulary that is academically or professionally valuable"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt
        )
        text = response.text.strip()
        # Strip accidental markdown code fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  JSON parse error for {category}: {e}")
        print(f"  Raw response (first 300 chars): {response.text[:300]}")
        return {"articles": []}
    except Exception as e:
        print(f"  Gemini API error for {category}: {e}")
        return {"articles": []}


def build_html_email(news_data: dict, date_str: str) -> str:
    """Build a styled HTML email from the structured news data."""

    category_style = {
        "IT/Tech":  ("#8e44ad", "#9b59b6", "💻"),
        "Economy":  ("#27ae60", "#2ecc71", "📈"),
        "World":    ("#c0392b", "#e74c3c", "🌍"),
    }

    articles_html = ""
    for category, data in news_data.items():
        header_color, border_color, emoji = category_style.get(
            category, ("#2c3e50", "#3498db", "📰")
        )
        articles_section = ""
        for article in data.get("articles", []):
            vocab_items = "".join(
                f"""<tr>
                      <td style="padding:4px 8px;font-weight:bold;color:#2c3e50;
                                 white-space:nowrap;vertical-align:top;">{v['word']}</td>
                      <td style="padding:4px 8px;color:#555;">{v['meaning']}</td>
                   </tr>"""
                for v in article.get("vocabulary", [])
            )
            articles_section += f"""
            <div style="border-left:4px solid {border_color};padding:16px 20px;
                        background:#f8f9fa;border-radius:0 8px 8px 0;margin-bottom:16px;">
              <div style="font-size:16px;font-weight:bold;color:#1a1a2e;margin-bottom:10px;">
                {article['title']}
              </div>
              <div style="color:#444;line-height:1.75;font-size:14px;margin-bottom:14px;">
                {article['summary']}
              </div>
              <div style="background:#eef6fb;padding:12px 16px;border-radius:6px;">
                <div style="font-size:11px;font-weight:bold;color:#2980b9;
                            text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">
                  📚 Key Vocabulary
                </div>
                <table style="border-collapse:collapse;width:100%;font-size:13px;">
                  {vocab_items}
                </table>
              </div>
            </div>"""

        articles_html += f"""
        <div style="margin-bottom:32px;">
          <div style="background:{header_color};color:white;padding:10px 16px;
                      border-radius:6px;font-size:15px;font-weight:bold;margin-bottom:14px;">
            {emoji}&nbsp; {category}
          </div>
          {articles_section}
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:'Segoe UI',Arial,sans-serif;">
  <div style="max-width:680px;margin:24px auto;background:white;border-radius:12px;
              overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.1);">
    <!-- Header -->
    <div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);
                padding:30px 32px;text-align:center;">
      <h1 style="margin:0;color:white;font-size:26px;letter-spacing:0.5px;">
        📰 Daily English News
      </h1>
      <p style="margin:6px 0 0;color:rgba(255,255,255,.7);font-size:14px;">{date_str}</p>
    </div>
    <!-- Body -->
    <div style="padding:28px 32px;">
      {articles_html}
    </div>
    <!-- Footer -->
    <div style="background:#f8f9fa;padding:16px 32px;text-align:center;
                color:#aaa;font-size:12px;border-top:1px solid #eee;">
      Generated automatically · Daily English News System · {date_str}
    </div>
  </div>
</body>
</html>"""


def send_email(html_content: str, date_str: str) -> None:
    """Send the HTML email via Gmail SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📰 Daily English News — {date_str}"
    msg["From"] = GMAIL_USER
    msg["To"] = RECIPIENT_EMAIL

    # Plain-text fallback
    plain = (
        f"Daily English News — {date_str}\n\n"
        "Please view this email in an HTML-capable mail client."
    )
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())

    print(f"✅ Email sent to {RECIPIENT_EMAIL}")


def main() -> None:
    kst = timezone(timedelta(hours=9))
    date_str = datetime.now(kst).strftime("%B %d, %Y")

    print(f"🗞  Generating Daily English News for {date_str} …\n")

    news_data: dict[str, dict] = {}
    for category, feeds in RSS_FEEDS.items():
        print(f"[{category}]")
        articles = fetch_articles(feeds)
        print(f"  RSS: fetched {len(articles)} article(s)")
        news_data[category] = generate_category_news(category, articles)
        count = len(news_data[category].get("articles", []))
        print(f"  Gemini: generated {count} summary article(s)")

    print("\n📧 Building and sending email …")
    html = build_html_email(news_data, date_str)
    send_email(html, date_str)


if __name__ == "__main__":
    main()
