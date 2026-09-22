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

The hooks only see staged files, so a file nobody edits is never checked. Running them over everything with `pre-commit run --all-files` is therefore a repository-wide rewrite, and it belongs in a commit of its own: the last one arrived inside an unrelated change and its damage surfaced weeks later. The `Linuxfabrik: Apply pre-commit hooks repository-wide` workflow does that run whenever the hook configuration changes and opens a pull request for it, so there is normally nothing left to do by hand.


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

The audience is a Linux system engineer with 30 seconds to decide whether an update is worth it. Write for that reader:

* **Lead with highlights.** Begin every release section with three to five sentences of running text, directly below the version heading and above the first `###` section. Cover what drives the update decision, including any manual step it requires. No bullet list, no issue links, no repetition of the individual entries. A release with only a handful of entries does not need one, since the entries themselves already fit on a screen.
* **State the change before its scope.** Up to five affected components keep the `component: what changed` form. From six on, put the statement first and close it with either a collective name (`all *-version checks`) or the components in parentheses, so the entry is understood from its first line. These broad entries come first in their subsection, ahead of the alphabetically sorted per-component entries.
* **One sentence per entry.** `Added`, `Changed` and `Fixed` say what an administrator notices. Root cause, reproduction steps and internal reasoning belong in the commit body and the issue.
* **Migration instructions only under `Breaking Changes`.** Wording such as "rename x to y" or "set z to restore the previous behaviour" anywhere else means the entry sits in the wrong section. Entries under `Breaking Changes` may run longer than one sentence.
* **Leave out contributor-only changes.** Lockfile and pin bumps, Dependabot and pre-commit configuration, GitHub Actions bumps and test infrastructure are covered by the git history and the pull request. Keep an entry only where an administrator sees the effect, for example when it changes the released artifact.

A release section starts like this:

```markdown
## [v6.1.0] - 2026-09-15

**Highlights:** Two long-standing sources of false alarms are gone, and container workloads are now covered. Cumulative counters are reported as rates instead of totals, so any dashboard built on them has to be re-imported.

### Added
```

The scope rule, on an entry affecting 43 components. Instead of:

```markdown
* about-me, borgbackup, deb-lastactivity, file-ownership, fs-xfs-stats, getent, ...: `--always-ok` to force an OK result
```

write:

```markdown
* `--always-ok` forces an OK result on 43 further components (about-me, borgbackup, deb-lastactivity, ...)
```


### Language

Code, comments, commit messages, and documentation must be written in English.


### CI Supply Chain

GitHub Actions in `.github/workflows/` are pinned by commit SHA, not by tag. Dependabot's `github-actions` ecosystem keeps these pins up to date.

Python packages installed via `pip` inside workflows follow a two-tier policy:

- `pre-commit` is installed from a hash-pinned requirements file at `.github/pre-commit/requirements.txt`, generated with `pip-compile --allow-unsafe --generate-hashes --strip-extras` from `.github/pre-commit/requirements.in`. Dependabot's `pip` ecosystem watches that directory and maintains both files.
- Every other tool a workflow installs with `pip` (`ansible-builder`, `build`, `mkdocs`, `pdoc`, `ruff`, `tox`, ...) follows the same model: a version pin in `.github/<name>/requirements.in`, a hash-pinned `requirements.txt` generated from it the same way, `pip install --require-hashes --requirement .github/<name>/requirements.txt` in the workflow, and a Dependabot `pip` entry for that directory. Dependabot does not read `run:` lines, so a version pinned there (`package==X.Y.Z`) is never updated, and a Scorecard `pipCommand not pinned by hash` finding on it is a real one.


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


### Text Encoding and Decoding

Convert between `bytes` and `str` through `lib.txt.to_text()` and `lib.txt.to_bytes()`, not with bare `.decode()` / `.encode()`, so the encoding policy stays in one place.

Decoding external bytes whose real encoding is not reliably known (subprocess stdout/stderr, WinRM and PowerShell output, file contents, sensor payloads) and that later end up in the plugin's printed result: pass `errors='strict_or_latin1'`.

```python
text = lib.txt.to_text(raw_bytes, errors='strict_or_latin1')
```

This decodes as UTF-8 and, on any invalid byte, retries the whole input as Latin-1. Latin-1 maps every byte `0x00`-`0xFF` one-to-one to a real Unicode scalar, so it never fails and re-encodes cleanly when the plugin prints its result.

Do **not** leave such data on the default handler (`errors=None`, which maps to `surrogateescape`). `surrogateescape` turns an invalid byte into a lone surrogate that decodes without error but raises `UnicodeEncodeError` later, at the stdout re-encode. That moves the crash away from the cause and makes it hard to diagnose (see [Linuxfabrik/lib#256](https://github.com/Linuxfabrik/lib/issues/256)).

When the source declares its encoding, decode with that codec first and only fall back. `url.fetch()` already does this for response bodies (declared HTTP charset, Latin-1 fallback only when none is declared), and `shell.py` decodes Windows subprocess output as UTF-8 where it is valid and in the OEM code page otherwise, because a program on Windows picks the code page of its piped output itself.

Encoding text back to bytes for stdin, hashing, sockets, or a base64 input: use `to_bytes()`. Base64 output is pure ASCII, so `to_text(base64.b64encode(...))` needs no special handler.


### Security

Most security advisories filed against the [Linuxfabrik Monitoring Plugins](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories) were rooted in this library, and every one of them affected all consumers at once. A function here is called with values nobody sanitized, from processes that may run as root, against servers nobody vouches for. Write it for that.

**Two attackers.** Check every function against both:

* A local, unprivileged account that makes a process running as root (e.g. via sudo) call the function. It controls every argument, and every file and directory it can create, `/tmp` included.
* The remote system the function talks to: a server, a management controller, a storage appliance. A malicious or compromised one controls every byte of its responses, including status codes, headers, redirects and links.

**Fix the invariant, not the report.** An advisory names one channel. The fix has to close the rule behind it. Before changing code:

1. State the invariant in one sentence, for example "a credential never leaves the origin it was given for".
2. List every channel through which it can break (for a credential: headers, request body, query string, cookies, URL userinfo, each redirect status code, error messages) and check each one against the source of the library underneath, not against its documentation.
3. Write one test per channel that fails without the fix. Run it against the unfixed code before trusting it.
4. Search the whole library for the same class, not only the reported function.

The header fix for [GHSA-4jc5-g844-4x33](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-4jc5-g844-4x33) left the request body open ([GHSA-pq9x-4pp3-p5r9](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-pq9x-4pp3-p5r9)), and the state database fix for [GHSA-r35r-fpx2-jgr4](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-r35r-fpx2-jgr4) left a migration path open ([GHSA-w2gg-hx6w-24w3](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-w2gg-hx6w-24w3)). Both were follow-up reports on a fix that closed only the channel it was shown.

* **Arguments are hostile.** Check the type, reject what does not fit, and return `(False, message)` instead of repairing the value. A string builder is not harmless: its output becomes a URL that is fetched, a command that is run, or a link that is clicked.
* **Responses are hostile.** Never take a request target from a response. Build a follow-up URL only from a relative path, with scheme, host and port pinned to the base URL the caller supplied (`redfish.build_url()`, [GHSA-96fx-pqc3-28xv](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-96fx-pqc3-28xv)). An endpoint announced in a discovery document is rebuilt from the caller's configuration, not used as is (`keycloak.obtain_admin_token()`, [GHSA-88fj-95f7-w68m](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-88fj-95f7-w68m)). Nothing is read without a bound: `url.fetch()` refuses a body beyond `max_bytes`, counted after decompression.
* **Credentials stay with their origin, on every channel.** `url.fetch()` drops caller headers and refuses to resend a request body when a redirect crosses the origin. The proxy is chosen by `net.get_proxy()`, which honours every exception the operator set, never by the HTTP library's own reading of the environment. A new HTTP path keeps all of these guarantees. A credential never appears in a returned message or an error: redact URLs (`url._redact_url()`), and name only the program when a command fails (`shell.shell_exec()`).
* **Commands are argv lists.** `shell.shell_exec()` takes a list and runs without a shell ([GHSA-798h-hpph-m24j](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-798h-hpph-m24j)). A value in a positional slot is guarded with `shell.safe_cli_value()`, so it cannot be read as an option. A program that runs code from its options (`apt-get -o`, `ssh -o`, an interpreter) is only safe with fixed arguments ([GHSA-8w6w-23mq-h8rg](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-8w6w-23mq-h8rg)).
* **A caller-chosen path is confined at every edge.** Canonicalize with `realpath()`, check containment with `disk.is_within()`, and open with symlink following disabled (`disk.read_file(allowed_roots=..., nofollow=True)`). This applies to the directory scanned, every entry found inside it and the final read, not only the first one. A filename check binds the symlink's name, never its target ([GHSA-f54c-p5vg-mr5c](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-f54c-p5vg-mr5c), [GHSA-q8c8-wxhc-3h4c](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-q8c8-wxhc-3h4c)). Where a module reads files on a caller's behalf, the confinement belongs in the module (`logsource` and its `allowed_roots`).
* **A hidden input is a live input.** Whatever the argument parser accepts is reachable in production, suppressed help text or not. `lftest.test()` reads fixtures only from below the running program's own `unit-test/` directory ([GHSA-rh9c-rqvg-f7pr](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-rh9c-rqvg-f7pr)).
* **No predictable paths in shared directories.** State and cache files live in a per-user directory that `db_sqlite.get_db_dir()` validates with `os.lstat()`: a real directory, owned by the effective user, no group or other permissions ([GHSA-r35r-fpx2-jgr4](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-r35r-fpx2-jgr4)). Never rename, move or open a file taken from `/tmp`; `os.rename()` moves a planted symlink along ([GHSA-w2gg-hx6w-24w3](https://github.com/Linuxfabrik/monitoring-plugins/security/advisories/GHSA-w2gg-hx6w-24w3)). Code that runs only once, such as a migration or a cleanup, gets the same scrutiny.
* **Fail closed.** When a guard cannot decide, refuse with a message that says why. Do not drop the offending part and carry on, since that sends something the caller never built.
* **Guards on third-party internals are tested against the real library.** Where a guard wraps a private attribute of a dependency (the redirect hooks of `httpx`), a test runs the real dependency through it, so a rename in a new release fails the test instead of silently switching the guard off. Record the versions the guard was verified against in a comment next to it.


### PyLint

To improve code quality, we use [PyLint](https://www.pylint.org/):

```bash
pylint mylib.py
```

See [PyLint's message codes](http://pylint-messages.wikidot.com/all-codes) for reference.


### Unit Tests

Unit tests use the standard-library [`unittest`](https://docs.python.org/3/library/unittest.html) framework (not pytest, so the suite runs across the full Python matrix, py3.9-py3.14, matching the library's `requires-python`). The setup mirrors the [Linuxfabrik Monitoring Plugins](https://github.com/Linuxfabrik/monitoring-plugins) so both projects look identical, but the library is tested independently: each test imports the local source directly, no other repository is required.

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
* **A passing test prints nothing.** A test that provokes a message on purpose, such as an abort, captures it (`contextlib.redirect_stdout()`) and asserts on it, and a test closes what it opens: connections, files, processes. `tools/run-unit-tests` then shows nothing but its progress, and a traceback or a `ResourceWarning` in between points at a real problem instead of drowning in noise. A release checks exactly that.
* **A test does not depend on the terminal it runs in.** CI and a piped run have none, a developer has one, and output differs between them: from Python 3.14 on, argparse colours its help on a terminal. Measure what a reader sees (strip the escape sequences), or fix the environment the test needs (`COLUMNS`, `NO_COLOR`) inside the test.
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

# the full Python matrix (py3.9-py3.14)
tools/run-tox-tests
```


### Commit Scopes

Use the library module name as commit scope:

```
fix(base.py): handle empty input in coe()
```

For the first commit of a new library, use `Add <library-name>`.
