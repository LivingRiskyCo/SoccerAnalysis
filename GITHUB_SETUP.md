# GitHub Setup Guide for Streamlit Deployment

## Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `soccer-analysis` (or your preferred name)
3. Description: "Soccer video analysis with player tracking and overlays"
4. Choose: **Public** (required for free Streamlit Cloud) or **Private** (if you have Streamlit Cloud for Teams)
5. **DO NOT** initialize with README, .gitignore, or license (we already have these)
6. Click "Create repository"

## Step 2: Connect Local Repository to GitHub

After creating the repository, GitHub will show you commands. Use these:

```bash
cd C:\Users\nerdw\soccer_analysis

# Add the remote repository (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/soccer-analysis.git

# Rename branch to main (GitHub's default)
git branch -M main

# Push your code
git push -u origin main
```

## Step 3: Deploy to Streamlit Cloud

1. Go to https://share.streamlit.io
2. Sign in with your GitHub account
3. Click "New app"
4. Select your repository: `YOUR_USERNAME/soccer-analysis`
5. Main file path: `streamlit_video_viewer.py`
6. App URL: `dsx-tracker` (or your preferred name)
7. Click "Deploy"

Your app will be available at: `https://dsx-tracker.streamlit.app`

## Alternative: Using GitHub CLI (if installed)

If you have GitHub CLI installed:

```bash
cd C:\Users\nerdw\soccer_analysis
gh repo create soccer-analysis --public --source=. --remote=origin --push
```

## Troubleshooting

**Authentication Issues?**
- Use GitHub Personal Access Token instead of password
- Or use SSH keys: `git remote set-url origin git@github.com:YOUR_USERNAME/soccer-analysis.git`

**Want to add more files later?**
```bash
git add .
git commit -m "Your commit message"
git push
```

