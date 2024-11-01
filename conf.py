"""Configuration values for Exercism Cogs."""
# pylint: disable=C0301
# General

GUILD_ID = 854117591135027261
COGS = [
    "CloseSupportThread",
    "InclusiveLanguage",
    "ModMessage",
    "RequestNotifier",
    "StreamingEvents",
    "TrackReact",
]

INCLUSIVE_LANGUAGE_BROS = (
    "Make sure you don't sound sexist and put people off talking to you, "
    "by using more inclusive language like \"Hey everyone\" not \"Hey ${TOKEN}\". Read more here: "
    "https://exercism.org/docs/community/being-a-good-community-member/writing-support-requests"
)

INCLUSIVE_LANGUAGE_GUYS = (
    "At Exercism, we try to ensure that the community is actively welcoming to people "
    "of all backgrounds and genders. Please choose a different word over "
    "gendered terms like 'guys' as this can feel exclusive in some cultures. Read more here: "
    "https://exercism.org/docs/community/being-a-good-community-member/writing-support-requests"
)

# inclusive language
EXCLUSIVE_LANGUAGE = [
    (r"\byou guys\b", INCLUSIVE_LANGUAGE_GUYS),
    (r"(hello|hey|hi|yo|sup|morning|afternoon|evening)\s*,?\s*(guys)", INCLUSIVE_LANGUAGE_GUYS),
    (r"(hello|hey|hi|yo|sup|morning|afternoon|evening)\s*,?\s*(?P<TOKEN>boys|lads|dudes|bros)", INCLUSIVE_LANGUAGE_BROS),
]

# mod_message.py
SUPPORT_CHANNEL = 1082698079163134073
CANNED_MESSAGES = {
    "codeblock": (
        "Increase your chance of getting help and look like a pro by sharing codeblocks not images. "
        "For example, you can type the following. Note, the \\`\\`\\` must be on their own line.\n"
        "\\`\\`\\`\nfor number in range(10):\n    total += number;\n\\`\\`\\`\n"
        "Discord will render that as so:\n"
        "```\nfor number in range(10):\n    total += number;\n```\n"
        "Click here to learn more about codeblocks: "
        "https://exercism.org/docs/community/being-a-good-community-member/writing-support-requests "
        "and http://bit.ly/howto-ask"
    ),
    "resolved": (
        "If everything is resolved, we ask that the person who posted the request "
        "react to the top/original post with a :white_check_mark: (`:white_check_mark:`). "
        "This indicates to others that this issue has been resolved and locks the thread.\n"
        "If all the tests pass and you want to further improve your solution, "
        'we encourage you to use the "Request a Code Review" feature on the website!'
    ),
    "beginner": (
        "👋🏼 Hello!\n"
        "Exercism is designed for people who have some experience in programming. "
        "If you are new to coding, we recommend joining our Beginners Bootcamp, starting in January: https://bootcamp.exercism.org\n\n"
        "There are many other great resources online, that can kickstart your journey in computer science.\n"
        "* [Harvard's CS50x course](http://cs50.harvard.edu/x/2024/) is great for a wide understanding.\n"
        "* [Code in Place](https://codeinplace.stanford.edu/) is a great intro to coding course "
        "which will teach you Python using their browser-based environment.\n"
        "* For a focus on web development, try [The Odin Projects](http://theodinproject.com). "
        "It is a long-term commitment that will guide you to through some projects and will leave you with a nice portfolio by the end.\n"
        "* For web development, [The MDN web docs](http://developer.mozilla.org/en-US/docs/Learn) are a valuable resource."
    ),
    "howto-ask": (
        "Asking questions well increases your chance of getting help. "
        "Learn how to write good support requests in this article: http://bit.ly/howto-ask"
    ),
    "criticize_language": (
        "While we love discussions around programming languages at Exercism, "
        "we have a strong policy of not criticising languages. "
        "We understand not every language is a good fit for everyone and that "
        "there may be features you strongly dislike or disagree with, "
        "but variety is the spice of life, and we expect everyone to "
        "remain respectful of the work of the creators and contributors to all languages."
    ),
    "flagged": (
        "This conversation has been flagged as having the potential to become heated. "
        "To all participants, please ensure you are careful of your tone and respectful to others' opinions. "
        "Remember to consider and acknowledge what others are posting before posting your response. "
        "In all conversations on Exercism, aim to learn something new and treat others kindly, rather than win a debate."
    ),
    "forum": (
        "👋 Hello! If you found an bug or want to suggest an improvement "
        "to either the website or an exercise, then the forum (https://forum.exercism.org) "
        "is the best place to post as it allows long-term asynchronous conversations. "
        "Please make sure you read https://exercism.org/docs/community/"
        "being-a-good-community-member/suggesting-exercise-improvements before posting."
    ),
    "inclusive": INCLUSIVE_LANGUAGE_GUYS,
    "support": (
        "👋 If you are stuck on an exercise and would like help, "
        f"we have a channel specifically for that: <#{SUPPORT_CHANNEL}>.\n\n"
        "Please move your message there, and when you do so, make sure to:\n"
        "* Include the track/language and exercise name in the title.\n"
        "* Include whatever code and errors you have.\n"
        r"* Share code and errors as text inside a codeblock (\`\`\`) and not as an image."
        "See also "
        "https://exercism.org/docs/community/being-a-good-community-member/writing-support-requests "
        "and http://bit.ly/howto-ask"
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
    "vim script": "vimscript",
    "elisp": "emacs_lisp",
    "cl": "common_lisp",
}
NO_REACT_CHANNELS = ["support"]

# mentor_requests.py
MENTOR_REQUEST_CHANNEL = 1091036025737986098

# streaming_events
DEFAULT_STREAMING_URL = "https://twitch.com/exercismlive"

# CloseSupportThread
SUPPORT_RESOLVED = "✅"
