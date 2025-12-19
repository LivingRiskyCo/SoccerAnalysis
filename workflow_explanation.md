# Player Tagging Workflow Explanation

## Two Different Workflows

### Workflow 1: Track Review & Player Assignment → Playback Viewer (CSV-based)
**Question**: If I assign players in Track Review & Player Assignment, then load CSV in Playback Viewer, will players be tagged?

**Answer**: **PARTIALLY** - It depends on whether the CSV has a `player_name` column.

**How it works:**
1. Track Review & Player Assignment tool:
   - Loads CSV file (`20251001_184229_analyzed_tracking_data.csv`)
   - You assign player names to tracks
   - **BUT**: The assignments are stored in the tool's memory, NOT automatically written back to the CSV
   - You need to click **"Save Assignments as Anchor Frames"** to create a PlayerTagsSeed JSON file

2. Playback Viewer:
   - Loads CSV file directly
   - Checks for `player_name` column in CSV (line 1552 in playback_viewer.py)
   - If `player_name` column exists → displays player names
   - If `player_name` column doesn't exist → shows track IDs (#7, #10, etc.)

**Problem**: The CSV export from analysis does NOT include `player_name` column by default. So even if you assign players in Track Review, the CSV won't have those names unless you:
- Export a new CSV with player names, OR
- Use Workflow 2 (anchor frames)

### Workflow 2: Track Review → Convert to Anchor Frames → Analysis (Recommended)
**Question**: Should I tag players on video tracks, then use "Convert Tracks → Anchor Frames"?

**Answer**: **YES - This is the recommended workflow!**

**How it works:**
1. Track Review & Player Assignment:
   - Load CSV file
   - Assign player names to tracks
   - Click **"Save Assignments as Anchor Frames"**
   - This creates/updates `PlayerTagsSeed-{video_name}.json`

2. Run Analysis:
   - Analysis loads anchor frames from PlayerTagsSeed JSON
   - Anchor frames have confidence 1.00 (ground truth)
   - Players are protected from Re-ID reassignment
   - New CSV export will include player names (if code is updated)

3. Playback Viewer:
   - Can load either:
     - CSV file (if it has `player_name` column)
     - OR overlay metadata (which has player names)

## Recommended Workflow

**Best Practice:**
1. Run initial analysis to generate CSV
2. Open Track Review & Player Assignment tool
3. Load the CSV file
4. Assign player names to tracks
5. Click **"Save Assignments as Anchor Frames"** (creates PlayerTagsSeed JSON)
6. Re-run analysis (it will load anchor frames and maintain player identities)
7. Playback Viewer will show player names from either:
   - New CSV (if player_name column is added to export)
   - Overlay metadata (which has player names)

## Current Issue

The CSV export does NOT include `player_name` column. So:
- Workflow 1 (CSV-only) won't show player names in Playback Viewer
- Workflow 2 (Anchor Frames) is the correct approach

## Solution Needed

We should update the CSV export to include `player_name` column so both workflows work.

