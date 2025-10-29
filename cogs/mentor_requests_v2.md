# Mentor Requests Cog

## Overview

This cog polls Exercism's API for requests in the queue.
The list of requests is synced to a per-track thread in the mentor requests Discord channel.

## Periodic Tasks

* Poll Exercism for mentor requests.
  * Each track can be handled as a separate task vs polling all tracks every time we get an updated.
    This is helpful since some tracks are significantly more active than others.
    We want to poll at most once every 5 minutes.
    Less active tracks can be polled as little as once per hour.
  * Store a copy of this in the DB and in memory.
  * Expose Exercism request rates to Prometheus.
  * Maintain the timestamps of the past N requests per-track to set the per-track interval.
    Spitballing, maybe use avg - 1 * stddev, clamped to 5-60 minutes.
* Poll Discord to get all messages in the channel/threads.
  * Since we control the messages, they shouldn't drift out of sync too often.
  * Reading messages from Discord should be relatively light weight.
  * Spread the reads. One track per minute.
  * Store the results in the DB and in memory.
* On any state change, queue the change (add message, remove message).

## Tasks

* Fetch track requests from Exercism.
* Fetch Discord messages for a track.
* Send a Discord message.
* Delete a Discord message.

## Worker

* Use a loop task that runs every 5 seconds.
* Use an async-safe lock so only one task runs at a time. If the lock is held, return.
* Store the timestamp for the next queued task. If the timestamp is in the future, return.
* If there is any issues executing a task, leave it for the next loop.
