from google.adk.agents.llm_agent import Agent
import os
import time
from datetime import date, timedelta
from google.adk.models.lite_llm import LiteLlm
import requests
from dotenv import load_dotenv

load_dotenv()

#llm = LiteLlm(model_name=os.getenv("MODEL_NAME"), api_key=os.getenv("OPENAI_API_KEY"))

model = LiteLlm(
    model=os.getenv("MODEL_NAME", os.getenv("OPENAI_API_KEY"))
)

# --- Step 1: Define the data tool the research team will use ---

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
_NEWS_CACHE_TTL_SECONDS = 600  # avoid re-hitting Finnhub for the same ticker within 10 minutes
_news_cache: dict[str, tuple[float, str]] = {}


def fetch_raw_stock_news(ticker: str) -> str:
    """Fetches real-time market headlines and articles for a given stock ticker.
    Fetch the positive news like New contracts or product launches.
    Fetch the negative news like earnings misses or management changes.
    Always ground your response with the source article, Date of the article.
            The out format should be strictly following:
            Search URL: <URL of the source article>
            Date of the article: <Date of the source article>
    """
    ticker = ticker.upper()

    if not FINNHUB_API_KEY:
        return (
            "News lookup is not configured: FINNHUB_API_KEY is missing from the environment. "
            "Proceed with the decision using price/position context only, and note in your "
            "response that fresh news could not be retrieved."
        )

    cached = _news_cache.get(ticker)
    if cached and (time.time() - cached[0]) < _NEWS_CACHE_TTL_SECONDS:
        return cached[1]

    today = date.today()
    params = {
        "symbol": ticker,
        "from": (today - timedelta(days=7)).isoformat(),
        "to": today.isoformat(),
        "token": FINNHUB_API_KEY,
    }

    last_error = None
    for attempt in range(3):
        try:
            response = requests.get(
                "https://finnhub.io/api/v1/company-news", params=params, timeout=10
            )
            if response.status_code == 429:
                last_error = "Too Many Requests"
                time.sleep(2 ** attempt)  # 1s, 2s, 4s backoff
                continue
            response.raise_for_status()
            articles = response.json()

            if not articles:
                result = f"No recent news found for {ticker}."
            else:
                headlines = [
                    f"- {item.get('headline')} ({item.get('source')})" for item in articles[:5]
                ]
                result = "\n".join(headlines)

            _news_cache[ticker] = (time.time(), result)
            return result
        except requests.RequestException as e:
            last_error = e
            break

    return (
        f"News temporarily unavailable for {ticker} ({last_error}). "
        "Proceed with the decision using price/position context only, and note in your "
        "response that fresh news could not be retrieved."
    )


# --- Step 2: Define the Sub-Agents (The Specialists) ---

summary_agent = Agent(
    model=model,
    name="summary_agent",
    description="A helpful Stock assistant for summarizing market information for the given ticker.",
    instruction="""You are a helpful Stock assistant in summarizing financial news for the given ticker.
        Take the raw stock news provided and compress it into a clean list of Positive News and Negative News.
        For the positive news, look for headlines that indicate growth, new contracts, product launches, or positive earnings.
        For the negative news, look for headlines that indicate earnings misses, management changes, or other negative developments.
        Look for the news on Posiive and Negative sentiments for the last 3 Days. If there is no news, mention that in your summary.    
        Look for global cues that may affect the stock price, such as macroeconomic news or geopolitical events.
        Always ground your response with the source article, Date of the article.
        Provide a clear summary of the positive and negative news in bullet points.
        If you are asked questions completely unrelated to stock or company news, strictly reply: 'I don't know.'""",
    tools=[fetch_raw_stock_news], # This agent can now actually look up the data
)

decision_agent = Agent(
    model=model,
    name="decision_agent",
    description="A helpful assistant for making investment decisions.",
    instruction="""You are a helpful assistant in making analytical investment decisions.
        Analyze the structured positive/negative summary data sent to you by the summary agent.
        Provide a concrete recommendation: BUY, SELL, AVERAGE OR HOLD.
        Always ground your response with the source article, Date of the article.
        The out format should be strictly following:
        Recommendation: <BUY/SELL/HOLD/AVERAGE>
        Search URL: <URL of the source article>
        Date of the article: <Date of the source article>
        For non-financial questions, strictly reply: 'I don't know.'"""
)


# --- Step 3: Define the Root Agent (The Manager / Router) ---

root_agent = Agent(
    model=model,
    name="root_agent",
    description="A helpful orchestrator for answering stock market questions.",
    instruction="""You are the team lead. Do not answer stock questions using your own knowledge.
    The user will provide the stock ticker , his average price and the number of shares he owns or his portfolio value. 
    You must delegate the research first to the summary_agent.
    Then, ensure that summary data is sent directly to the decision_agent for a final rating.
    Consolidate their individual outputs into a single clean response for the user.
    Only answer stock market questions.""",
    # CRITICAL CHANGE: You must pass the specialists to the root team list
    # so the model knows it can hand off tasks to them natively.
    sub_agents=[summary_agent, decision_agent], 
)