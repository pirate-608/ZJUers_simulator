**Standard:**

```text
<type>(<scope>): <subject>
# ↑ Max 50 chars. Imperative mood. No trailing period.

<body>
# ↑ Blank line
# Explain the motivation and context ("why", not "how").
# Wrap lines at 72 characters.

<footer>
# ↑ Blank line (only if applicable)
# Issue references: Closes #123, Fixes #456
# Breaking changes: BREAKING CHANGE: <explain incompatibility and migration>
```

**Example 1: Atomic Feature:**

```text
feat(auth): add jwt token refresh mechanism

- implement automatic token refresh before expiration
- add refresh token endpoint to api client

Closes #89
```

**Example 2: Atomic Bug Fix:**

```text
fix(ui): resolve button overlap on mobile viewports

The submit button overlapped the footer on screens < 768px. 
Added a media query to adjust bottom margin and flex-direction.

Fixes #102
```

**Example 3: Breaking Change:**

```text
refactor(api): migrate user service to typescript

Migrated the entire user service module from JavaScript to TypeScript 
to improve type safety and developer experience.

BREAKING CHANGE: The user service API now requires typed request 
objects. Update all callers to use the `UserRequest` interface 
instead of plain objects.
```

