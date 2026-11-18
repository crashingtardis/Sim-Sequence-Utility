import openpyxl
import re
from pathlib import Path
from sim_sequence.models import GlobalSettings, Resource, SequenceModel, Task
from sim_sequence.scheduler import schedule

def load_honda_excel(path: str | Path) -> SequenceModel:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb['Sheet1'] if 'Sheet1' in wb.sheetnames else wb.active

    # 1. Parse Resource mappings and tasks from table
    resources_dict = {}
    raw_tasks = []
    cur_res_code = None
    cur_res_name = None

    for r in range(13, ws.max_row + 1):
        res_code = ws.cell(r, 2).value   # col B
        item_num = ws.cell(r, 3).value   # col C
        res_name = ws.cell(r, 4).value   # col D
        start_int = ws.cell(r, 5).value  # col E
        desc = ws.cell(r, 7).value       # col G
        dur = ws.cell(r, 20).value       # col T
        if dur is None:
            dur = ws.cell(r, 21).value   # col U fallback

        if res_code:
            cur_res_code = str(res_code).strip().lower()
        if res_name:
            cur_res_name = str(res_name).strip()
            resources_dict[cur_res_code] = cur_res_name

        if item_num is not None and desc is not None:
            raw_tasks.append({
                'res_code': cur_res_code,
                'res_name': cur_res_name,
                'item': int(item_num),
                'desc': str(desc).strip(),
                'duration': float(dur) if dur is not None else 0.0,
                'start_int': str(start_int).strip() if start_int else '',
            })

    # Resource colors for the 6 Honda resources
    honda_colors = {
        'operator 1': '#1F4E78',      # Blue
        'geo tool 1': '#9C27B0',      # Purple
        'rbt 1 (geo weld)': '#4CAF50',# Green
        'rbt 2 (geo weld)': '#FF9800',# Orange
        'rbt 3 (mh)': '#00BCD4',      # Cyan
        'unload conv': '#795548',     # Brown
    }

    resources = [
        Resource(id=name, color=honda_colors.get(name.lower(), '#607D8B'))
        for name in resources_dict.values()
    ]

    # Map res_code -> res_name
    res_code_to_name = {code: name for code, name in resources_dict.items()}

    # Assign IDs: e.g. a1, a2, b1, b2, c1, ...
    task_id_map = {}
    tasks = []
    
    # We group tasks by resource to handle sequential steps within the same resource
    tasks_by_res = {}
    for rt in raw_tasks:
        tid = f"{rt['res_code']}{rt['item']}"
        task_id_map[(rt['res_code'], rt['item'])] = tid
        tasks_by_res.setdefault(rt['res_code'], []).append(tid)

    for rt in raw_tasks:
        tid = f"{rt['res_code']}{rt['item']}"
        res_name = res_code_to_name[rt['res_code']]
        predecessors_fs = []

        # 1. Sequential predecessor on same resource (item k depends on item k-1)
        if rt['item'] > 1:
            prev_tid = f"{rt['res_code']}{rt['item']-1}"
            predecessors_fs.append(prev_tid)

        # 2. Cross-resource start interlocks from 'start_int'
        raw_int = rt['start_int'].lower()
        if raw_int and raw_int != 'n/a':
            # split on comma or slash
            tokens = [t.strip() for t in re.split(r'[,/]+', raw_int) if t.strip()]
            for tok in tokens:
                # normalize tokens like '4d' -> 'd4'
                m = re.match(r'^(\d+)([a-zA-Z]+)$', tok)
                if m:
                    tok = f"{m.group(2)}{m.group(1)}"
                # Filter out cycle-inducing loopbacks (e.g. e2 on a1, or f1 on e4)
                if tid == 'a1' and tok == 'e2':
                    continue
                if tid == 'e4' and tok == 'f1':
                    continue
                if tok != tid and tok not in predecessors_fs:
                    predecessors_fs.append(tok)

        tasks.append(Task(
            id=tid,
            name=rt['desc'],
            resource=res_name,
            duration=rt['duration'],
            predecessors_fs=predecessors_fs,
            predecessors_ss=[],
        ))

    settings = GlobalSettings(
        available_time=3600.0,
        takt_time=60.0,
        time_increment=1.0,
        output_file="outputs/honda_seq_dev_111826.xlsx",
    )

    return SequenceModel(settings=settings, resources=resources, tasks=tasks)

if __name__ == "__main__":
    model = load_honda_excel("honda_seq_dev_111826.xlsx")
    scheduled = schedule(model)
    print(f"Successfully scheduled {len(scheduled.tasks)} tasks across {len(scheduled.resources)} resources!")
    max_t = max(t.end_time for t in scheduled.tasks)
    print(f"Total Cycle Time: {max_t:.1f}s vs Takt: {scheduled.settings.takt_time}s")
    for t in scheduled.tasks:
        print(f"{t.id:3s} [{t.resource:18s}] {t.name:42s} | {t.start_time:4.1f}s -> {t.end_time:4.1f}s ({t.duration}s) FS:{t.predecessors_fs}")
