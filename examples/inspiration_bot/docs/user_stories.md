# User Stories

> **Worked example** for the Inspiration Bot. (Stage 3: success as UX.)

1. As a **new user**, I want to send `/start` and get a warm, plain-language hello explaining what
   the bot does and how to feed it, so I know what to do in the first 10 seconds.
2. As a **user**, I want to forward a **photo** and have it understood, stored, and filed, so my
   visual inspiration stops disappearing into my camera roll.
3. As a **user**, I want to send a **thought, quote, or link** as text and have it captured and
   categorized, so words-that-struck-me are kept too.
4. As a **user**, I want the bot to quietly maintain a sense of **what inspires me** that sharpens
   with each thing I send, so it gets more "me" over time without me filling in a profile.
5. As a **user**, I want a **short, personal nudge each morning** based on that profile, so
   inspiration comes back to me instead of rotting in a folder.
6. As a **user**, I want to ask for one **right now** (`/inspire`) when I want a hit, so I'm not
   only waiting for the scheduled send.
7. As a **user**, I want to **change when (and how often) it pings me** just by *telling it in chat*
   ("send me at 7am", "only weekdays", "pause for now"), so the schedule bends to my life without a
   settings screen.
8. As a **user**, I want to see **what it thinks of me** (`/profile`), so the bot isn't a black box.
9. As a **user**, I want to **delete everything** (`/delete`, with a confirm step), so I stay in
   control of my data and can start fresh.

## What "good" feels like

I forward a photo on the bus without a second thought; the bot replies with a one-line "got it —
filed under *quiet architecture*." Days later, a morning message lands that's *so* on-taste it makes
me smile. It feels less like an app and more like a friend with a good eye.

## Out of scope (for now)

Voice/video/stickers (text + photos only). Editing or browsing past items in-chat. Multiple
profiles. Sharing between users. Rich recurrence rules (cron expressions, multiple sends a day) —
v1 keeps it to a daily/weekday/weekly cadence at one local hour.
