from google.adk.agents.llm_agent import Agent
import os 
from google.adk.models.lite_llm import LiteLlm


model = LiteLlm(
    model=os.getenv("MODEL_NAME", os.getenv("OPENAI_API_KEY"))
)

def calculate_simple_interest(principal, rate, time):
    """This tool calculates the simple interest. Based on the principal amount, rate of interest, and time period."""
    return (principal * rate * time) / 100

def calculate_compound_interest(principal, rate, time):
    """This tool calculates the compound interest. Based on the principal amount, rate of interest, and time period.""" 
    return principal * (1 + rate / 100) ** time - principal 

def interest_difference(principal, rate, time):
    """This tool calculates the difference between compound interest and simple interest. Based on the principal amount, rate of interest, and time period."""
    return calculate_compound_interest(principal, rate, time) - calculate_simple_interest(principal, rate, time)

root_agent = Agent(
    model = model,
    name='root_agent',
    description='A helpful assistant for user questions.',
    instruction="""Your are an helpful assistant in answering only finance questions. For other questions you say i dont know.
    Use calculate_simple_interest, calculate_compound_interest, and interest_difference tools to answer finance questions.
    Use interest_difference tool to calculate the difference between compound interest and simple interest when needed.
    """,
    tools = [calculate_simple_interest, calculate_compound_interest, interest_difference]
)
