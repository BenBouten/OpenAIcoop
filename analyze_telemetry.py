import json
import sys
from collections import Counter
from pathlib import Path

# Find latest event log
log_dir = Path("logs/telemetry")
event_logs = sorted(log_dir.glob("events_*.jsonl"))

if not event_logs:
    sys.stdout.write("No event logs found\n")
    sys.exit(0)

latest_log = event_logs[-1]
sys.stdout.write(f"Analyzing: {latest_log.name}\n")
sys.stdout.write("=" * 80 + "\n\n")

# Parse events
events = []
with open(latest_log, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except:
                pass

if not events:
    sys.stdout.write("No valid events found\n")
    sys.exit(0)

sys.stdout.write(f"TOTAL EVENTS: {len(events)}\n")
sys.stdout.write(f"Time range: tick {events[0]['tick']} to {events[-1]['tick']}\n")
duration = events[-1]['tick'] - events[0]['tick']
sys.stdout.write(f"Duration: {duration} ticks (~{duration/1000:.1f}s)\n\n")

# Categories
categories = Counter(e['category'] for e in events)
sys.stdout.write("EVENT CATEGORIES:\n")
for cat, count in sorted(categories.items()):
    pct = (count / len(events)) * 100
    sys.stdout.write(f"  {cat:15s}: {count:5d} ({pct:5.1f}%)\n")

# AI events
ai_events = [e for e in events if e['category'] == 'AI']
if ai_events:
    sys.stdout.write(f"\n{'='*80}\n")
    sys.stdout.write(f"AI BEHAVIOR ANALYSIS ({len(ai_events)} events)\n")
    sys.stdout.write(f"{'='*80}\n\n")
    
    threats = [e for e in ai_events if e['event_type'] == 'THREAT_DETECTED']
    prey = [e for e in ai_events if e['event_type'] == 'PREY_ACQUIRED']
    
    sys.stdout.write(f"Threats detected: {len(threats)}\n")
    if threats:
        dists = [e['details']['dist'] for e in threats if 'dist' in e['details']]
        if dists:
            sys.stdout.write(f"  Avg distance: {sum(dists)/len(dists):.1f}\n")
            sys.stdout.write(f"  Range: {min(dists):.1f} - {max(dists):.1f}\n")
        
        entities = Counter(e['entity_id'] for e in threats)
        sys.stdout.write(f"  Most threatened (top 5):\n")
        for eid, cnt in entities.most_common(5):
            sys.stdout.write(f"    {eid}: {cnt}\n")
    
    sys.stdout.write(f"\nPrey spotted: {len(prey)}\n")
    if prey:
        dists = [e['details']['dist'] for e in prey if 'dist' in e['details']]
        if dists:
            sys.stdout.write(f"  Avg distance: {sum(dists)/len(dists):.1f}\n")
            sys.stdout.write(f"  Range: {min(dists):.1f} - {max(dists):.1f}\n")
        
        entities = Counter(e['entity_id'] for e in prey)
        sys.stdout.write(f"  Most active hunters (top 5):\n")
        for eid, cnt in entities.most_common(5):
            sys.stdout.write(f"    {eid}: {cnt}\n")

# Behavior
behavior = [e for e in events if e['category'] == 'BEHAVIOR']
if behavior:
    sys.stdout.write(f"\n{'='*80}\n")
    sys.stdout.write(f"BEHAVIOR ACTIVITIES ({len(behavior)} events)\n")
    sys.stdout.write(f"{'='*80}\n\n")
    
    activities = Counter(e['details']['name'] for e in behavior)
    for activity, count in activities.most_common():
        pct = (count / len(behavior)) * 100
        sys.stdout.write(f"  {activity:25s}: {count:5d} ({pct:5.1f}%)\n")

# Carcass
carcass = [e for e in events if e['category'] == 'CARCASS']
if carcass:
    sys.stdout.write(f"\n{'='*80}\n")
    sys.stdout.write(f"CARCASS DECOMPOSITION ({len(carcass)} events)\n")
    sys.stdout.write(f"{'='*80}\n\n")
    
    transitions = [(e['details']['from'], e['details']['to']) for e in carcass]
    for (f, t), cnt in Counter(transitions).most_common():
        sys.stdout.write(f"  {f:15s} -> {t:15s}: {cnt}\n")

sys.stdout.write(f"\n{'='*80}\n")
sys.stdout.write("ANALYSIS COMPLETE\n")
sys.stdout.write(f"{'='*80}\n")
