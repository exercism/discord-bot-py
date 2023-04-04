"""Configuration values for Exercism Cogs."""
# pylint: disable=C0301
# General

GUILD_ID = 854117591135027261
MODULES = [
    "InclusiveLanguage",
    "ModMessage",
    "RequestNotifier",
    "StreamingEvents",
    "TrackReact",
]

# mod_message.py
SUPPORT_CHANNEL = 1082698079163134073
CANNED_MESSAGES = {
    "flagged": (
        "This conversation has been flagged as having the potential to become heated. "
        "To all participants, please ensure you are careful of your tone and respectful to others' opinions. "
        "Remember to consider and acknowledge what others are posting before posting your response. "
        "In all conversations on Exercism, aim to learn something new and treat others kindly, rather than win a debate."
    ),
    "criticize_language": (
        "While we love discussions around programming languages at Exercism, "
        "we have a strong policy of not criticising languages. "
        "We understand not every language is a good fit for everyone and that "
        "there may be features you strongly dislike or disagree with, "
        "but variety is the spice of life, and we expect everyone to "
        "remain respectful of the work of the creators and contributors to all languages."
    ),
    "support": (
        "👋 If you are stuck on an exercise and would like help, "
        f"we have a channel specifically for that: <#{SUPPORT_CHANNEL}>.\n\n"
        "Please move your message there, and when you do so, make sure to:\n"
        "* Include the track/language and exercise name in the title.\n"
        "* Include whatever code and errors you have.\n"
        "* Share code and errors as text inside a codeblock (\`\`\`) and not as an image."
    ),

}

# track_react.py
CASE_SENSITIVE = {"go", "red"}
ALIASES = {
    "c#": "csharp",
    r"c\+\+": "cpp",
    "f#": "fsharp",
    "golang": "go",
    "js": "javascript",
    "pharo": "pharo_smalltalk",
    "q#": "qsharp",
    "ts": "typescript",
    "vb.net": "vb_net",
    "elisp": "emacs_lisp",
    "cl": "common_lisp",
}

# mentor_requests.py
MENTOR_REQUEST_CHANNEL = 1091036025737986098

# streaming_events
DEFAULT_STREAMING_URL = "https://twitch.com/exercismlive"

# inclusive language
EXCLUSIVE_LANGUAGE = [
    r"\byou guys\b",
    r"(hello|hey|hi|yo|sup|morning|afternoon|evening)\s*,?\s*(guys|boys|lads|dudes)",
]
