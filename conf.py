"""Configuration values for Exercism Cogs."""
# pylint: disable=C0301

CHANNEL_ID = {
    "Exercism #photos": 1203795616594010192,
    "Exercism #programming": 1157359032760287302,
    "Exercism #bootcamp-signup-questions": 1314074955880857731,
    "test": 1091223069407842306,
}
# General

GUILD_ID = 854117591135027261
COGS = [
    "CloseSupportThread",
    "InclusiveLanguage",
    "ModMessage",
    "PinnedMessage",
    "RequestNotifier",
    "StreamingEvents",
    "ThreadReminder",
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
        "If you are new to coding, we strongly recommend joining our Beginners Bootcamp, starting in January: https://bootcamp.exercism.org"
    ),
    "learning": (
        "Exercism is designed for people who have some experience in programming. "
        "Here are a few great online resources that can kickstart your journey in computer science.\n\n"
        "* [Exercism's Beginners Bootcamp](https://bootcamp.exercism.org) will give you a solid programming foundation.\n"
        "* [Harvard's CS50x course](http://cs50.harvard.edu/x/2024/) is great for a wide understanding.\n"
        "* [Code in Place](https://codeinplace.stanford.edu/) is a great intro to coding course "
        "which will teach you Python using their browser-based environment.\n"
        "* For a focus on web development, try [The Odin Projects](http://theodinproject.com). "
        "It is a long-term commitment that will guide you to through some projects and will leave you with a nice portfolio by the end.\n"
        "* For web development, [The MDN web docs](http://developer.mozilla.org/en-US/docs/Learn) are a valuable resource."
    ),
    "howto-ask": (
        "How you ask questions makes a huge difference in the help we can provide. "
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


# PinnedMessage
PINNED_MESSAGES = {
    # Test channel in test server.
    1091223069407842306: "This is a pinned message.",
    # Exercism #photo channel
    CHANNEL_ID["Exercism #photos"]: """\
> **📸 Pinned Reminder 📸**
> Use this channel to share photos you took of your pets, family, art, or anything else that is meaningful to you.
> If someone else's photo catches your eye, please use threads to discuss.
> Thank you for being part of our Exercism community!""",
    1326564185643024394: """\
> **Pinned Reminder**
> To keep things tidy in this channel, please remember to use threads when replying to people's posts. You can start a thread by hovering over the message you want to reply to, clicking on the `...` and then on "Create Thread". Thanks!""",
    # Exercism #programming
    CHANNEL_ID["Exercism #programming"]: """\
> ** Pinned Reminder **
> To keep things tidy in this channel, please remember to use threads when replying to people's posts. You can start a thread by hovering over the message you want to reply to, clicking on the `...` and then on "Create Thread". Thanks!""",
    # Exercism
    CHANNEL_ID["Exercism #bootcamp-signup-questions"]: """\
> ** Pinned Reminder **
> If you're missing the #bootcamp role/color/channel, please double check you synced your Exercism account to Discord.
> See <https://exercism.org/settings/integrations>. If you are synced and it still doesn't work, try unlinking and relinking :slight_smile:""",
}

THREAD_REMINDER_CHANNELS = [
    CHANNEL_ID["Exercism #photos"],
    CHANNEL_ID["Exercism #programming"],
    CHANNEL_ID["test"],
]
