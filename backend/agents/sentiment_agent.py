"""
Sentiment Analyst Agent - Analyzes news and social media sentiment using LLMs.

LLM priority: Groq (fastest, free tier) → HuggingFace → Ollama
News priority: NewsAPI → Google News RSS → yfinance
"""
import re
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

from agents.base_agent import BaseAgent
from models.schemas import AgentScore, VisualizationData, SentimentMetrics
from services.news_service import news_service
from services.llm_service import llm_router, LLMProvider
from services.finnhub_service import finnhub_service

logger = logging.getLogger(__name__)

# Negation words that flip sentiment
_NEGATION_PATTERN = re.compile(
    r"\b(not|no|never|neither|nor|cannot|can't|won't|don't|doesn't|didn't|isn't|aren't|wasn't|weren't|hardly|scarcely|barely)\b",
    re.IGNORECASE
)


def _score_from_label(label: str, context: str = "") -> float:
    """
    Convert a sentiment label into a gradient float score [-1, 1].
    Handles negation in the context surrounding the label.
    """
    label_lower = label.lower().strip()

    # Gradient map
    SCORES = {
        "very positive": 0.90,
        "strongly positive": 0.90,
        "highly positive": 0.90,
        "positive": 0.65,
        "slightly positive": 0.38,
        "mildly positive": 0.38,
        "somewhat positive": 0.38,
        "neutral": 0.0,
        "mixed": 0.0,
        "unclear": 0.0,
        "slightly negative": -0.38,
        "mildly negative": -0.38,
        "somewhat negative": -0.38,
        "negative": -0.65,
        "highly negative": -0.90,
        "strongly negative": -0.90,
        "very negative": -0.90,
        "bearish": -0.65,
        "bullish": 0.65,
    }

    score = SCORES.get(label_lower)

    # Fuzzy fallback for labels not in map
    if score is None:
        if "positive" in label_lower or "bullish" in label_lower or "good" in label_lower:
            score = 0.65
        elif "negative" in label_lower or "bearish" in label_lower or "bad" in label_lower:
            score = -0.65
        else:
            score = 0.0

    # Check for negation in the surrounding context (flip direction if negated)
    # Use a small window around the label in the context string
    if context and _NEGATION_PATTERN.search(context):
        # Be conservative — only flip if negation occurs immediately nearby
        # Look for patterns like "not positive", "not bullish"
        negated = re.search(
            r"\b(not|no|never|cannot|can't|won't|don't|doesn't|didn't|isn't|aren't|wasn't|weren't)\s+(positive|bullish|good|negative|bearish|bad)",
            context,
            re.IGNORECASE
        )
        if negated:
            score = -score

    return score


class SentimentAgent(BaseAgent):
    """Analyzes sentiment from news and social media using LLMs."""

    def __init__(self):
        super().__init__("Sentiment Analyst")

    async def analyze(self, ticker: str, **kwargs) -> AgentScore:
        """
        Perform sentiment analysis on news articles.

        Analyzes:
        - Recent news articles (last 30 days)
        - Sentiment classification using Groq Llama3 (with fallbacks)
        - Sentiment trends over time
        - Source diversity

        Returns:
            AgentScore with sentiment score (0-100)
        """
        self.log_info(f"Starting sentiment analysis for {ticker}")

        try:
            # Get company name for better news search
            company_name = await self._get_company_name(ticker)

            # Fetch news articles (multiple sources)
            articles = await self._fetch_news(ticker, company_name)

            if not articles:
                self.log_warning("No news articles found")
                return self.create_score(
                    score=50.0,
                    confidence=0.2,
                    factors={"no_data": 1.0},
                    metrics={"article_count": 0},
                    visualizations=[],
                    explanation="Insufficient news data for sentiment analysis"
                )

            # Analyze sentiment for each article
            sentiment_results = await self._analyze_article_sentiments(articles)

            # Calculate metrics
            metrics = self._calculate_metrics(sentiment_results, articles)

            # Calculate factor scores
            factor_scores = self._calculate_factor_scores(metrics)

            # Calculate overall score
            overall_score = self._calculate_overall_score(metrics, factor_scores)

            # Calculate confidence
            confidence = self._calculate_confidence(articles, sentiment_results, metrics)

            # Generate visualizations
            visualizations = self._create_visualizations(sentiment_results, metrics)

            # Create explanation
            explanation = self._generate_explanation(metrics, overall_score)

            self.log_info(
                f"Sentiment analysis complete: Score={overall_score:.2f}, "
                f"Confidence={confidence:.2f}, Articles={len(articles)}"
            )

            return self.create_score(
                score=overall_score,
                confidence=confidence,
                factors=factor_scores,
                metrics=metrics.__dict__,
                visualizations=visualizations,
                explanation=explanation
            )

        except Exception as e:
            self.log_error(f"Sentiment analysis failed: {str(e)}")
            return self.create_score(
                score=50.0,
                confidence=0.1,
                factors={"error": 1.0},
                metrics={"error": str(e)},
                visualizations=[],
                explanation=f"Analysis failed: {str(e)}"
            )

    async def _get_company_name(self, ticker: str) -> str:
        """Get company name for better news search."""
        try:
            if finnhub_service.is_available():
                profile = finnhub_service.get_company_profile(ticker)
                if profile and 'name' in profile:
                    return profile['name']
        except Exception:
            pass
        return ticker

    async def _fetch_news(self, ticker: str, company_name: str) -> List[Dict[str, Any]]:
        """
        Fetch recent news articles from multiple sources.

        Priority:
          1. NewsAPI (if key configured)    — best quality, broad coverage
          2. Google News RSS (always free)   — good fallback
          3. yfinance news (always free)     — financial-focused fallback
        """
        articles = []

        # 1. NewsAPI / Google RSS (news_service handles both internally)
        try:
            raw = news_service.get_company_news(
                company_name=company_name,
                ticker=ticker,
                days_back=30,
                page_size=50
            )
            if raw:
                articles.extend(raw)
                self.log_info(f"Got {len(raw)} articles from NewsAPI/RSS")
        except Exception as e:
            self.log_warning(f"NewsAPI/RSS fetch failed: {e}")

        # 2. yfinance news fallback (financial-focused, always available)
        if len(articles) < 10:
            try:
                yf_articles = news_service.get_yfinance_news(ticker)
                if yf_articles:
                    # Deduplicate by title
                    existing_titles = {a.get('title', '').lower() for a in articles}
                    new_articles = [
                        a for a in yf_articles
                        if a.get('title', '').lower() not in existing_titles
                    ]
                    articles.extend(new_articles)
                    self.log_info(f"Added {len(new_articles)} articles from yfinance")
            except Exception as e:
                self.log_warning(f"yfinance news fetch failed: {e}")

        return articles[:30]  # Limit to 30 most recent

    async def _analyze_article_sentiments(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze sentiment for each article using LLM."""
        results = []
        batch_size = 5

        for i in range(0, len(articles), batch_size):
            batch = articles[i:i + batch_size]
            try:
                batch_results = await self._analyze_batch(batch)
                results.extend(batch_results)
            except Exception as e:
                self.log_warning(f"Batch analysis failed: {str(e)}")
                for article in batch:
                    results.append({
                        'title': article.get('title', article.get('headline', '')),
                        'sentiment': 0.0,
                        'confidence': 0.3,
                        'date': article.get('publishedAt', article.get('datetime', ''))
                    })

        return results

    async def _analyze_batch(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze a batch of articles using best available LLM."""
        articles_text = "\n\n".join([
            f"Article {i + 1}: {article.get('title', article.get('headline', ''))}\n"
            f"Summary: {article.get('description', article.get('summary', ''))[:200]}"
            for i, article in enumerate(articles)
        ])

        prompt = f"""Analyze the sentiment of these financial news articles.

For each article respond on ONE line in EXACTLY this format:
Article N: [sentiment] | [confidence] | [one-sentence reason]

Sentiment must be one of:
  very positive, positive, slightly positive, neutral, slightly negative, negative, very negative

Confidence must be one of: high, medium, low

Articles:
{articles_text}"""

        system_prompt = "You are a precise financial sentiment analyst. Use exact labels only. Be objective."

        try:
            # Priority: Groq (fast, free tier) → HuggingFace → Ollama
            response, provider = await llm_router.generate(
                prompt=prompt,
                provider_priority=[
                    LLMProvider.GROQ_LLAMA3_70B,
                    LLMProvider.GROQ_MIXTRAL,
                    LLMProvider.HUGGINGFACE_MIXTRAL,
                    LLMProvider.OLLAMA_MIXTRAL,
                ],
                system_prompt=system_prompt,
                temperature=0.2,   # Low temperature → more consistent labels
                max_tokens=800
            )

            self.log_info(f"Sentiment LLM provider: {provider}")
            return self._parse_sentiment_response(response, articles)

        except Exception as e:
            self.log_warning(f"LLM unavailable ({e}), using heuristic fallback")
            return self._heuristic_sentiment(articles)

    def _parse_sentiment_response(self, response: str, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse LLM response into structured sentiment data.

        Expected format: 'Article N: [label] | [confidence] | [reason]'
        """
        results = []
        lines = response.strip().split('\n')

        # Build a lookup: article index → matching line
        line_map: Dict[int, str] = {}
        for line in lines:
            m = re.match(r'Article\s+(\d+)\s*:', line, re.IGNORECASE)
            if m:
                idx = int(m.group(1)) - 1   # 0-based
                line_map[idx] = line

        for i, article in enumerate(articles):
            title = article.get('title', article.get('headline', ''))
            date = article.get('publishedAt', article.get('datetime', ''))
            article_line = line_map.get(i, "")

            if article_line:
                parts = [p.strip() for p in article_line.split('|')]
                # parts[0] = "Article N: [label]", parts[1] = confidence, parts[2] = reason
                label_raw = parts[0].split(':', 1)[-1].strip() if ':' in parts[0] else ""
                confidence_raw = parts[1] if len(parts) > 1 else "medium"
                reason = parts[2] if len(parts) > 2 else ""

                # Score using gradient helper (with negation detection)
                context = f"{label_raw} {reason}".lower()
                sentiment_score = _score_from_label(label_raw, context)

                confidence_map = {"high": 0.88, "medium": 0.60, "low": 0.35}
                confidence = confidence_map.get(confidence_raw.lower().split()[0], 0.60)

                results.append({
                    'title': title,
                    'sentiment': round(sentiment_score, 3),
                    'confidence': confidence,
                    'date': date,
                    'label': label_raw,
                    'reason': reason
                })
            else:
                # LLM didn't return a line for this article — use heuristic
                heuristic = self._heuristic_single(title)
                results.append({
                    'title': title,
                    'sentiment': heuristic['sentiment'],
                    'confidence': 0.30,
                    'date': date,
                    'label': 'neutral',
                    'reason': 'not scored by LLM'
                })

        return results

    def _heuristic_sentiment(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Keyword-based fallback when no LLM is available.
        Better than returning all-neutral — at least directionally meaningful.
        """
        return [self._heuristic_single(
            article.get('title', article.get('headline', '')),
            article.get('description', article.get('summary', '')),
            article.get('publishedAt', article.get('datetime', ''))
        ) for article in articles]

    def _heuristic_single(self, title: str, description: str = "", date: str = "") -> Dict[str, Any]:
        """Simple keyword-based sentiment for a single article."""
        text = f"{title} {description}".lower()

        POSITIVE_WORDS = {
            'beat', 'beats', 'surge', 'surged', 'jump', 'jumps', 'gain', 'gains',
            'profit', 'profits', 'record', 'growth', 'grew', 'soar', 'soars',
            'rally', 'rallies', 'upgrade', 'upgraded', 'buy', 'strong', 'bullish',
            'outperform', 'raise', 'raised', 'exceed', 'exceeds', 'exceeded',
            'positive', 'breakout', 'recovery', 'upbeat', 'optimistic'
        }
        NEGATIVE_WORDS = {
            'miss', 'misses', 'missed', 'loss', 'losses', 'decline', 'declines',
            'fell', 'fall', 'falls', 'drop', 'drops', 'dropped', 'plunge', 'plunges',
            'cut', 'cuts', 'downgrade', 'downgraded', 'sell', 'weak', 'bearish',
            'underperform', 'lower', 'disappoints', 'disappointing', 'warning',
            'recession', 'crash', 'bankrupt', 'lawsuit', 'fine', 'penalty'
        }

        words = set(re.findall(r'\b\w+\b', text))

        pos_hits = len(words & POSITIVE_WORDS)
        neg_hits = len(words & NEGATIVE_WORDS)

        if pos_hits > neg_hits + 1:
            score = min(0.55, 0.25 + pos_hits * 0.08)
        elif neg_hits > pos_hits + 1:
            score = max(-0.55, -0.25 - neg_hits * 0.08)
        else:
            score = 0.0

        return {
            'title': title,
            'sentiment': round(score, 3),
            'confidence': 0.35,  # Heuristic is lower confidence
            'date': date,
            'label': 'positive' if score > 0.1 else 'negative' if score < -0.1 else 'neutral',
            'reason': f'keyword heuristic ({pos_hits} positive, {neg_hits} negative signals)'
        }

    def _calculate_metrics(
        self,
        sentiment_results: List[Dict[str, Any]],
        articles: List[Dict[str, Any]]
    ) -> SentimentMetrics:
        """Calculate sentiment metrics."""
        if not sentiment_results:
            return SentimentMetrics(overall_sentiment=0.0)

        # Confidence-weighted average sentiment
        total_weighted = sum(r['sentiment'] * r['confidence'] for r in sentiment_results)
        total_confidence = sum(r['confidence'] for r in sentiment_results)
        overall_sentiment = total_weighted / total_confidence if total_confidence > 0 else 0.0

        # Count categories (using gradient thresholds)
        positive_count = sum(1 for r in sentiment_results if r['sentiment'] > 0.20)
        negative_count = sum(1 for r in sentiment_results if r['sentiment'] < -0.20)
        neutral_count = len(sentiment_results) - positive_count - negative_count

        # Get unique sources
        sources = list(set(
            article.get('source', {}).get('name', 'Unknown')
            if isinstance(article.get('source'), dict)
            else str(article.get('source', 'Unknown'))
            for article in articles
        ))

        # Top articles (most extreme sentiments first)
        sorted_results = sorted(sentiment_results, key=lambda r: abs(r['sentiment']), reverse=True)
        top_articles = [
            {
                'title': r['title'][:100],
                'sentiment': 'Positive' if r['sentiment'] > 0.20 else 'Negative' if r['sentiment'] < -0.20 else 'Neutral',
                'score': str(round(r['sentiment'], 2))
            }
            for r in sorted_results[:5]
        ]

        return SentimentMetrics(
            overall_sentiment=round(overall_sentiment, 3),
            positive_count=positive_count,
            negative_count=negative_count,
            neutral_count=neutral_count,
            sources=sources,
            top_articles=top_articles
        )

    def _calculate_factor_scores(self, metrics: SentimentMetrics) -> Dict[str, float]:
        """
        Calculate DIRECTIONAL factor scores (0-100).

        Critically: source_diversity is a data-quality signal, NOT a bullish signal.
        It belongs in confidence, not here. Only sentiment direction scores live here.
        """
        scores = {}

        # Factor 1: overall weighted-average sentiment, mapped [-1,1] -> [0,100]
        sentiment_score = (metrics.overall_sentiment + 1) * 50
        scores['overall_sentiment'] = round(max(0.0, min(100.0, sentiment_score)), 2)

        # Factor 2: positive/negative article ratio (directional distribution)
        total = metrics.positive_count + metrics.negative_count + metrics.neutral_count
        if total > 0:
            positive_ratio = metrics.positive_count / total
            negative_ratio = metrics.negative_count / total

            if positive_ratio >= 0.60:
                scores['sentiment_distribution'] = 88
            elif positive_ratio >= 0.45:
                scores['sentiment_distribution'] = 72
            elif positive_ratio >= 0.30:
                scores['sentiment_distribution'] = 58
            elif negative_ratio >= 0.60:
                scores['sentiment_distribution'] = 15
            elif negative_ratio >= 0.45:
                scores['sentiment_distribution'] = 28
            elif negative_ratio >= 0.30:
                scores['sentiment_distribution'] = 42
            else:
                # Mostly neutral — score is exactly 50, no directional signal
                scores['sentiment_distribution'] = 50

        # NOTE: source_diversity is handled in _calculate_confidence, not here.
        # It tells us how reliable the data is, not whether the market is bullish.
        return scores

    def _calculate_overall_score(
        self,
        metrics: SentimentMetrics,
        factor_scores: Dict[str, float]
    ) -> float:
        """Calculate overall sentiment score (purely directional, 0-100)."""
        if not factor_scores:
            return 50.0

        # Directional weights only
        weights = {
            'overall_sentiment': 0.60,    # Confidence-weighted average of all articles
            'sentiment_distribution': 0.40, # Positive vs negative article ratio
        }

        total_weight = sum(weights.get(f, 0) for f in factor_scores)
        if total_weight == 0:
            return 50.0

        weighted_sum = sum(
            factor_scores[f] * weights.get(f, 0)
            for f in factor_scores
        )
        return round(weighted_sum / total_weight, 2)

    def _calculate_confidence(
        self,
        articles: List[Dict[str, Any]],
        sentiment_results: List[Dict[str, Any]],
        metrics: SentimentMetrics = None
    ) -> float:
        """
        Calculate confidence based on data quality.
        Source diversity is a reliability bonus — it lives here, not in the score.
        """
        if not articles or not sentiment_results:
            return 0.2

        # Article volume: 20+ articles → full confidence on this axis
        article_confidence = min(1.0, len(articles) / 20)

        # Average LLM/heuristic confidence per article
        avg_sentiment_confidence = (
            sum(r['confidence'] for r in sentiment_results) / len(sentiment_results)
        )

        # Source diversity bonus: more outlets → more reliable signal
        diversity_bonus = 0.0
        if metrics is not None:
            n = len(metrics.sources)
            if n >= 7:
                diversity_bonus = 0.08
            elif n >= 5:
                diversity_bonus = 0.05
            elif n >= 3:
                diversity_bonus = 0.02

        raw = article_confidence * 0.35 + avg_sentiment_confidence * 0.65 + diversity_bonus
        return round(min(0.95, raw), 2)

    def _create_visualizations(
        self,
        sentiment_results: List[Dict[str, Any]],
        metrics: SentimentMetrics
    ) -> List[VisualizationData]:
        """Create visualizations."""
        visualizations = []

        # Sentiment distribution pie chart
        visualizations.append(
            self.create_visualization(
                chart_type="pie",
                title="Sentiment Distribution",
                data={
                    "labels": ["Positive", "Neutral", "Negative"],
                    "values": [metrics.positive_count, metrics.neutral_count, metrics.negative_count],
                    "colors": ["#10b981", "#6b7280", "#ef4444"]
                }
            )
        )

        # Sentiment timeline (if we have dates)
        dated_results = [r for r in sentiment_results if r.get('date')]
        if dated_results:
            dated_results.sort(key=lambda x: x['date'])
            last_15 = dated_results[-15:]
            visualizations.append(
                self.create_visualization(
                    chart_type="line",
                    title="Sentiment Over Time",
                    data={
                        "dates": [r['date'][:10] for r in last_15],
                        "sentiment": [round(r['sentiment'], 3) for r in last_15]
                    }
                )
            )

        return visualizations

    def _generate_explanation(self, metrics: SentimentMetrics, overall_score: float) -> str:
        """
        Generate explanation grounded in article counts — never contradicts the raw data.
        Uses positive_ratio as the primary signal, not the score, to avoid mismatches
        like '0/30 positive but mildly positive'.
        """
        parts = []
        total = metrics.positive_count + metrics.negative_count + metrics.neutral_count

        if total == 0:
            return "No articles analyzed."

        positive_ratio = metrics.positive_count / total
        negative_ratio = metrics.negative_count / total

        # Lead sentence grounded in actual counts
        if positive_ratio >= 0.55:
            parts.append(
                f"Predominantly positive news: {metrics.positive_count}/{total} articles bullish "
                f"({positive_ratio:.0%})."
            )
        elif positive_ratio >= 0.35:
            parts.append(
                f"Mixed-to-positive news: {metrics.positive_count} positive, "
                f"{metrics.negative_count} negative, {metrics.neutral_count} neutral out of {total} articles."
            )
        elif negative_ratio >= 0.55:
            parts.append(
                f"Predominantly negative news: {metrics.negative_count}/{total} articles bearish "
                f"({negative_ratio:.0%})."
            )
        elif negative_ratio >= 0.35:
            parts.append(
                f"Mixed-to-negative news: {metrics.negative_count} negative, "
                f"{metrics.positive_count} positive out of {total} articles."
            )
        else:
            parts.append(
                f"Neutral/mixed news coverage: {metrics.neutral_count}/{total} articles neutral, "
                f"{metrics.positive_count} positive, {metrics.negative_count} negative."
            )

        # Source diversity note
        n = len(metrics.sources)
        if n >= 5:
            parts.append(f"Good source diversity ({n} outlets).")
        elif n >= 3:
            parts.append(f"Moderate source diversity ({n} outlets).")

        return " ".join(parts)


# Global instance
sentiment_agent = SentimentAgent()
