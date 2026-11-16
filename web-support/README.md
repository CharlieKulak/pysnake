# PySnake in the browser

This folder builds the browser version of PySnake with [pygbag](https://pygame-web.github.io/).

| File | What it does |
| --- | --- |
| `build.sh` | Builds the browser game into `build/pysnake/build/web/` |
| `main.py` | The browser entry point that starts the game |
| `serve.py` | A plain file server for trying a build on your network (no accounts, records or versus) |
| `build/` | Build output. Ignored by git, safe to delete |

```sh
pip install -e . pygbag
web-support/build.sh
python web-support/serve.py
```

## On an OpenSnake server

Accounts, snake points, records and versus come from an [OpenSnake server](https://github.com/CharlieKulak/opensnake). To serve PySnake from one, copy the build into the server's `web-support/clients/<name>/`. For example, `clients/py/` is served at `/py/`. You can also unzip a PySnake release's web download there. The game talks to the server it was loaded from.
