"""Quick schedule dump for visual verification."""
from sim_sequence.loader import load_yaml
from sim_sequence.scheduler import schedule

model = load_yaml("inputs/example_sequence.yaml")
schedule(model)

print(f"{'Task':<22} {'Resource':<14} {'Start':>6} {'End':>6} {'Dur':>5}")
print("-" * 58)
for t in model.tasks:
    print(f"{t.id:<22} {t.resource:<14} {t.start_time:>6.1f} {t.end_time:>6.1f} {t.duration:>5.1f}")

print()
cycle_time = max(t.end_time for t in model.tasks)
takt = model.settings.takt_time
print(f"Cycle time : {cycle_time:.1f}s")
print(f"Takt time  : {takt:.1f}s")
print(f"Utilization: {cycle_time/takt*100:.1f}%  {'✓ OK' if cycle_time <= takt else '✗ OVER TAKT'}")
