# Professional Sports Analysis Export Guide

Convert your tracking data to formats used by professional coaches, scouts, and broadcasters.

## 🎯 Quick Start

```bash
# Export to all formats
python export_to_professional_formats.py --csv "20-sec_analyzed_tracking_data.csv" --fps 24

# Export to specific format
python export_to_professional_formats.py --csv "20-sec_analyzed_tracking_data.csv" --format tracab
```

## 📊 Supported Formats

### 1. **SportsCode / Hudl** (XML)
**Used by:** College & professional coaches, NCAA teams, NFL teams

**What it does:**
- Timeline-based video analysis
- Tagging and coding system
- Statistical reports
- Playlist creation

**Import instructions:**
1. Open Hudl SportsCode
2. File → Import → XML Data
3. Select the `*_sportscode.xml` file
4. Map timeline markers to your video

**Best for:** 
- ✓ Coaching reviews
- ✓ Play-by-play analysis
- ✓ Creating highlight reels

---

### 2. **TRACAB / Second Spectrum** (JSON)
**Used by:** NBA, NFL, Premier League, Champions League

**What it does:**
- Real-time player tracking
- Speed and distance metrics
- Broadcast overlays (TV graphics)
- Advanced analytics

**Import instructions:**
1. Use Second Spectrum API endpoint
2. Or import into ChyronHego TRACAB system
3. JSON follows TRACAB v4.0 schema

**Best for:**
- ✓ TV broadcast graphics
- ✓ Performance analytics
- ✓ Scouting reports

**Data included:**
- Frame-by-frame positions (meters)
- Player speed and acceleration
- Ball possession tracking
- Field coordinates (center-origin)

---

### 3. **Dartfish / Nacsport** (XML)
**Used by:** Olympic teams, professional academies, sports institutes

**What it does:**
- Video tagging and annotation
- Tactical analysis
- Performance feedback
- Side-by-side comparison

**Import instructions:**
1. Open Dartfish or Nacsport
2. File → Import → Tracking Data
3. Select the `*_dartfish.xml` file
4. Sync with your video file

**Best for:**
- ✓ Tactical breakdowns
- ✓ Player development
- ✓ Movement analysis

---

### 4. **Stats Perform (Opta)** (JSON)
**Used by:** EPL, La Liga, Serie A, MLS (official data provider)

**What it does:**
- Event data (passes, shots, tackles)
- xG (expected goals) models
- Player ratings
- League statistics

**Import instructions:**
1. Upload to Opta platform
2. Or integrate via Stats Perform API
3. JSON follows Opta F24 schema

**Best for:**
- ✓ Match statistics
- ✓ Player scouting
- ✓ Betting analytics

**Analytics included:**
- Possession time per player
- Distance covered
- Speed metrics
- Event timeline

---

## 🔧 Advanced Usage

### Batch Export Multiple Files

```bash
# Export all CSV files in a directory
for file in *.csv; do
    python export_to_professional_formats.py --csv "$file" --fps 24
done
```

### Custom FPS

```bash
# For high-speed cameras (120 FPS)
python export_to_professional_formats.py --csv "data.csv" --fps 120

# For slow-motion (30 FPS)
python export_to_professional_formats.py --csv "data.csv" --fps 30
```

### Specify Output Directory

```bash
python export_to_professional_formats.py \
    --csv "20-sec_analyzed_tracking_data.csv" \
    --output-dir "./professional_exports" \
    --format tracab
```

---

## 📁 Output Files

After running the export, you'll get:

```
my_video_analyzed_tracking_data_sportscode.xml    # Hudl SportsCode
my_video_analyzed_tracking_data_tracab.json       # Second Spectrum
my_video_analyzed_tracking_data_dartfish.xml      # Dartfish/Nacsport
my_video_analyzed_tracking_data_statsperform.json # Stats Perform
```

---

## 🔍 Data Format Details

### Your CSV Format (Input)
```csv
frame,timestamp,ball_x,ball_y,ball_detected,ball_x_m,ball_y_m,ball_trajectory_angle,ball_speed_mps,player_id,player_x,player_y,confidence,possession_player_id,distance_to_ball
0,0.0,1920,1080,True,12.3,10.5,45.2,5.3,1,1850,950,0.95,1,0.15
```

### TRACAB JSON (Output Example)
```json
{
  "metadata": {
    "provider": "Custom Soccer Tracker",
    "fps": 24.0,
    "pitch_size": [24.6, 20.0],
    "coordinate_system": "center_origin"
  },
  "frames": [
    {
      "frame_id": 0,
      "timestamp": 0.0,
      "ball": {
        "x": 12.3,
        "y": 10.5,
        "speed": 5.3,
        "possession": 1
      },
      "players": [
        {
          "player_id": 1,
          "x": 11.8,
          "y": 9.2,
          "speed": 4.5
        }
      ]
    }
  ]
}
```

---

## 🎬 Integration Workflows

### Workflow 1: Coaching Analysis (SportsCode)
1. Record practice/game → `practice.mp4`
2. Run tracking: `python combined_analysis_optimized.py --input practice.mp4 ...`
3. Export: `python export_to_professional_formats.py --csv practice_tracking_data.csv --format sportscode`
4. Import XML into SportsCode
5. Tag plays, create playlists, generate reports

### Workflow 2: TV Broadcast (TRACAB)
1. Record match → `match.mp4`
2. Run tracking with high accuracy
3. Export: `--format tracab`
4. Send JSON to broadcast team
5. They overlay graphics on TV feed

### Workflow 3: Scouting Report (Stats Perform)
1. Record player highlights → `player_23.mp4`
2. Run tracking
3. Export: `--format statsperform`
4. Upload to scouting platform
5. Generate player comparison reports

---

## 🔐 Professional Platform Access

| Platform | Access | Cost | Best For |
|----------|--------|------|----------|
| **Hudl SportsCode** | License required | $1,000-5,000/year | Coaching |
| **Second Spectrum** | Enterprise only | Custom pricing | Broadcast |
| **Dartfish** | License required | $500-2,000/year | Video analysis |
| **Stats Perform** | API access | Contact sales | Data analytics |
| **Nacsport** | License required | $300-1,500/year | Amateur to pro |

### Free Alternatives:
- **LongoMatch** (open-source, reads Dartfish XML)
- **TaggedData** (free tagging tool)
- **Soccerway** (community scouting)

---

## 🚀 Next Steps

1. **Test the export:**
   ```bash
   python export_to_professional_formats.py --csv "your_tracking_data.csv"
   ```

2. **Verify the output:**
   - Check file size (should be reasonable)
   - Open XML in a text editor to inspect
   - Validate JSON at jsonlint.com

3. **Import into platform:**
   - Follow platform-specific import instructions above
   - Sync with your video file
   - Verify timestamps match

4. **Share with coaches/scouts:**
   - Email the XML/JSON files
   - Include the original video
   - Provide field calibration info

---

## ⚠️ Important Notes

- **Coordinate systems vary:** TRACAB uses center-origin (0,0 = center), some use top-left
- **FPS must match:** Export FPS must match your video FPS
- **File size:** TRACAB JSON can be large for long videos (1-2 MB per minute)
- **Team IDs:** Currently all players are team 0 (add team classification for better results)
- **Jersey numbers:** Extracted from player ID (e.g., ID 36 → Jersey #36)

---

## 🛠️ Customization

Edit `export_to_professional_formats.py` to:

1. **Add team classification:**
   ```python
   "team_id": 1 if player['id'] in home_team_ids else 2
   ```

2. **Add jersey numbers:**
   ```python
   "jersey_number": jersey_mapping.get(player['id'], player['id'] % 100)
   ```

3. **Include player names:**
   ```python
   "player_name": player_names.get(player['id'], f"Player {player['id']}")
   ```

4. **Add event detection:**
   ```python
   if detect_pass(prev_possession, current_possession):
       add_event("pass", timestamp, player_id)
   ```

---

## 📞 Support

- **Format issues:** Check schema documentation for each platform
- **Import errors:** Verify FPS and coordinate system
- **File size:** Use `--format` to export only needed formats

---

## 📚 Resources

- [TRACAB Specification](https://tracab.com/developers)
- [SportsCode User Guide](https://hudl.com/support/sportscode)
- [Dartfish Academy](https://www.dartfish.com/academy)
- [Stats Perform API Docs](https://developer.statsperform.com)

**Now your tracking data is ready for professional sports analysis platforms!** 🎯⚽📊

