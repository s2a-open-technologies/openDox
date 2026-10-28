## Description

Brief description of the change. Reference related issues with
`Closes #123` where applicable.

## Type of change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing
      functionality to not work as expected)
- [ ] Documentation change
- [ ] Refactoring / maintenance

## Checklist

- [ ] Code follows the project conventions (ruff for backend, ESLint for
      frontend — run `ruff check --fix .` / `npm run lint` locally)
- [ ] Tests added or updated for the change
      (`pytest tests/` / `cd frontend && npm run test`)
- [ ] Database models changed? Alembic migration created
      (`alembic revision --autogenerate -m "..."`) and both `upgrade` and
      existing-data paths verified
- [ ] New/changed SQLModel tables registered in
      `backend/components/models/__init__.py`
- [ ] No real patient data, credentials, or secrets in code, tests,
      screenshots, or logs
- [ ] Entry added under `## [Unreleased]` in `CHANGELOG.md`
- [ ] AGPL/SPDX license header added to new source files
- [ ] `AGENTS.md` updated if dev commands, architecture, or gotchas changed
- [ ] "Kein Medizinprodukt" disclaimer preserved in recording dialog and
      transcript view, and the first-login gate stays unbypassable
      (only relevant if auth/disclaimer flow was touched)

## Contributor License Agreement

Ohne Haken kann der Pull Request nicht übernommen werden. /
*The pull request cannot be merged without this box ticked.*

- [ ] Ich habe die [CLA](https://github.com/s2a-open-technologies/openDox/blob/master/CLA.md) gelesen und stimme ihr für diesen und alle
      künftigen Beiträge zu. / I have read the [CLA](https://github.com/s2a-open-technologies/openDox/blob/master/CLA.md) and agree to it
      for this and all future contributions.
