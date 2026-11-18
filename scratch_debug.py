from sim_sequence.sample_data import get_sample_sequence
from sim_sequence.scheduler import schedule

if __name__ == "__main__":
    model = get_sample_sequence()
    scheduled = schedule(model)
    print(f"Successfully scheduled {len(scheduled.tasks)} tasks across {len(scheduled.resources)} resources!")
    max_t = max(t.end_time for t in scheduled.tasks)
    print(f"Total Cycle Time: {max_t:.1f}s vs Takt: {scheduled.settings.takt_time}s")
    for t in scheduled.tasks:
        print(f"{t.id:3s} [{t.resource:20s}] {t.name:45s} | {t.start_time:4.1f}s -> {t.end_time:4.1f}s ({t.duration}s) FS:{t.predecessors_fs}")
