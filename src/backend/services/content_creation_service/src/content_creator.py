"""
Content Creator - builds multi-paragraph analyses for climate news batches.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests


class ContentCreator:
    """Generate rich summaries and insights from a list of articles."""

    def __init__(self, perplexity_api_key: str):
        self.api_key = perplexity_api_key
        self.base_url = "https://api.perplexity.ai"
        self.model = "sonar"

    def create_summary(
        self,
        articles: List[Dict[str, Any]],
        country: str = "Finland",
        language: str = "fi"
    ) -> Dict[str, Any]:
        """Return an extended summary object for the supplied articles."""
        articles_text = "\n\n".join(
            [
                f"Article {i + 1}: {art['title']}\n{art.get('summary', '')[:400]}"
                for i, art in enumerate(articles[:10])
            ]
        )

        lang_names = {
            "fi": "Finnish",
            "en": "English",
            "sv": "Swedish",
            "no": "Norwegian",
            "de": "German",
        }
        target_lang = lang_names.get(language, "English")

        prompt = f"""You are a senior climate analyst. Create an executive briefing based on the following articles from {country}.

ARTICLES:
{articles_text}

Deliverables in {target_lang}:
1. A title that captures the dominant narrative.
2. An executive summary with 2-3 coherent paragraphs (minimum 8 sentences total).
3. 4-6 key findings with referenced facts.
4. An impact analysis describing short- and mid-term implications for {country}.
5. A confidence assessment that mentions supporting data sources (e.g. ClimateCheck, NOAA, NASA if present).
6. 3 actionable recommendations.

Respond in JSON format (valid JSON, no comments):
{{
  "title": "Main headline",
  "summary_plain_text": "Two to three paragraphs...",
  "summary_markdown": "### Executive Summary\\nParagraphs...\\n\\n### Key Developments\\n- ...\\n- ...\\n\\n### Outlook\\n...",
  "key_findings": ["Finding 1", "Finding 2", ...],
  "impact_analysis": "Implication narrative",
  "confidence_assessment": "Confidence explanation",
  "recommended_actions": ["Action 1", "Action 2", "Action 3"],
  "language": "{target_lang}"
}}
"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 2400,
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            summary = self._parse_summary_response(content, articles, country, language)
            summary["created_with"] = "perplexity"
            return summary
        except requests.RequestException as exc:
            print(f"[ContentCreator] Perplexity API error: {exc}")
            return self._create_fallback_summary(articles, country, language)

    def _parse_summary_response(
        self,
        content: str,
        articles: List[Dict[str, Any]],
        country: str,
        language: str,
    ) -> Dict[str, Any]:
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start < 0 or json_end <= json_start:
            return self._create_fallback_summary(articles, country, language)

        json_str = content[json_start:json_end]
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError:
            return self._create_fallback_summary(articles, country, language)

        result.setdefault("summary_plain_text", result.get("summary", ""))
        result.setdefault("summary_markdown", result.get("summary_plain_text", ""))
        result.setdefault("summary", result.get("summary_plain_text", ""))
        result.setdefault("key_findings", [])
        result.setdefault("impact_analysis", "Impact analysis not provided.")
        result.setdefault("confidence_assessment", "Confidence estimate not provided by model.")
        result.setdefault("recommended_actions", [])
        result.setdefault("language", language)

        result["created_at"] = datetime.now().isoformat()
        result["article_count"] = len(articles)
        result["country"] = country
        return result

    def _create_fallback_summary(
        self,
        articles: List[Dict[str, Any]],
        country: str,
        language: str,
    ) -> Dict[str, Any]:
        titles = [article.get("title", "") for article in articles[:5]]
        plain = f"Latest climate news from {country}. Analysed {len(articles)} articles."
        markdown = (
            "### Executive Summary\n" + plain + "\n\n"
            "### Key Developments\n" + "\n".join(f"- {title}" for title in titles if title)
        )

        return {
            "title": f"Climate News Highlights: {country}",
            "summary_plain_text": plain,
            "summary_markdown": markdown,
            "summary": plain,
            "key_findings": titles,
            "impact_analysis": "Impact analysis not available (fallback).",
            "confidence_assessment": "Confidence data unavailable (fallback).",
            "recommended_actions": ["Stay informed", "Support local climate initiatives", "Share verified information"],
            "created_at": datetime.now().isoformat(),
            "article_count": len(articles),
            "country": country,
            "language": language,
            "created_with": "fallback",
        }

    def analyze_trends(
        self,
        articles: List[Dict[str, Any]],
        time_period_days: int = 30,
    ) -> Dict[str, Any]:
        return {
            "emerging_topics": ["climate policy", "renewable energy", "carbon emissions"],
            "sentiment_trend": "increasing concern",
            "geographic_focus": [articles[0].get("country_code", "N/A")] if articles else [],
            "key_actors": ["Government", "EU", "NGOs"],
        }


def test_content_creator() -> None:
    api_key = "demo"
    creator = ContentCreator(api_key)
    demo_articles = [
        {"title": "Example article", "summary": "Content about climate."}
    ]
    print(creator.create_summary(demo_articles, country="Finland", language="fi"))


if __name__ == "__main__":
    test_content_creator()
