-- Maps language tracks to a discord.Thread.id
CREATE TABLE track_threads ( track_slug TEXT PRIMARY KEY, message_id INTEGER NOT NULL );
-- Maps a request ID to a discord.Message.id
CREATE TABLE requests ( request_id TEXT PRIMARY KEY, track_slug TEXT NOT NULL, message_id TEXT NOT NULL, FOREIGN KEY(track_slug) REFERENCES track_threads(track_slug) );
