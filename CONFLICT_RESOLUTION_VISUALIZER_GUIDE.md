# Conflict Resolution Visualizer - How It Works

## Overview

The Conflict Resolution Visualizer is a real-time tool that:
1. **Detects** when the same player is assigned to multiple tracks
2. **Visualizes** current track assignments and conflicts
3. **Allows** you to correct assignments before errors propagate
4. **Applies** corrections to forward progression immediately

---

## How Conflicts Are Detected

### During Analysis (Real-Time)

**Location**: `combined_analysis_optimized.py` (lines ~6477-6506)

**Process**:
1. **Global Player Tracking**: The system maintains `player_to_track_global` - a mapping of `{player_name: track_id}`
2. **Conflict Detection**: When assigning a player to a track:
   ```python
   if player_name in player_to_track_global:
       assigned_track = player_to_track_global[player_name]
       if assigned_track != track_id and assigned_track is still active:
           # CONFLICT DETECTED!
           player_conflict = True
   ```
3. **Conflict Reporting**: When detected:
   ```python
   shared_state.report_player_conflict(
       player_name,      # e.g., "Rocco Piazza"
       assigned_track,   # e.g., Track #6 (already has Rocco)
       track_id,         # e.g., Track #12 (trying to assign Rocco here)
       current_frame     # Frame number where conflict occurred
   )
   ```

**Example**:
- Frame 3200: Rocco Piazza is on Track #6
- Frame 3201: System tries to assign Rocco to Track #12
- **Conflict detected**: Same player on two active tracks!
- **Reported to GUI**: `shared_state.report_player_conflict("Rocco Piazza", 6, 12, 3201)`

---

## How Conflicts Are Visualized

### GUI Display (`live_viewer_controls.py`)

**Tab**: "👤 Player Corrections"

**Three Main Sections**:

#### 1. **Player Conflicts List** (Top Section)
- **Shows**: All unresolved conflicts
- **Format**: `⚠ {player_name} on tracks: #{track1}, #{track2} (Frame {frame})`
- **Color Coding**:
  - Red background: Conflict summary
  - Blue background: Individual track entries (clickable)
- **Auto-refresh**: Every 2 seconds
- **Source**: `shared_state.get_player_conflicts()`

**Example Display**:
```
⚠ Rocco Piazza on tracks: #6, #12 (Frame 3201)
  → Track #6: Rocco Piazza
  → Track #12: Rocco Piazza
```

#### 2. **Current Player Assignments** (Middle Section)
- **Shows**: All active track assignments
- **Format**: `Track #{track_id}: {player_name} {status}`
- **Status Indicators**:
  - `✅ CORRECTED`: Correction applied
  - `⏳ PENDING`: Correction queued (waiting for next frame)
  - (no status): Normal assignment
- **Auto-refresh**: Every 2 seconds
- **Source**: `shared_state.get_current_track_assignments()`

**Example Display**:
```
Track #1: Yusuf Cankara
Track #6: Rocco Piazza ⏳ PENDING
Track #12: Rocco Piazza
Track #15: Merritt Jones ✅ CORRECTED
```

#### 3. **Applied Corrections History** (Bottom Section)
- **Shows**: All corrections you've made
- **Format**: `Track #{track_id} → {player_name} (Frame {frame})`
- **Purpose**: Track what you've fixed

---

## How Corrections Are Applied

### Step 1: User Makes Correction

**In GUI**:
1. Enter Track ID (e.g., `12`)
2. Select correct player (e.g., `"James Carlson"`)
3. Click "✅ Apply Correction"

**What Happens**:
```python
# In live_viewer_controls.py
shared_state.apply_player_correction(track_id, correct_player)
# Stores in: pending_corrections[track_id] = correct_player
```

### Step 2: Analysis Picks Up Correction

**Location**: `combined_analysis_optimized.py` (lines ~6883-6926)

**Process**:
1. **Before assigning player to track**, analysis checks:
   ```python
   pending_corrections = shared_state.get_pending_corrections()
   if track_id in pending_corrections:
       correct_player = pending_corrections[track_id]
   ```

2. **If correction exists**:
   - **Override** the automatic assignment
   - **Use** the user-specified player
   - **Log**: `🔧 USER CORRECTION: Track #12 'Rocco Piazza' → 'James Carlson'`

3. **If correction is `None`** (from conflict resolution):
   - **Unassign** the player from that track
   - **Clear** all global mappings
   - **Prevent** future assignments to that track

### Step 3: Forward Progression Updated

**Immediate Effects**:
- ✅ Track assignment changed for **current frame**
- ✅ Global mappings updated (`player_to_track_global`, `jersey_to_track_global`)
- ✅ Future frames use the corrected assignment
- ✅ Breadcrumb stored (preference for this track)

**Breadcrumb System**:
```python
shared_state.set_player_track_breadcrumb(player_name, track_id, confidence=1.0)
```
- **Future matching** will prefer this track for this player
- **Confidence boost**: +0.15 to +0.25 similarity score
- **Persists** across frames until you change it

---

## Conflict Resolution Workflow

### Method 1: Manual Correction

1. **See conflict** in conflicts list
2. **Enter Track ID** and **select correct player**
3. **Click "Apply Correction"**
4. **Result**: Track assignment changed immediately

### Method 2: Conflict Resolution Dialog

1. **Double-click** a conflict in the list
2. **Dialog opens** asking to confirm track
3. **Click "✅ Confirm Track"** or **"❌ Not This Track"**
4. **Result**: 
   - If confirmed: Sets breadcrumb, resolves conflict
   - If rejected: You can manually correct it

### Method 3: Choose Selected Track

1. **Select** a conflict in the list
2. **Click "✅ Choose Selected Track"**
3. **Dialog opens** with radio buttons for each track
4. **Select** the correct track
5. **Click "Confirm"**
6. **Result**: 
   - Correct track gets the player
   - Other tracks are unassigned
   - Conflict marked as resolved

---

## Real-Time Updates

### Auto-Refresh System

**Assignments**: Refreshes every 2 seconds
- Gets latest from `shared_state.get_current_track_assignments()`
- Shows pending corrections with `⏳ PENDING` status
- Updates when analysis applies corrections

**Conflicts**: Refreshes every 2 seconds
- Gets latest from `shared_state.get_player_conflicts()`
- Only shows unresolved conflicts
- Removes conflicts when resolved

**Thread Safety**:
- Uses `window.after_idle()` for GUI updates
- Prevents threading errors
- Safe to update from analysis thread

---

## How It Prevents Errors

### Before Correction

**Problem**:
- Frame 3200: Rocco on Track #6
- Frame 3201: System assigns Rocco to Track #12
- **Result**: Rocco appears on both tracks (WRONG!)

### After Correction

**Solution**:
1. **Conflict detected** at Frame 3201
2. **Reported to GUI** immediately
3. **You see conflict** in real-time
4. **You correct**: Track #12 → James Carlson
5. **Next frame**: Track #12 = James Carlson (CORRECT!)
6. **Future frames**: Track #12 stays with James (breadcrumb)

### Forward Progression

**Corrections affect**:
- ✅ **Current frame**: Assignment changed immediately
- ✅ **Next frames**: Correct assignment continues
- ✅ **Future matching**: Breadcrumb guides Re-ID
- ✅ **Global state**: All mappings updated

---

## Data Flow Diagram

```
Analysis Thread                    Shared State                    GUI Thread
─────────────────                  ────────────                    ──────────

Detects Conflict
  │
  ├─> report_player_conflict()
  │   └─> player_conflicts[player] = {tracks: [6, 12], ...}
  │
  ├─> update_track_assignment()
  │   └─> current_track_assignments[track_id] = player_name
  │
  └─> (continues analysis)

                                    get_player_conflicts()
                                    └─> Returns unresolved conflicts
                                    
                                    get_current_track_assignments()
                                    └─> Returns all track assignments
                                    
                                    
User clicks "Apply Correction"
  │
  ├─> apply_player_correction()
  │   └─> pending_corrections[track_id] = correct_player
  │
  └─> (GUI updates display)


Analysis Thread (next frame)
  │
  ├─> get_pending_corrections()
  │   └─> Gets user corrections
  │
  ├─> Applies correction
  │   └─> Overrides automatic assignment
  │
  └─> Updates global mappings
      └─> Forward progression corrected!
```

---

## Key Features

### 1. **Real-Time Detection**
- Conflicts detected **as they happen**
- No waiting for analysis to complete
- Immediate notification in GUI

### 2. **Visual Feedback**
- **Color coding**: Red for conflicts, blue for clickable tracks
- **Status indicators**: Shows pending/applied corrections
- **Auto-refresh**: Always shows current state

### 3. **Immediate Application**
- Corrections applied on **next frame**
- No need to restart analysis
- Forward progression updated instantly

### 4. **Breadcrumb System**
- Corrections create **preferences**
- Future matching **prefers** corrected tracks
- Confidence boost for preferred tracks

### 5. **Conflict Prevention**
- **Prevents** same player on multiple tracks
- **Unassigns** player from wrong tracks
- **Maintains** global consistency

---

## Example Scenario

### Initial State
- **Frame 1000**: Rocco Piazza on Track #6
- **Frame 1001**: System tries to assign Rocco to Track #12
- **Conflict detected!**

### GUI Shows
```
⚠ Player Conflicts:
  ⚠ Rocco Piazza on tracks: #6, #12 (Frame 1001)
    → Track #6: Rocco Piazza
    → Track #12: Rocco Piazza

Current Assignments:
  Track #6: Rocco Piazza
  Track #12: Rocco Piazza
```

### You Correct It
1. Enter Track ID: `12`
2. Select Player: `"James Carlson"`
3. Click "Apply Correction"

### Result
```
Current Assignments:
  Track #6: Rocco Piazza
  Track #12: James Carlson ✅ CORRECTED

Applied Corrections:
  Track #12 → James Carlson (Frame 1001)
```

### Forward Progression
- **Frame 1002+**: Track #12 = James Carlson (correct!)
- **Breadcrumb**: James prefers Track #12
- **Future matching**: System prefers Track #12 for James

---

## Technical Details

### Shared State Functions

**Conflict Reporting**:
```python
shared_state.report_player_conflict(player_name, assigned_track, conflicting_track, frame_num)
```

**Getting Conflicts**:
```python
conflicts = shared_state.get_player_conflicts()
# Returns: {player_name: {'tracks': [track1, track2], 'frame': frame_num, 'resolved': False}}
```

**Applying Corrections**:
```python
shared_state.apply_player_correction(track_id, correct_player)
# Stores in: pending_corrections[track_id] = correct_player
```

**Resolving Conflicts**:
```python
shared_state.resolve_player_conflict(player_name, correct_track_id)
# Marks conflict as resolved
# Unassigns player from other tracks
# Sets breadcrumb
```

### Analysis Integration

**Checking Corrections** (every frame):
```python
pending_corrections = shared_state.get_pending_corrections()
if track_id in pending_corrections:
    correct_player = pending_corrections[track_id]
    # Override automatic assignment
```

**Updating Assignments** (every frame):
```python
shared_state.update_track_assignment(track_id, player_name)
# Updates current_track_assignments
# Notifies GUI to refresh
```

---

## Summary

The Conflict Resolution Visualizer is a **real-time, interactive tool** that:

1. ✅ **Detects** conflicts as they happen
2. ✅ **Visualizes** current state and conflicts
3. ✅ **Allows** you to correct assignments immediately
4. ✅ **Applies** corrections to forward progression
5. ✅ **Prevents** errors from propagating
6. ✅ **Learns** from your corrections (breadcrumbs)

**It's not fake or mock data** - it's a real-time interface to the running analysis that lets you guide and correct tracking as it happens!

