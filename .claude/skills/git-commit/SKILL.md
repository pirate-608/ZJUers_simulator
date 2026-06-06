---
name: git-commit
description: Analyze code changes and generate professional Git Commit Messages adhering to the industry-standard Conventional Commits specification.
argument-hint: "[--tag <tagname>] [--push]"
---

# Git Commit Skill

## 🎯 Objective
This skill guides the AI to analyze staged code changes (`git diff`) and generate clear, semantic, and structurally sound Git Commit Messages following the **Conventional Commits** specification.

## 📜 Core Principles
1. **Atomic**: One commit must do exactly one thing. 
2. **Clear**: Explain **what** was done and **why**, rather than just describing mechanical code changes.
3. **Imperative Mood**: The subject line must use the imperative mood (e.g., "Add feature", not "Added feature" or "Adds feature"), as if giving a command to the codebase.
4. **Length Limits**: Subject line ≤ 50 characters. Body lines ≤ 72 characters for optimal terminal readability.
5. **No Trailing Punctuation**: Do not end the subject line with a period (`.`).

## ⚙️ Execution Flow (Instructions for AI)
When requested to generate a commit message, you **MUST** follow this exact branching logic:

### Step 1: Analyze Atomicity (CRITICAL)
Review the provided `git diff` or code changes. 
- **IF** the changes contain multiple unrelated modifications (e.g., fixing a bug in `auth` AND updating documentation in `README`), **STOP**. 
  - **Action**: Output *only* a brief, polite warning: *"⚠️ The staged changes appear to contain multiple unrelated modifications. For best practices, please split them into separate atomic commits before I generate the message."* **Do not** generate a commit message template.
- **ELSE** (the changes are atomic or logically grouped), proceed to Step 2.

### Step 2: Determine Metadata
- **Type**: Select the most appropriate type from the [Type List] below.
- **Scope (Optional)**: Extract the specific module/component affected (e.g., `auth`, `ui`, `api`).

### Step 3: Generate Output (STRICT TEMPLATE)
If Step 1 passed, you **MUST** output the commit message strictly adhering to the template below. Do not add conversational filler (like "Here is your commit message:") before or after the template.

## 📚 Type List
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Formatting, white-space, missing semi-colons (no logic change)
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `build`: Changes affecting the build system or external dependencies
- `ci`: Changes to CI configuration files and scripts
- `chore`: Other changes that don't modify `src` or `test` files
- `revert`: Reverts a previous commit

### Step 4: Handle Git Tag (Conditional - ONLY if user requested)
After outputting the commit message template, **IF** the user explicitly requested a tag (e.g., "create tag v1.0.0", "tag this commit", or via a `--tag` parameter), execute the following logic:

1. **Create the tag locally**: Run `git tag <tagname>`
2. **Check for existing tag**: If the tag already exists, output a warning:
   - *"⚠️ Tag '<tagname>' already exists. Force recreate? (yes/no)"*
   - **IF** user confirms, run `git tag -f <tagname>`
3. **Push the tag (Conditional)**: 
   - **IF** user also requested push (or `--push` is present), run `git push origin <tagname>`
   - **IF** pushing to remote and tag already exists remotely, use `git push origin <tagname> --force` (with user confirmation)
4. **If no tag requested**: Skip this entire step silently.

**Important**: Tag creation is a **separate operation** from commit creation. The commit message template is always output first, then tag logic executes only on user request.
---

## 📝 Commit Message Template

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

## 🚫 Anti-Patterns to Avoid
- ❌ `update code` (Too vague)
- ❌ `Fixed the bug` (Not imperative, lacks context)
- ❌ `feat: add new feature.` (Trailing period)
- ❌ Generating a single commit message for unrelated changes (violates Step 1).
- ❌ Adding conversational text like "Sure, here is your commit message:" around the template.

## 📚 Additional Resources

- **Commit Examples**: See `references/commit-examples.md` for real-world commit message samples.
- **Tag Handling Examples**: See `references/tag-handling-examples.md` for the exact structure.