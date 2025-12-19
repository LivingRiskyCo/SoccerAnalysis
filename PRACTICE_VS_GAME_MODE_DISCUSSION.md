# Practice vs Game Mode - Feature Discussion

## Overview

Add a setting to the Setup Wizard to distinguish between **Practice** and **Game** videos, with different team assignment and color matching strategies for each mode.

## Current System

### Team Color Configuration
- **Location**: `team_color_config.json` (via "Color Helper (Ball & Team)" in GUI)
- **Structure**: 
  ```json
  {
    "team_colors": {
      "team1": {
        "name": "Team 1",
        "hsv_ranges": {"lower": [...], "upper": [...]}
      },
      "team2": {
        "name": "Team 2", 
        "hsv_ranges": {"lower": [...], "upper": [...]}
      }
    }
  }
  ```

### Current Team Classification
- **Function**: `classify_player_team()` in `combined_analysis_optimized.py`
- **Method**: 
  1. Extract jersey region from player bbox
  2. Use K-means clustering to find dominant colors
  3. Compare HSV values against team HSV ranges
  4. Assign to team1 or team2 based on match score
- **Uniform Extraction**: `extract_uniform_colors()` extracts jersey/shorts/socks colors but not heavily used

### Player Gallery Integration
- Players have `team` field stored in `player_gallery.json`
- Team assignment happens during:
  - Setup Wizard tagging
  - Analysis (via `classify_player_team()`)
  - Manual correction

## Proposed Feature: Practice vs Game Mode

### Practice Mode
**Philosophy**: Flexible, player-centric team assignment

**Behavior**:
1. **Player-Based Team Assignment**
   - Each player can be assigned to a team individually
   - Team assignment based on player's actual jersey color (not strict uniform rules)
   - More forgiving color matching (wider HSV ranges)
   - Players can switch sides during practice

2. **Color Matching Strategy**
   - Use individual player's jersey color as reference
   - Learn colors per-player rather than per-team
   - Allow multiple colors per team (e.g., some players in pinnies, some in jerseys)
   - Store player-specific color profiles in Player Gallery

3. **Team Side Configuration**
   - "Set Team Sides" button/interface in Setup Wizard
   - Allow manual assignment: "Player X is on Team 1", "Player Y is on Team 2"
   - Visual side indicator (left/right or top/bottom of field)
   - Can change sides mid-practice

4. **Data Storage**
   - Store in `seed_config.json`: `"video_type": "practice"`
   - Store player-team assignments per frame or per session
   - Store player-specific color profiles

### Game Mode
**Philosophy**: Structured, uniform-based team assignment

**Behavior**:
1. **Uniform-Based Team Assignment**
   - Use pre-configured uniform settings (from Color Helper)
   - Strict HSV range matching based on team uniforms
   - All players on a team should match uniform colors
   - Enforce uniform consistency (jersey + shorts + socks)

2. **Color Matching Strategy**
   - Use team HSV ranges from `team_color_config.json`
   - Apply uniform color correction (accounting for lighting, shadows)
   - More strict matching thresholds
   - Cross-reference jersey, shorts, and socks colors

3. **Uniform Settings Integration**
   - Leverage existing "Color Helper (Ball & Team)" settings
   - Use uniform color profiles for better accuracy
   - Apply color correction based on uniform settings
   - Validate team assignments against uniform rules

4. **Data Storage**
   - Store in `seed_config.json`: `"video_type": "game"`
   - Reference uniform settings from `team_color_config.json`
   - Store team assignments with uniform validation

## Implementation Questions & Decisions Needed

### 1. Setup Wizard UI
**Where to add the setting?**
- [ ] At the very beginning (first screen)?
- [ ] In a "Video Settings" section?
- [ ] As a dropdown/radio buttons near the top?

**Options**:
```
┌─────────────────────────────────────┐
│ Video Type: ○ Practice  ○ Game     │
└─────────────────────────────────────┘
```

### 2. Practice Mode - Team Side Configuration
**How should users set team sides?**

**Option A: Per-Player Assignment**
- List all players
- Radio buttons: "Team 1" | "Team 2" | "Not Playing"
- Can change per frame

**Option B: Side-Based Assignment**
- Visual field representation
- Click/drag players to left/right side
- Auto-assigns to Team 1 or Team 2 based on side

**Option C: Color-Based with Manual Override**
- Auto-detect based on colors
- Manual override for any player
- "Set All Players" button

**Recommendation**: Option A (per-player assignment) - most flexible

### 3. Practice Mode - Color Learning
**How to learn player-specific colors?**

**Option A: Learn from Tagged Frames**
- When user tags a player, learn their jersey color
- Store in Player Gallery: `player_color_profile: {hsv_range: [...]}`
- Use for future matching

**Option B: Manual Color Selection**
- "Set Player Color" button
- User clicks on player's jersey in frame
- Extract and store color

**Option C: Hybrid**
- Auto-learn from tags
- Manual override available

**Recommendation**: Option C (hybrid) - best of both worlds

### 4. Game Mode - Uniform Integration
**How to use uniform settings more effectively?**

**Current**: Only jersey color is heavily used

**Proposed Enhancements**:
1. **Multi-Component Matching**
   - Match jersey + shorts + socks
   - Weighted scoring (jersey 70%, shorts 20%, socks 10%)
   - Require minimum match score

2. **Uniform Color Correction**
   - Account for lighting conditions
   - Adjust HSV ranges based on field lighting
   - Use uniform reference colors for correction

3. **Uniform Validation**
   - Flag players that don't match team uniform
   - Suggest corrections
   - Enforce consistency

**Questions**:
- Should we require all 3 components (jersey/shorts/socks) or just jersey?
- How strict should uniform matching be? (threshold values)
- Should we show uniform mismatch warnings?

### 5. Data Storage & Persistence

**Where to store video type?**
- `seed_config.json` (per-video)
- `project_config.json` (per-project)
- Both?

**Structure**:
```json
{
  "video_path": "...",
  "video_type": "practice" | "game",
  "practice_settings": {
    "team_sides": {
      "player_name": "team1" | "team2",
      ...
    },
    "player_colors": {
      "player_name": {
        "hsv_range": {...},
        "learned_from_frames": [...]
      }
    }
  },
  "game_settings": {
    "uniform_config": "team_color_config.json",
    "strict_matching": true,
    "require_uniform_validation": true
  }
}
```

### 6. Analysis Integration

**How does this affect `combined_analysis_optimized.py`?**

**Practice Mode**:
- Use player-specific color profiles if available
- Fall back to team colors if player color not learned
- More lenient matching thresholds
- Allow team reassignment during analysis

**Game Mode**:
- Use team HSV ranges strictly
- Apply uniform color correction
- Validate against uniform settings
- Stricter matching thresholds
- Flag uniform mismatches

**Code Changes Needed**:
- Modify `classify_player_team()` to check video type
- Add player-specific color matching for practice mode
- Add uniform validation for game mode
- Update team assignment logic

### 7. Player Gallery Integration

**How to store player-specific colors?**

**Current Structure**:
```json
{
  "player_id": {
    "name": "...",
    "team": "team1" | "team2",
    ...
  }
}
```

**Proposed Addition**:
```json
{
  "player_id": {
    "name": "...",
    "team": "team1" | "team2",
    "color_profile": {
      "practice_mode": {
        "hsv_range": {"lower": [...], "upper": [...]},
        "learned_from": ["frame_123", "frame_456"],
        "confidence": 0.85
      },
      "game_mode": {
        "uniform_reference": "team1_uniform",
        "jersey_color": "blue",
        "shorts_color": "white",
        "socks_color": "blue"
      }
    }
  }
}
```

### 8. Backward Compatibility

**Existing videos without video_type?**
- Default to "game" mode (current behavior)
- Or prompt user to select on first open
- Or auto-detect based on team color config presence

**Recommendation**: Default to "game" for backward compatibility

## Implementation Plan (Pending Approval)

### Phase 1: Setup Wizard UI
1. Add "Video Type" selection (Practice/Game)
2. Store in `seed_config.json`
3. Load/save with project

### Phase 2: Practice Mode - Team Side Configuration
1. Add "Set Team Sides" interface
2. Per-player team assignment
3. Store in `seed_config.json`
4. Visual indicators in Setup Wizard

### Phase 3: Practice Mode - Color Learning
1. Learn colors from tagged frames
2. Store in Player Gallery
3. Use for team classification
4. Manual color override option

### Phase 4: Game Mode - Uniform Enhancement
1. Multi-component uniform matching
2. Uniform color correction
3. Uniform validation
4. Warning system for mismatches

### Phase 5: Analysis Integration
1. Update `classify_player_team()` for both modes
2. Add player-specific color matching
3. Add uniform validation
4. Update team assignment logic

## Questions for Discussion

1. **UI/UX**: Where should the "Video Type" selector appear? Beginning of Setup Wizard?

2. **Practice Mode**: How should team sides be configured? Per-player assignment or side-based?

3. **Color Learning**: Auto-learn from tags, manual selection, or both?

4. **Game Mode**: How strict should uniform matching be? Require all components or just jersey?

5. **Backward Compatibility**: Default to "game" mode for existing videos?

6. **Player Gallery**: Store player-specific colors in Player Gallery or separate config?

7. **Analysis**: Should analysis mode be selectable independently, or always follow Setup Wizard setting?

8. **Visual Feedback**: How should we show team assignments in Setup Wizard? Color-coded? Side indicators?

## Next Steps

1. **Review this document** - Confirm understanding and approach
2. **Answer questions** - Provide preferences for implementation decisions
3. **Prioritize features** - Which parts are most important?
4. **Implementation** - Start with Phase 1 (UI) and iterate

---

**Please review and provide feedback on:**
- Overall approach (makes sense?)
- UI/UX preferences
- Implementation priorities
- Any additional requirements or concerns

