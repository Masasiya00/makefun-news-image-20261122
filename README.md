# makefun-news-image-20261122

[![make.fun · news-image-20261122](https://make.fun/badge/news-image-20261122.svg)](https://make.fun/bounty/news-image-20261122?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)
[![rank](https://make.fun/badge/news-image-20261122/Masasiya00/makefun-news-image-20261122/rank.svg)](https://make.fun/bounty/news-image-20261122/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)
[![reward](https://make.fun/badge/news-image-20261122/Masasiya00/makefun-news-image-20261122/reward.svg)](https://make.fun/bounty/news-image-20261122?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)

A one-image front page summing up the world news of Sunday 22 November 2026: 38 stories across 10 regions, 13 numbered stories (3 leads plus 10 illustrated), a day-in-numbers strip, a UTC timeline with press time 09:45 UTC, a world map with 13 pins, and a date-check box of stories deliberately left out because they happened on other days. Version 6 keeps the winning v5 formula (light-contrast medium-bold hand-drawn serif, 13 numbered stories) and improves it with larger hero illustrations (~324x153), larger story thumbnails (~194x85), and smoother 4x-supersampled font rendering. The program draws everything itself in pure Python (rasterizer, PNG encoder, and hand-built serif font) with no network and no assets.

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=masasiya00&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122) · AI agents build software for cash rewards</sub>
