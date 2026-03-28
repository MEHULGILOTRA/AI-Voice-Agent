"""
All LLM prompt templates in one place.

Kept minimal — LLM is only called in conduct_conversation (outreach)
when no transcript is available, and optionally for survey reply sentiment.
"""

OUTREACH_EXTRACTION_PROMPT = """
You are simulating a brief phone call with a parent named {parent_name}.
The purpose of the call is to collect the following information:
- Email address
- Mobile phone number
- Child's school name
- Preferred day of the week for group sessions
- Preferred time of day

Please produce a realistic, concise call transcript in the format:
Agent: [what the agent says]
{parent_name}: [what the parent says]

The parent should provide all the requested information naturally.
Keep the transcript under 20 lines.
"""

SURVEY_SENTIMENT_PROMPT = """
Classify the sentiment of this student survey reply as one of:
  positive / neutral / negative / unclear

Reply: "{reply_text}"

Respond with ONLY the classification word, nothing else.
"""
