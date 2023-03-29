# Exercism Discord Bot

This is a Python bot built on top of the [Discord.py framework](https://discordpy.readthedocs.io/en/stable/).

TODO: Document the various bot features.

## Code layout

* `.env` contains private configuration values which are populated into the environment.
* `conf.py` contains public configuration values which are passed into various Cogs.
* `bot.py` is the executable entry point. It instantiates the various Cogs and starts the bot.
* `mentor_requests.py` tracks requests on Exercism and updates threads with current requests.
* `mod_message.py` provides an app command (or slash command) for mods to send canned messages.
* `track_react.py` contains the logic to react to messages with track-specific emojis.

## Setup

### Exercism library

`exercism_lib` is a symlink to [this Exercism lib](https://github.com/IsaacG/python-projects/tree/master/exercism.org), which is used to fetch data from Exercism.
Ideally, this would be a proper git submodule and the Exericsm logic would be its own repo, not a shared projects repo.

```shell
ln -s $root/python-projects/exercism.org exercism_lib
```

### Configurations

The [dotenv](https://pypi.org/project/python-dotenv/) module is used to load some configurations from a private `.env` file.
Expected environment variables include:
* `DISCORD_TOKEN`: The bot token used by the bot to identify with Discord.
