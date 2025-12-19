# How to Completely Disable Re-ID

## Problem
Even when you uncheck "Re-ID (Re-identification)" in the GUI, Re-ID may still be enabled because:

1. **Harmonic Mean** auto-enables Re-ID (required for it to work)
2. **Tracker Type** - Some trackers include Re-ID by default:
   - `deepocsort` = OC-SORT + Re-ID (includes Re-ID)
   - `strongsort` = StrongSORT (includes Re-ID)
   - `botsort` = ByteTrack + Re-ID (includes Re-ID)

## Solution: Complete Re-ID Disable

To **completely disable Re-ID**, you need to:

### Step 1: Uncheck Re-ID
- Go to **Tracking** tab
- **Uncheck** "Re-ID (Re-identification)" checkbox

### Step 2: Uncheck Harmonic Mean
- In **Tracking** tab
- **Uncheck** "Use Harmonic Mean Association"
- (Harmonic Mean requires Re-ID, so it will auto-enable Re-ID if checked)

### Step 3: Change Tracker Type
- In **Tracking** tab
- Change **Tracker Type** from `deepocsort` to one of:
  - **`bytetrack`** - Fast motion-based tracking (NO Re-ID)
  - **`ocsort`** - Better occlusion handling (NO Re-ID)

**Recommended**: Use **`bytetrack`** for fastest pure tracking without Re-ID.

### Step 4: Verify Settings
Before starting analysis, verify:
- ✅ Re-ID checkbox: **UNCHECKED**
- ✅ Harmonic Mean checkbox: **UNCHECKED**
- ✅ Tracker Type: **`bytetrack`** or **`ocsort`** (NOT `deepocsort`, `strongsort`, or `botsort`)

## Tracker Types Reference

| Tracker | Re-ID Included? | Speed | Best For |
|---------|----------------|-------|----------|
| **bytetrack** | ❌ No | ⚡ Fastest | Open play, fast processing |
| **ocsort** | ❌ No | ⚡ Fast | Better occlusion handling |
| **deepocsort** | ✅ Yes | 🐢 Slower | Best accuracy with Re-ID |
| **strongsort** | ✅ Yes | 🐢 Slowest | Maximum accuracy |
| **botsort** | ✅ Yes | 🐢 Slower | ByteTrack + Re-ID |

## What You'll See When Re-ID is Disabled

When Re-ID is properly disabled, you should **NOT** see these messages:
- ❌ "✓ Loaded torchreid model"
- ❌ "✓ Re-ID Tracker initialized"
- ❌ "✓ Re-ID tracker enabled"
- ❌ "Re-ID Filter Module initialized"

You **WILL** see:
- ✅ "Using tracker: bytetrack" (or ocsort)
- ✅ No Re-ID related messages

## For Post-Analysis Tagging Workflow

If you're using the **Post-Analysis Tagging Workflow**:
1. **Disable Re-ID** (follow steps above)
2. Run analysis - you'll get clean tracking data with track IDs only
3. Use **Consolidate IDs** to merge duplicate track IDs
4. Use **Track Review & Assign** to tag players
5. Build gallery from verified matches

This workflow is **much better** than tagging during analysis because:
- No false matches polluting gallery
- Full context when tagging
- Quality control before committing

## Troubleshooting

**If Re-ID still appears enabled after unchecking:**

1. Check if Harmonic Mean is checked (it auto-enables Re-ID)
2. Check tracker type (should be `bytetrack` or `ocsort`)
3. Restart the GUI to ensure settings are saved
4. Check the log output - it will show if Re-ID is being auto-enabled

**If you see warnings:**
- The system will now warn you if you disable Re-ID but use a tracker that includes it
- Switch to `bytetrack` or `ocsort` to avoid Re-ID completely

