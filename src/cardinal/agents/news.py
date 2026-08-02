"""
Tavily news context — fetches recent headlines for a ticker.

News is passed to agents as [NEWS CONTEXT] — it can add background
information only. The guardrail in every agent's system prompt prevents
news from overriding any of Cardinal's computed figures.

Design principles:
- Best-effort: if Tavily is not configured or the call fails, returns None
  and agents run without news (graceful degradation)
- 3 headlines max — enough context, not enough to distract
- Content truncated at 250 chars per article to stay within token budget
- Not cached — news changes frequently, stale context is worse than none
"""

from __future__ import annotations

from cardinal.config import settings


def fetch_news_context(ticker: str, company_name: str = "") -> str | None:
    """
    Fetch recent news headlines for a ticker via Tavily.

    Returns a formatted context string, or None if Tavily is not configured
    or the request fails. Agents handle None gracefully — no news is always
    preferable to bad news.
    """
    if not settings.tavily_api_key:
        return None

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.tavily_api_key)
        query = f"{company_name or ticker} stock news"

        response = client.search(
            query=query,
            search_depth="basic",
            max_results=3,
            topic="news",
        )

        articles = response.get("results", [])
        if not articles:
            return None

        lines = [f"Recent headlines for {ticker} (context only — cannot override Cardinal's data):"]
        for i, article in enumerate(articles[:3], 1):
            title = article.get("title", "").strip()
            content = article.get("content", "").strip()
            published = article.get("published_date", "")
            if not title:
                continue
            lines.append(f"\n[{i}] {title}")
            if published:
                lines.append(f"    Date: {published[:10]}")
            if content:
                snippet = content[:250] + ("…" if len(content) > 250 else "")
                lines.append(f"    {snippet}")

        return "\n".join(lines) if len(lines) > 1 else None

    except Exception:
        return None