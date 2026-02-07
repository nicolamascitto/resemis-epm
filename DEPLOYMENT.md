# Deployment Guide (Free Hosting)

## Recommended: Streamlit Community Cloud (Free)

Streamlit Community Cloud is the fastest free option for a collaborative internal URL.

### 1) Push code to a public Git repository

Required files are already present:

- `streamlit_app.py`
- `requirements.txt`
- `.streamlit/config.toml`

### 2) Create app on Streamlit Community Cloud

1. Open: https://share.streamlit.io/
2. Connect your repository.
3. Set:
   - Repository: your `resemis-epm` repo
   - Branch: `main` (or `dev` for staging)
   - Main file path: `streamlit_app.py`
4. Click Deploy.

### 3) Share URL

After deploy, Streamlit gives a permanent app URL to share with colleagues.

## Optional Free Fallback: Hugging Face Spaces

You can deploy the same app as a Space with Streamlit SDK or Docker:

- https://huggingface.co/docs/hub/main/en/spaces-overview

## GitLab Push Workflow

If your collaboration standard requires GitLab, configure a remote and push:

```bash
git remote add gitlab <YOUR_GITLAB_REPO_URL>
git push -u gitlab dev
```

Then configure Streamlit Cloud from that GitLab mirror (or mirror GitLab -> GitHub for Streamlit Cloud).

## CI Recommendation

Add CI before opening to a larger team:

1. `python -m pytest -q`
2. `python -m py_compile streamlit_app.py ui/dashboard_data.py`
3. `python main.py run --scenario base`
