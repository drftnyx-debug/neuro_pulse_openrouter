# NEURO PULSE — OpenRouter free starter

Uses Python standard library, RSS feeds, OpenRouter's free-model router, Telegram Bot API, and GitHub Actions.

## Setup
1. Create a repository on GitHub and upload all files, including `.github/workflows/publish.yml`.
2. Go to Settings → Secrets and variables → Actions → New repository secret.
3. Add these secrets:
   - `TELEGRAM_BOT_TOKEN`: token from BotFather
   - `TELEGRAM_CHANNEL_ID`: public channel username such as `@yourchannelusername`, or numeric chat ID for private channels
   - `OPENROUTER_API_KEY`: key from OpenRouter
4. Go to Actions and enable workflows if prompted.
5. Run “Publish NEURO PULSE” manually once, then inspect the logs and the Telegram channel.

Get an OpenRouter key: https://openrouter.ai/keys
Free router/model info: https://openrouter.ai/openrouter/free

## Free-tier limits
OpenRouter currently lists 50 free-model requests/day and 20 requests/minute for accounts that have not purchased credits. Limits and model availability may change. A free model can be temporarily unavailable or rate-limited. Two posts/day uses only a small fraction of the nominal daily request limit.

## Important limitations
- This starter publishes at most one new RSS item per workflow run. If feeds have no new items, no post is published.
- It does not guarantee that generated claims are correct. Review the first few posts manually.
- Scheduled GitHub Actions may be delayed. The included cron is 07:00 and 14:00 UTC, which is 10:00 and 17:00 Kyiv time while Ukraine is UTC+3; adjust for seasonal time changes.
- Do not commit secrets or share them in chat.
- A public repo exposes source code; the secrets must only be stored in GitHub Actions Secrets.
- GitHub Actions requires permission to push `state.json` updates. If that step fails, enable Actions write permissions in repository settings.
