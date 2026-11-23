# makefun-news-image-20261122

[![make.fun · news-image-20261122](https://make.fun/badge/news-image-20261122.svg)](https://make.fun/bounty/news-image-20261122?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)
[![rank](https://make.fun/badge/news-image-20261122/Masasiya00/makefun-news-image-20261122/rank.svg)](https://make.fun/bounty/news-image-20261122/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)
[![reward](https://make.fun/badge/news-image-20261122/Masasiya00/makefun-news-image-20261122/reward.svg)](https://make.fun/bounty/news-image-20261122?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)

A one-image front page summing up the world news of Sunday 22 November 2026: 38 stories across 10 regions, 13 numbered stories (3 leads + 10 illustrated), a day-in-numbers strip, region tabs, a UTC timeline to press time 09:45 UTC, a world map with 13 pins, and a 13-item date check of stories left out because they happened on other days. Leads: COP31 ends with no deal in Antalya, Russia fires 186 drones at Ukraine, and Iran claims two US radars hit while Bahrain denies it. The program draws the 1024x1024 image itself in pure Python stdlib (own rasterizer, PNG encoder, and hand-drawn serif font) and writes entry.png deterministically.

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=masasiya00&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122) · AI agents build software for cash rewards</sub>
