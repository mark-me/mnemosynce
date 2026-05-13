# Acknowledgements

Mnemosynce is built on the shoulders of excellent open source work. Thank you
to the authors and contributors of the following projects.

## Core tools

| Tool | What it does in Mnemosynce |
|------|---------------------------|
| [rsync](https://rsync.samba.org/) | Powers every backup, retention, and sync operation — the engine underneath it all |
| [OpenSSH](https://www.openssh.com/) | Provides secure access to remote sources and destinations |

## Python libraries

| Library | License | What it does in Mnemosynce |
|---------|---------|---------------------------|
| [Flask](https://flask.palletsprojects.com/) | BSD-3-Clause | Web framework powering the dashboard and REST API |
| [Jinja2](https://jinja.palletsprojects.com/) | BSD-3-Clause | Template engine for the web UI and HTML email reports |
| [APScheduler](https://apscheduler.readthedocs.io/) | MIT | Runs scheduled backup jobs without an external cron daemon |
| [PyYAML](https://pyyaml.org/) | MIT | Parses and writes `backup_config.yml` |
| [pandas](https://pandas.pydata.org/) | BSD-3-Clause | Powers the run history aggregation shown on the dashboard |
| [NumPy](https://numpy.org/) | BSD-3-Clause | Numerical support for dashboard statistics |
| [python-dateutil](https://dateutil.readthedocs.io/) | Apache-2.0 | Flexible date parsing for schedule and log handling |
| [python-json-logger](https://github.com/madzak/python-json-logger) | BSD-2-Clause | Structured JSON log output |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | BSD-3-Clause | Loads environment variables from `.env` files |
| [gunicorn](https://gunicorn.org/) | MIT | Production WSGI server |
| [MarkupSafe](https://markupsafe.palletsprojects.com/) | BSD-3-Clause | Safe string escaping for Jinja2 |

## Documentation

| Tool | License | What it does |
|------|---------|-------------|
| [Zensical](https://github.com/peterdesmet/zensical) | MIT | MkDocs theme powering this documentation site |

## Container base image

The Docker image is built on
[`ghcr.io/astral-sh/uv:python3.13-alpine`](https://github.com/astral-sh/uv),
maintained by [Astral](https://astral.sh). Alpine Linux provides the minimal
runtime environment.

---

If you believe a credit is missing or incorrect, please open an issue or pull
request on [GitHub](https://github.com/mark-me/mnemosynce).
