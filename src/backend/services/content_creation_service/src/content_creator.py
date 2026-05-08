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

        if not self.api_key:
            raise RuntimeError(
                "ContentCreator: PERPLEXITY_API_KEY is required; "
                "no synthetic fallback is available."
            )

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
            raise

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
            raise ValueError(
                "ContentCreator: model response did not contain a JSON object"
            )

        json_str = content[json_start:json_end]
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"ContentCreator: model response was not valid JSON: {exc}"
            ) from exc

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

    def analyze_trends(
        self,
        articles: List[Dict[str, Any]],
        time_period_days: int = 30,
    ) -> Dict[str, Any]:
        """Compute trend metrics by tallying real article tags / countries / sources.

        No fabricated topics. If the corpus is empty we return zero-valued buckets
        so callers can detect the absence of data rather than read a synthetic answer.
        """
        from collections import Counter

        topic_counter: Counter = Counter()
        country_counter: Counter = Counter()
        source_counter: Counter = Counter()

        for article in articles:
            tags = article.get("tags") or article.get("categories") or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            for tag in tags:
                topic_counter[str(tag).lower()] += 1

            cc = article.get("country_code")
            if cc:
                country_counter[cc.upper()] += 1

            source = article.get("source_name") or article.get("source")
            if source:
                source_counter[source] += 1

        return {
            "emerging_topics": [t for t, _ in topic_counter.most_common(5)],
            "topic_counts": dict(topic_counter.most_common(10)),
            "geographic_focus": [c for c, _ in country_counter.most_common(5)],
            "active_sources": [s for s, _ in source_counter.most_common(10)],
            "article_count": len(articles),
            "time_period_days": time_period_days,
            "computed_at": datetime.now().isoformat(),
        }


