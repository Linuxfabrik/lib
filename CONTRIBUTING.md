# Contributing


## Linuxfabrik Standards

The following standards apply to all Linuxfabrik repositories.


### Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).


### Issue Tracking

Open issues are tracked on GitHub Issues in the respective repository. In addition to the GitHub default labels (`bug`, `documentation`, `duplicate`, `enhancement`, `good first issue`, `help wanted`, `invalid`, `question`, `wontfix`), the following project-specific labels are used:

| Label | Use for |
|---|---|
| `build` | Packaging, build scripts, distribution artifacts. |
| `ci/cd` | Continuous integration, GitHub Actions workflows, release automation, test automation. |
| `dependencies` | Pull requests opened by Dependabot. |
| `github_actions` | Pull requests that update GitHub Actions workflow definitions or pinned action SHAs. |
| `python` | Pull requests that update Python dependencies. |

When opening a new issue, attach the label that matches the area of work. The `build` and `ci/cd` labels mirror the conventional commit scopes used in the same areas (`fix(build): ...`, `chore(ci/cd): ...`).


### Pre-commit

Some repositories use [pre-commit](https://pre-commit.com/) for automated linting and formatting checks. If the repository contains a `.pre-commit-config.yaml`, install [pre-commit](https://pre-commit.com/#install) and configure the hooks after cloning:

```bash
pre-commit install
```


### Commit Messages

Commit messages follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification:

```
<type>(<scope>): <subject>
```

If there is a related issue, append `(fix #N)`:

```
<type>(<scope>): <subject> (fix #N)
```

`<type>` must be one of:

- `chore`: Changes to the build process or auxiliary tools and libraries
- `docs`: Documentation only changes
- `feat`: A new feature
- `fix`: A bug fix
- `perf`: A code change that improves performance
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `style`: Changes that do not affect the meaning of the code (whitespace, formatting, etc.)
- `test`: Adding missing tests


### Changelog

Document all changes in `CHANGELOG.md` following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Sort entries within sections alphabetically.


### Language

Code, comments, commit messages, and documentation must be written in English.


### CI Supply Chain

GitHub Actions in `.github/workflows/` are pinned by commit SHA, not by tag. Dependabot's `github-actions` ecosystem keeps these pins up to date.

Python packages installed via `pip` inside workflows follow a two-tier policy:

- `pre-commit` is installed from a hash-pinned requirements file at `.github/pre-commit/requirements.txt`, generated with `pip-compile --generate-hashes --strip-extras` from `.github/pre-commit/requirements.in`. Dependabot's `pip` ecosystem watches that directory and maintains both files.
- One-shot installs such as `ansible-builder`, `build`, `mkdocs`, `pdoc`, and `ruff` in release, docs, or test workflows are version-pinned only (`package==X.Y.Z`) and kept fresh by Dependabot. Scorecard's `pipCommand not pinned by hash` findings for these are considered acceptable risk and may be dismissed.


### Coding Conventions

- Sort variables, parameters, lists, and similar items alphabetically where possible.
- Always use long parameters when using shell commands.
- Use RFC [5737](https://datatracker.ietf.org/doc/html/rfc5737), [3849](https://datatracker.ietf.org/doc/html/rfc3849), [7042](https://datatracker.ietf.org/doc/html/rfc7042#section-2.1.1), and [2606](https://datatracker.ietf.org/doc/html/rfc2606) in examples and documentation:
    - IPv4: `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`
    - IPv6: `2001:DB8::/32`
    - MAC: `00-00-5E-00-53-00` through `00-00-5E-00-53-FF` (unicast), `01-00-5E-90-10-00` through `01-00-5E-90-10-FF` (multicast)
    - Domains: `*.example`, `example.com`


---


## Python Library Guidelines


### PEP 8

We follow [PEP 8 -- Style Guide for Python Code](https://www.python.org/dev/peps/pep-0008/) where it makes sense.


### Docstrings

Libraries are documented using [numpydoc docstrings](https://numpydoc.readthedocs.io/en/latest/format.html#docstring-standard), so that `pydoc lib/base.py` produces useful output.


### PyLint

To improve code quality, we use [PyLint](https://www.pylint.org/):

```bash
pylint mylib.py
```

See [PyLint's message codes](http://pylint-messages.wikidot.com/all-codes) for reference.


### Unit Tests

Unit tests use the standard-library [`unittest`](https://docs.python.org/3/library/unittest.html) framework (not pytest, so the suite runs across the full Python matrix, py3.6-py3.14). The setup mirrors the [Linuxfabrik Monitoring Plugins](https://github.com/Linuxfabrik/monitoring-plugins) so both projects look identical, but the library is tested independently: each test imports the local source directly, no other repository is required.

#### Test directory structure

Each module under test gets its own directory under `tests/`, mirroring the monitoring-plugins `check-plugins/<name>/unit-test/` layout:

```
tests/db_sqlite/
├── lib                     # symlink to the repo root (../..), so `import lib.db_sqlite` resolves to the local source
└── unit-test/
    ├── run                 # the executable test file (unittest)
    └── fixtures/           # sample input files (only if needed)
```

The `lib` symlink plus `sys.path.insert(0, '..')` at the top of `run` make `import lib.<module>` load the working-tree source, so tests always exercise local changes.

#### Writing tests

* Cover **every public function**, **all keyword-argument combinations**, and the edge cases: zero, value and unit boundaries, very large, very small, negative, empty, and wrong data types. Use `assertRaises` where the function raises and assert the real value where it degrades gracefully.
* **Probe first, then assert.** Run the function and observe the actual output before writing the expectation; never guess.
* **Keep fixture tests hermetic.** Mock every network call, subprocess, socket and external service with `unittest.mock` (patch `lib.url.*`, `lib.shell.shell_exec`, etc.) and drive parsers from fixtures under `unit-test/fixtures/`. These run in a fraction of a second and cover the whole `tox` matrix.
* Only reach for **container-based tests** (via `lib.lftest` and testcontainers-python) when a function's behaviour really depends on a live service. For functions that talk to an application, use a Red Hat family container running the current LTS release of that application. Container tests are detected automatically and excluded from the fast matrix.

See `tests/human/unit-test/run` (pure functions) and `tests/db_sqlite/unit-test/run` (security edge cases) as reference implementations.

#### Running tests

```bash
# all fast (fixture) tests, used by tox
tools/run-unit-tests --no-container

# a single module
tools/run-unit-tests db_sqlite

# only the container tests (thin wrapper around --only-container)
tools/run-container-tests

# everything in parallel (lint + fast + container), aggregated
tools/run-all-tests

# the full Python matrix (py3.6-py3.14)
tools/run-tox-tests
```


### Commit Scopes

Use the library module name as commit scope:

```
fix(base.py): handle empty input in coe()
```

For the first commit of a new library, use `Add <library-name>`.
