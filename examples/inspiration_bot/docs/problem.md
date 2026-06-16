# Problem

> **Worked example** for the Inspiration Bot, a Telegram agent. (Stage 1: the limit of my current agency.)

I collect things that inspire me — a photo I shot, a quote, a screenshot, a half-formed idea —
and they scatter across camera roll, notes apps, and bookmarks. Two things never happen:

1. **They never get organized.** I never go back and tag or make sense of them.
2. **They never come back to me.** Inspiration only helps if it resurfaces when I'm open to it;
   mine just rots in a folder.

What I actually want is something that lives *where I already am* (my chat app), quietly
**absorbs** what I throw at it, builds a sense of **what inspires me**, and then **comes back to
me on its own** each morning with a small nudge that fits my taste. That second half — the agent
**initiating**, not just responding — is the capability I don't have today.

## Why a Telegram bot (not a web app)

- **Zero UI to build and zero login to manage.** Telegram already authenticated the user; every
  message arrives with a verified `from.id`. Identity is free (see `policy.md`).
- **It can reach *out*.** A bot can message me unprompted — which is the whole point of the morning
  nudge. A web app can't knock on your door.
- **Sharing is native.** Forwarding a photo or a link to a chat is a one-tap habit I already have.

## What "done" looks like

I forward photos and thoughts to a bot all week without thinking about it. Each morning it sends me
one short, personal thing — a prompt, a reflection, sometimes a generated image — that feels like it
*gets* what I'm into. And I can wipe everything it knows about me with one command.
