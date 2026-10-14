# PromptCheck GitHub Action

Run continuous prompt checks, evaluations, and regression tests inside GitHub Actions.

## Example Workflow

```yaml
name: Prompt CI

on: [push, pull_request]

jobs:
  check-prompts:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run PromptCheck
        uses: ./action
        with:
          config: "promptcheck.yaml"
          api-url: "https://api.promptcheck.dev"
```
