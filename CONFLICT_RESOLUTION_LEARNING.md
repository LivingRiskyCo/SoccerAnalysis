# Conflict Resolution & Learning Feedback Loop

## How Manual Corrections Teach the System

When you manually tag/correct players at conflict points, the system learns in **multiple ways** that compound over time:

---

## 1. **Immediate Breadcrumb Creation** 🍞

**What happens:**
- You correct: "Track #6 should be Gunnar Nesbitt, not Track #1"
- System creates a **breadcrumb**: `Gunnar Nesbitt → Track #6 (confidence: 1.0)`

**How it helps:**
- Next time the system sees Track #6, it gets a **+0.05 to +0.15 similarity boost** for Gunnar Nesbitt
- This makes Track #6 more likely to match Gunnar Nesbitt in future frames
- The boost increases with each confirmation (up to 0.15)

**Code location:** `shared_state.py` → `set_player_track_breadcrumb()`

---

## 2. **Route Locking** 🔒

**What happens:**
- If you correct a player in early frames (first 1000 frames), the route is **locked**
- Example: "Gunnar Nesbitt → Track #1" at Frame 50 gets locked

**How it helps:**
- Locked routes get **+0.20 to +0.25 similarity boost** (strongest boost)
- This ensures early-frame assignments are strongly preferred
- Prevents the system from switching to wrong tracks later

**Code location:** `shared_state.py` → `lock_early_route()`

---

## 3. **Gallery Track History** 📚

**What happens:**
- When a player is correctly assigned to a track, it's recorded in the gallery
- Example: "Gunnar Nesbitt was on Track #1 (5 times), Track #6 (2 times)"

**How it helps:**
- Gallery provides **+0.05 to +0.15 boost** based on frequency
- If Gunnar was on Track #1 many times before, future matches get boosted
- This creates a "memory" of which tracks each player prefers

**Code location:** `player_gallery.py` → `update_track_history()`, `get_track_history_boost()`

---

## 4. **Re-ID Feature Learning** 🎯

**What happens:**
- When you correct a match, the system learns from that detection
- Re-ID features (appearance, shape, movement) are updated in the gallery
- Reference frames are added to the player's profile

**How it helps:**
- Better Re-ID features = better similarity scores = fewer conflicts
- The system learns what each player "looks like" from your corrections
- Over time, similarity scores improve (0.60 → 0.75 → 0.85)

**Code location:** `combined_analysis_optimized.py` → Auto-learning section

---

## 5. **Combined Boost System** 🚀

**All boosts stack together:**

```
Final Similarity = Base Re-ID Similarity 
                 + Locked Route Boost (0.20-0.25)  ← Highest priority
                 + User Breadcrumb Boost (0.05-0.15)
                 + Gallery History Boost (0.05-0.15)
                 + Jersey Number Boost (0.05)
                 + Early Frame Boost (0.10)
```

**Example:**
- Base similarity: 0.65 (Gunnar Nesbitt on Track #6)
- Locked route: +0.20 (Gunnar was on Track #6 in early frames)
- User breadcrumb: +0.10 (You corrected this before)
- Gallery history: +0.10 (Gunnar was on Track #6 many times)
- **Final: 1.05** (capped at 1.0) = **Very high confidence match**

---

## The Learning Feedback Loop 🔄

```
┌─────────────────────────────────────────────────────────┐
│ 1. CONFLICT DETECTED                                     │
│    "Gunnar on Track #1 AND Track #6"                     │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│ 2. YOU MANUALLY CORRECT                                  │
│    "Track #6 = Gunnar Nesbitt"                           │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│ 3. SYSTEM LEARNS (Multiple Ways)                        │
│    ✓ Breadcrumb created (Track #6 preferred)            │
│    ✓ Route locked (if early frame)                       │
│    ✓ Gallery history updated                             │
│    ✓ Re-ID features learned                              │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│ 4. FUTURE MATCHES IMPROVED                              │
│    Track #6 gets +0.20-0.40 boost for Gunnar            │
│    Similarity: 0.65 → 0.85-1.05                         │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│ 5. FEWER CONFLICTS                                       │
│    System correctly assigns Gunnar to Track #6           │
│    No more conflicts at this point                       │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│ 6. REPEAT FOR OTHER CONFLICTS                           │
│    Each correction makes system smarter                  │
│    Conflicts decrease with each replay                  │
└─────────────────────────────────────────────────────────┘
```

---

## Why It Gets Faster Over Time ⚡

### First Run:
- No breadcrumbs, no history
- System relies only on Re-ID similarity (0.60-0.70)
- Many conflicts occur
- You correct 10-20 conflicts

### Second Run:
- Breadcrumbs from first run (+0.10 boost)
- Gallery history (+0.10 boost)
- Better Re-ID features (learned from corrections)
- **Fewer conflicts** (maybe 5-10)

### Third Run:
- Strong breadcrumbs (+0.15 boost)
- Rich gallery history (+0.15 boost)
- Excellent Re-ID features (0.75-0.85 similarity)
- **Even fewer conflicts** (maybe 2-5)

### Fourth+ Run:
- System "remembers" all your corrections
- Combined boosts make matches very confident
- **Minimal conflicts** (0-2, mostly edge cases)

---

## Best Practices for Faster Learning 🎯

### 1. **Correct Conflicts Early**
- Fix conflicts in the first 1000 frames → Routes get locked
- Locked routes have the strongest boost (0.20-0.25)

### 2. **Be Consistent**
- If you correct "Track #6 = Gunnar" once, stick with it
- Repeated corrections increase breadcrumb confidence

### 3. **Use Conflict Resolution Window**
- The GUI shows conflicts in real-time
- Double-click to jump to conflict frame
- Correct immediately while analysis is running

### 4. **Let System Learn**
- After corrections, let the system process more frames
- It will learn from your corrections and improve

---

## Example: Real Conflict Resolution

**Frame 100: Conflict Detected**
```
⚠ Player conflict: Gunnar Nesbitt already assigned to Track #1, cannot assign to Track #6
```

**You Correct:**
- Open Conflict Resolution window
- See: "Gunnar Nesbitt on tracks: #1, #6"
- Choose: Track #6 is correct
- System: Creates breadcrumb, locks route, updates gallery

**Frame 200: Same Situation**
```
🔍 Gallery match: Track #6 → Gunnar Nesbitt (similarity: 0.65)
   + Locked route boost: +0.20
   + User breadcrumb: +0.10
   + Gallery history: +0.10
   = Final: 1.05 (capped at 1.0) ✓ MATCHED
```

**Result:** No conflict! System correctly assigns Gunnar to Track #6.

---

## Summary

**Yes, manually tagging at conflict points will:**
1. ✅ Create breadcrumbs that boost future matches
2. ✅ Lock routes for early-frame corrections
3. ✅ Update gallery history
4. ✅ Improve Re-ID features
5. ✅ Reduce conflicts with each replay

**The system learns exponentially:**
- Each correction helps multiple future matches
- Combined boosts make matches very confident
- Fewer conflicts = less manual work needed
- System becomes self-correcting over time

**Think of it as:**
- First run: You teach the system
- Second run: System remembers your teachings
- Third run: System applies your teachings automatically
- Fourth+ run: System is an expert, rarely needs help






