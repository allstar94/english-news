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
GMAIL_APP_PASSWORD = re.sub(r"[^\x20-\x7E]", " ", os.environ["GMAIL_APP_PASSWORD"]).strip()
RECIPIENT_EMAILS = ["alsltar94@gmail.com", "k30027@gmail.com"]

# --- RSS Feeds by Category ---
RSS_FEEDS = {
    "World": [
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://feeds.washingtonpost.com/rss/world",
    ],
    "Economy": [
        "https://www.cnbc.com/id/10001147/device/rss/rss.html",
        "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
        "https://feeds.marketwatch.com/marketwatch/topstories/",
    ],
    "IT/Tech": [
        "https://feeds.feedburner.com/TechCrunch/",
        "https://www.theverge.com/rss/index.xml",
        "https://www.wired.com/feed/rss",
    ],
}


def fetch_articles(feeds: list[str], count: int = 5) -> list[dict]:
    """Fetch recent articles from RSS feeds."""
    articles = []
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                title = entry.get("title", "").strip()
                raw_summary = entry.get("summary", entry.get("description", "")).strip()
                summary = re.sub(r"<[^>]+>", " ", raw_summary)
                summary = re.sub(r"\s+", " ", summary).strip()[:600]
                source = feed.feed.get("title", feed_url)
                if title:
                    articles.append({"title": title, "summary": summary, "source": source})
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
            f"[{i+1}] Source: {a['source']}\n    Title: {a['title']}\n    Content: {a['summary']}"
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
      "source": "Name of the news source (e.g., TechCrunch, BBC News)",
      "summary_en": "3-4 sentence summary in clear, natural English.",
      "summary_kr": "한국어 요약 2~3문장. 핵심 내용을 자연스러운 한국어로 설명.",
      "vocabulary": [
        {{
          "word": "English word or phrase",
          "en_definition": "English definition (include part of speech)",
          "kr_meaning": "한국어 뜻",
          "example": "Example sentence using this word in context."
        }}
      ],
      "grammar_point": {{
        "sentence": "An actual sentence from the article that demonstrates an interesting grammar pattern.",
        "pattern": "Grammar pattern name (e.g., 관계대명사 which, 분사구문, 가정법 과거완료)",
        "explanation": "한국어로 이 문장의 문법 구조를 상세하게 설명. 문법 패턴이 어떻게 쓰였는지, 비슷한 문장을 어떻게 만들 수 있는지 알려주기."
      }},
      "practical_expression": {{
        "expression": "A useful English expression from or related to the article",
        "meaning": "한국어 뜻과 뉘앙스 설명",
        "usage": "비즈니스/일상에서 이 표현을 쓸 수 있는 상황과 예문 2개"
      }}
    }}
  ]
}}

Rules:
- Exactly 2-3 articles per category
- Each summary_en: 3-4 sentences, clear English
- Each summary_kr: 2-3 sentences, natural Korean
- Each article: 3-5 vocabulary items with English definition + Korean meaning + example
- grammar_point: Pick the most educational sentence and explain the grammar structure IN KOREAN
- practical_expression: Choose a business/daily expression, explain usage IN KOREAN with 2 example sentences"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt
        )
        text = response.text.strip()
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


def generate_quiz(news_data: dict) -> list[dict]:
    """Generate a mini quiz based on all news articles."""
    client = genai.Client(api_key=GEMINI_API_KEY)

    all_articles = []
    for category, data in news_data.items():
        for article in data.get("articles", []):
            all_articles.append(f"[{category}] {article.get('title', '')}: {article.get('summary_en', '')}")

    articles_text = "\n\n".join(all_articles)

    prompt = f"""Based on these news articles:

{articles_text}

Create exactly 4 quiz questions to test comprehension and vocabulary. Mix these types:
- Fill in the blank (1-2 questions)
- True/False (1-2 questions)
- Word matching (1 question)

Return ONLY valid JSON — no markdown fences:
{{
  "quiz": [
    {{
      "type": "fill_blank",
      "question": "The company announced a ______ in quarterly revenue. (hint: 증가)",
      "answer": "surge"
    }},
    {{
      "type": "true_false",
      "question": "Statement about the article content.",
      "answer": "True",
      "explanation": "Brief explanation of why."
    }},
    {{
      "type": "word_match",
      "question": "Match the words with their meanings:\\n1. surge\\n2. plummet\\n3. volatile",
      "answer": "1-급증하다, 2-급락하다, 3-변동이 심한"
    }}
  ]
}}

Rules:
- Exactly 4 questions total
- Questions should be based on actual content from the articles
- Include Korean hints or explanations where helpful
- Make questions educational and varied in difficulty"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt
        )
        text = response.text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return json.loads(text).get("quiz", [])
    except Exception as e:
        print(f"  Quiz generation error: {e}")
        return []


def build_html_email(news_data: dict, quiz: list[dict], date_str: str) -> str:
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
            # Vocabulary table
            vocab_rows = ""
            for v in article.get("vocabulary", []):
                vocab_rows += f"""<tr style="border-bottom:1px solid #e8e8e8;">
                    <td style="padding:8px;font-weight:bold;color:#2c3e50;white-space:nowrap;vertical-align:top;">{v.get('word','')}</td>
                    <td style="padding:8px;color:#444;font-size:13px;">
                      <div>{v.get('en_definition','')}</div>
                      <div style="color:#2980b9;margin-top:2px;">→ {v.get('kr_meaning','')}</div>
                      <div style="color:#888;font-style:italic;margin-top:2px;">"{v.get('example','')}"</div>
                    </td>
                  </tr>"""

            # Grammar point
            gp = article.get("grammar_point", {})
            grammar_html = ""
            if gp:
                grammar_html = f"""
              <div style="background:#fff8e1;padding:14px 16px;border-radius:6px;margin-top:12px;border-left:4px solid #ff9800;">
                <div style="font-size:11px;font-weight:bold;color:#e65100;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">
                  📝 Grammar Point — {gp.get('pattern','')}
                </div>
                <div style="font-size:13px;color:#333;background:#fff3e0;padding:8px 12px;border-radius:4px;margin-bottom:8px;font-style:italic;">
                  "{gp.get('sentence','')}"
                </div>
                <div style="font-size:13px;color:#555;line-height:1.7;">{gp.get('explanation','')}</div>
              </div>"""

            # Practical expression
            pe = article.get("practical_expression", {})
            expression_html = ""
            if pe:
                expression_html = f"""
              <div style="background:#e8f5e9;padding:14px 16px;border-radius:6px;margin-top:12px;border-left:4px solid #4caf50;">
                <div style="font-size:11px;font-weight:bold;color:#2e7d32;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">
                  💬 Practical Expression
                </div>
                <div style="font-size:15px;font-weight:bold;color:#1b5e20;margin-bottom:6px;">
                  "{pe.get('expression','')}"
                </div>
                <div style="font-size:13px;color:#555;margin-bottom:4px;">{pe.get('meaning','')}</div>
                <div style="font-size:13px;color:#666;line-height:1.7;">{pe.get('usage','')}</div>
              </div>"""

            # Source
            source = article.get("source", "")
            source_html = f'<span style="font-size:12px;color:#999;">📌 {source}</span>' if source else ""

            articles_section += f"""
            <div style="border-left:4px solid {border_color};padding:16px 20px;
                        background:#f8f9fa;border-radius:0 8px 8px 0;margin-bottom:20px;">
              <div style="font-size:16px;font-weight:bold;color:#1a1a2e;margin-bottom:6px;">
                {article.get('title','')}
              </div>
              {source_html}
              <!-- English Summary -->
              <div style="color:#444;line-height:1.75;font-size:14px;margin:12px 0;">
                {article.get('summary_en','')}
              </div>
              <!-- Korean Summary -->
              <div style="background:#f0f0f0;padding:10px 14px;border-radius:6px;margin-bottom:14px;">
                <div style="font-size:11px;font-weight:bold;color:#666;margin-bottom:4px;">🇰🇷 한국어 요약</div>
                <div style="font-size:13px;color:#333;line-height:1.7;">{article.get('summary_kr','')}</div>
              </div>
              <!-- Vocabulary -->
              <div style="background:#eef6fb;padding:12px 16px;border-radius:6px;">
                <div style="font-size:11px;font-weight:bold;color:#2980b9;
                            text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;">
                  📚 Key Vocabulary
                </div>
                <table style="border-collapse:collapse;width:100%;font-size:13px;">
                  {vocab_rows}
                </table>
              </div>
              {grammar_html}
              {expression_html}
            </div>"""

        articles_html += f"""
        <div style="margin-bottom:32px;">
          <div style="background:{header_color};color:white;padding:10px 16px;
                      border-radius:6px;font-size:15px;font-weight:bold;margin-bottom:14px;">
            {emoji}&nbsp; {category}
          </div>
          {articles_section}
        </div>"""

    # Quiz section
    quiz_html = ""
    if quiz:
        quiz_items = ""
        for i, q in enumerate(quiz, 1):
            qtype = q.get("type", "")
            type_label = {"fill_blank": "빈칸 채우기", "true_false": "True / False", "word_match": "단어 매칭"}.get(qtype, qtype)
            type_color = {"fill_blank": "#3498db", "true_false": "#e67e22", "word_match": "#9b59b6"}.get(qtype, "#555")

            question_text = q.get("question", "").replace("\n", "<br>")
            answer_text = q.get("answer", "")
            explanation = q.get("explanation", "")
            explanation_html = f"<div style='color:#666;font-size:12px;margin-top:4px;'>{explanation}</div>" if explanation else ""

            quiz_items += f"""
            <div style="background:#f8f9fa;padding:14px 16px;border-radius:8px;margin-bottom:12px;">
              <div style="font-size:11px;font-weight:bold;color:{type_color};text-transform:uppercase;margin-bottom:6px;">
                Q{i}. {type_label}
              </div>
              <div style="font-size:14px;color:#333;line-height:1.6;margin-bottom:8px;">{question_text}</div>
              <details style="cursor:pointer;">
                <summary style="font-size:13px;color:#2980b9;font-weight:bold;">정답 보기</summary>
                <div style="margin-top:6px;padding:8px 12px;background:#e8f8f5;border-radius:4px;font-size:13px;color:#1a5276;">
                  ✅ {answer_text}
                  {explanation_html}
                </div>
              </details>
            </div>"""

        quiz_html = f"""
        <div style="margin-bottom:32px;">
          <div style="background:#1a1a2e;color:white;padding:10px 16px;
                      border-radius:6px;font-size:15px;font-weight:bold;margin-bottom:14px;">
            🧠&nbsp; Mini Quiz
          </div>
          {quiz_items}
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:'Segoe UI',Arial,sans-serif;">
  <div style="max-width:680px;margin:24px auto;background:white;border-radius:12px;
              overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.1);">
    <div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);
                padding:30px 32px;text-align:center;">
      <h1 style="margin:0;color:white;font-size:26px;letter-spacing:0.5px;">
        📰 Daily English News
      </h1>
      <p style="margin:6px 0 0;color:rgba(255,255,255,.7);font-size:14px;">{date_str}</p>
    </div>
    <div style="padding:28px 32px;">
      {articles_html}
      {quiz_html}
    </div>
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
    msg["To"] = ", ".join(RECIPIENT_EMAILS)

    plain = (
        f"Daily English News — {date_str}\n\n"
        "Please view this email in an HTML-capable mail client."
    )
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAILS, msg.as_string())

    print(f"✅ Email sent to {', '.join(RECIPIENT_EMAILS)}")


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

    print("\n[Quiz]")
    quiz = generate_quiz(news_data)
    print(f"  Generated {len(quiz)} quiz question(s)")

    print("\n📧 Building and sending email …")
    html = build_html_email(news_data, quiz, date_str)
    send_email(html, date_str)


if __name__ == "__main__":
    main()
