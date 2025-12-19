# Player Matching Criteria and Hierarchy

## Overview
The system uses a multi-stage matching process with strict constraints to ensure accurate player identification. Matches are evaluated in a specific order of priority.

---

## Stage 1: Initial Re-ID Matching

### 1.1 Re-ID Feature Extraction
- Extract 512-dimensional feature vectors from each detection
- Features are computed using OSNet (torchreid) model
- Features capture visual appearance (jersey, body shape, etc.)

### 1.2 Gallery Matching
- Compare detection features against all players in the Player Gallery
- Calculate cosine similarity scores (0.0 to 1.0)
- **Minimum threshold**: Must meet GUI Re-ID Similarity Threshold (default: 0.5, adjustable)

### 1.3 Team Color Filtering (Applied During Matching)
- **Detection team classification**: Each detection is classified as "Gray" or "Blue" based on jersey color
- **Gallery team filtering**: Players are filtered by their assigned team in the gallery
  - If detection is "Gray" → only match players from "Gray" team in gallery
  - If detection is "Blue" → only match players from "Blue" team in gallery
- **Color similarity boost**: Same-team matches get +10% similarity boost

### 1.4 Top Match Selection
- Select the player with the highest similarity score that meets the threshold
- Store top 5 alternative matches for conflict resolution

---

## Stage 2: Constraint Checking (Before Assignment)

### 2.1 High Confidence Lock Check
**Purpose**: Prevent unnecessary updates to already-identified players

**Lock Levels**:
- **Very High Confidence (≥0.80)**: Locked - requires 0.25+ improvement AND 90+ frames
- **High Confidence (≥0.75)**: Locked - requires 0.20+ improvement AND 60+ frames  
- **Medium/Low Confidence (<0.75)**: Can update with 0.15+ improvement AND 30+ frames

**Result**: If track already has a name and doesn't meet update criteria → **SKIP**

### 2.2 Jersey Constraint Check
**Purpose**: Ensure only ONE player per jersey number on the field at a time

**Checks**:
1. Is this jersey number already assigned to another active track?
   - If YES → **JERSEY CONFLICT**
   - If NO → Continue
2. Is the jersey available for reassignment? (original track is inactive)
   - If YES → Allow reassignment
   - If NO → **JERSEY CONFLICT**

**Result**: If jersey conflict → Try alternative matches

### 2.3 Team Constraint Check
**Purpose**: Ensure players can only be on ONE team at a time

**Checks**:
1. **Global team assignment**: Is this player already assigned to a different team?
   - If player is on "Gray" team globally → Cannot assign to "Blue" detection
   - If player is on "Blue" team globally → Cannot assign to "Gray" detection
   - If YES → **TEAM CONFLICT**

2. **Detection vs. Player team match**: Does detection team match player's gallery team?
   - If detection is "Gray" but player is "Blue" in gallery → **TEAM CONFLICT**
   - If detection is "Blue" but player is "Gray" in gallery → **TEAM CONFLICT**

**Result**: If team conflict → Try alternative matches

---

## Stage 3: Conflict Resolution

### 3.1 Alternative Match Selection
**When**: Jersey conflict OR team conflict detected

**Process**:
1. Iterate through top 5 alternative matches (sorted by similarity)
2. For each alternative:
   - Check if similarity ≥ GUI threshold
   - Check jersey constraint (no conflict)
   - Check team constraint (no conflict)
   - If all checks pass → **USE THIS ALTERNATIVE**
3. If no conflict-free alternative found → **NO MATCH** (track remains unnamed)

### 3.2 Jersey Persistence Boost
**Purpose**: Maintain consistency when a track previously had a jersey

**Process**:
- If track had jersey #6 before → Boost matches with jersey #6 to the top
- This prevents Rocco #6 from being reassigned to Gunnar #5 due to Re-ID confusion

---

## Stage 4: Match Application

### 4.1 Assignment Conditions
A match is applied ONLY if:
- ✅ No jersey conflict OR conflict resolved with alternative
- ✅ No team conflict OR conflict resolved with alternative
- ✅ Track has no name OR update criteria met

### 4.2 Global Registration
When a match is applied:
1. **Player name** → Assigned to track
2. **Jersey number** → Registered globally (`jersey_to_track_global`)
3. **Team assignment** → Registered globally (`player_to_team_global`)
4. **Confidence** → Stored for future update decisions

---

## Complete Matching Hierarchy (Priority Order)

### **Level 1: Initial Matching**
1. **Re-ID similarity** (must meet GUI threshold, default: 0.5)
2. **Team color filtering** (detection team must match player team)
3. **Color similarity boost** (+10% for same-team matches)

### **Level 2: Constraint Validation**
4. **High confidence lock** (prevent unnecessary updates)
5. **Jersey uniqueness** (only one player per jersey globally)
6. **Team uniqueness** (player can only be on one team)

### **Level 3: Conflict Resolution**
7. **Alternative match search** (try top 5 alternatives)
8. **Jersey persistence boost** (prefer previous jersey assignments)

### **Level 4: Final Assignment**
9. **Match application** (assign name, register jersey & team globally)
10. **Confidence storage** (store for future update decisions)

---

## Example Scenarios

### Scenario 1: Perfect Match
```
Detection: Similarity=0.75, Team=Gray, Jersey=6
Player: Rocco Piazza, Team=Gray, Jersey=6
Result: ✅ MATCH (no conflicts)
```

### Scenario 2: Jersey Conflict
```
Detection: Similarity=0.70, Team=Gray, Jersey=6
Player: Rocco Piazza, Team=Gray, Jersey=6
Global: Jersey #6 already assigned to Track #3 (active)
Result: ⚠ JERSEY CONFLICT → Try alternative match
```

### Scenario 3: Team Conflict
```
Detection: Similarity=0.68, Team=Blue, Jersey=11
Player: Carson Gribble, Team=Blue, Jersey=11
Global: Carson already on "Gray" team (Track #8)
Result: ⚠ TEAM CONFLICT → Try alternative match
```

### Scenario 4: High Confidence Lock
```
Detection: Similarity=0.72, Team=Gray, Jersey=6
Player: Rocco Piazza, Team=Gray, Jersey=6
Track: Already named "Rocco Piazza" (similarity=0.78, 20 frames ago)
Result: 🔒 LOCKED (requires 0.20+ improvement AND 60+ frames)
```

### Scenario 5: Successful Alternative
```
Primary Match: Rocco Piazza (similarity=0.70) → JERSEY CONFLICT
Alternative #1: Gunnar Nesbitt (similarity=0.65) → JERSEY CONFLICT
Alternative #2: Anay Rao (similarity=0.63) → ✅ NO CONFLICTS
Result: ✅ MATCH with Anay Rao
```

---

## Key Parameters (GUI Adjustable)

| Parameter | Default | Purpose |
|-----------|---------|---------|
| **Re-ID Similarity Threshold** | 0.5 | Minimum similarity to consider a match |
| **High Confidence Lock (≥0.75)** | 0.20 improvement + 60 frames | Prevent updates to high-confidence matches |
| **Very High Confidence Lock (≥0.80)** | 0.25 improvement + 90 frames | Almost never update very high-confidence matches |
| **Medium/Low Confidence Update** | 0.15 improvement + 30 frames | Allow updates for lower-confidence matches |

---

## Summary

**Matching Priority**:
1. **Similarity** (must meet threshold)
2. **Team match** (detection team = player team)
3. **Jersey uniqueness** (no duplicate jerseys)
4. **Team uniqueness** (player on one team only)
5. **Confidence lock** (prevent unnecessary updates)

**Conflict Resolution**:
- Try top 5 alternatives
- Prefer jersey persistence
- Require all constraints satisfied

**Result**: Accurate, consistent player identification with strict uniqueness constraints.

