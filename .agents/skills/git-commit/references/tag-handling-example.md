## 📌 Tag Handling Logic Reference

| User Request | Action |
| :--- | :--- |
| "Commit with tag v1.0.0" | Output template → create tag `v1.0.0` |
| "Commit, push, and tag v2.0.0" | Output template → create tag → push tag |
| "Tag this commit as beta" | Output template → create tag `beta` |
| Tag already exists | Warn and ask for force recreate |
| No tag mentioned | Skip tag logic entirely |

**Tag naming conventions** (suggest to user if they ask):
- Version tags: `v1.0.0`, `v2.3.4`
- Release candidates: `v1.0.0-rc1`
- Hotfix tags: `hotfix-1.2.3`
- Custom tags: `beta`, `stable`, `legacy-v2`