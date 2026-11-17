import os
import json
import math
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z_TABLE = {
    0.05: -1.645,
    0.25: -0.674,
    0.50: 0.0,
    0.75: 0.674,
    0.95: 1.645,
}

def round2(x: float) -> float | int:
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value

def norm_name(name: str) -> str:
    return re.sub(r'[^a-z0-9]', '', name.lower())

def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace('Z', '+00:00'))

def forecast_case(case: dict, path_name: str) -> dict:
    levels = case.get("levels", LEVELS)
    game_info = case.get("game", {})
    game_name = game_info.get("name", "")
    norm_target_name = norm_name(game_name)
    day_start_str = case.get("day_start", "")
    notes = case.get("notes", "")
    comparables = case.get("comparables", [])

    first_known = next((k for k in case.get("known", []) if k.get("hour") == 1), None)
    if first_known is None:
        raise ValueError(f"{path_name} has no hour-1 print")
    p1 = max(1.0, float(first_known["viewers"]))

    # Parse day_start
    try:
        day_start_dt = parse_iso(day_start_str)
    except Exception:
        day_start_dt = None

    # PATH A — REPLAY
    replay_map = {} # hour -> viewers
    matched_comp = None
    if day_start_dt:
        matching_comps = []
        for comp in comparables:
            if comp.get("day_start") == day_start_str:
                matching_comps.append(comp)
        
        # Prefer comp whose name equals game_name if available
        best_comp = None
        for comp in matching_comps:
            if comp.get("name") == game_name:
                best_comp = comp
                break
        if not best_comp and matching_comps:
            best_comp = matching_comps[0]

        if best_comp:
            hourly = best_comp.get("hourly", [])
            hourly_by_dt = {}
            for pt in hourly:
                try:
                    dt = parse_iso(pt["from"])
                    hourly_by_dt[dt] = float(pt["viewers"])
                except Exception:
                    pass
            
            comp_h1_dt = day_start_dt
            comp_h1_val = hourly_by_dt.get(comp_h1_dt)
            if comp_h1_val is not None and comp_h1_val > 0:
                if abs(math.log(comp_h1_val / p1)) <= 0.02:
                    all_present = True
                    temp_map = {}
                    for h in range(2, 25):
                        dt = day_start_dt + timedelta(hours=h-1)
                        val = hourly_by_dt.get(dt)
                        if val is not None and val > 0:
                            temp_map[h] = val
                        else:
                            all_present = False
                            break
                    if all_present:
                        matched_comp = best_comp
                        for h in range(2, 25):
                            replay_map[h] = temp_map[h]
                    else:
                        matched_comp = best_comp
                        for h in range(2, 25):
                            dt = day_start_dt + timedelta(hours=h-1)
                            val = hourly_by_dt.get(dt)
                            if val is not None and val > 0:
                                replay_map[h] = val

    # If full replay map is available (all hours 2..24 present), short-circuit Path A Replay
    if len(replay_map) == 23:
        hours_output = []
        for row in case.get("forecast", []):
            h = row.get("hour")
            val = replay_map[h]
            q_list = [round2(val)] * len(levels)
            for i in range(1, len(q_list)):
                if q_list[i] < q_list[i-1]:
                    q_list[i] = q_list[i-1]
            hours_output.append({"hour": h, "q": q_list})
        return {"hours": hours_output}

    # Build platform vocabulary across all comparables
    vocab = set()
    for comp in comparables:
        p_str = comp.get("platforms", "")
        if isinstance(p_str, str):
            for tok in re.findall(r'[a-z0-9]+', p_str.lower()):
                vocab.add(tok)

    target_tokens = set()
    for tok in re.findall(r'[a-z0-9]+', notes.lower()):
        if tok in vocab:
            target_tokens.add(tok)

    # Filter pool for Path B
    pool = []
    for comp in comparables:
        c_name = comp.get("name", "")
        c_norm = norm_name(c_name)
        if matched_comp and comp == matched_comp:
            continue
        if norm_target_name and (norm_target_name in c_norm or c_norm in norm_target_name):
            continue
        pool.append(comp)

    # Compute Path B raw log-ratio quantiles for each hour 2..24
    path_b_hours = set()
    raw_path_b_qs = {} # hour -> list of 5 quantile values

    for h in range(2, 25):
        if h in replay_map:
            # If partial replay hour exists, we can use it or fall through to Path B; specification says: "If an accepted match lacks some hour in 2..24, fill just that hour from PATH B."
            # So if h is in replay_map, we skip Path B for this hour.
            continue

        pairs = []
        for comp in pool:
            hourly = comp.get("hourly", [])
            try:
                c_start = parse_iso(comp["day_start"])
            except Exception:
                continue
            dt_1 = c_start
            dt_h = c_start + timedelta(hours=h-1)

            v1_val = None
            vh_val = None
            for pt in hourly:
                try:
                    pdt = parse_iso(pt["from"])
                    if pdt == dt_1:
                        v1_val = float(pt["viewers"])
                    elif pdt == dt_h:
                        vh_val = float(pt["viewers"])
                except Exception:
                    pass

            if v1_val is not None and v1_val > 0 and vh_val is not None and vh_val > 0:
                r = math.log(vh_val / v1_val)
                w = math.exp(-((math.log(v1_val) - math.log(p1)) ** 2) / (2 * (1.1 ** 2)))
                c_platforms = comp.get("platforms", "")
                c_tokens = set(re.findall(r'[a-z0-9]+', c_platforms.lower())) if isinstance(c_platforms, str) else set()
                if target_tokens and (c_tokens & target_tokens):
                    w *= 3.0
                pairs.append((r, w))

        if not pairs:
            z_vals = [Z_TABLE.get(lvl, 0.0) for lvl in levels]
            q_list = [round2(p1 * math.exp(z * 0.15 * math.sqrt(h - 1))) for z in z_vals]
            for i in range(1, len(q_list)):
                if q_list[i] < q_list[i-1]:
                    q_list[i] = q_list[i-1]
            replay_map[h] = q_list
            continue

        path_b_hours.add(h)
        pairs.sort(key=lambda x: x[0])
        total_w = sum(w for _, w in pairs)
        r_first = pairs[0][0]
        r_last = pairs[-1][0]

        pts = [(0.0, r_first)]
        cum_w = 0.0
        for r_val, w_val in pairs:
            mid = cum_w + w_val / 2.0
            pts.append((mid, r_val))
            cum_w += w_val
        pts.append((total_w, r_last))

        hour_log_qs = []
        for lvl in levels:
            target_x = lvl * total_w
            if target_x <= 0:
                val = r_first
            elif target_x >= total_w:
                val = r_last
            else:
                val = r_last
                for i in range(len(pts) - 1):
                    x1, y1 = pts[i]
                    x2, y2 = pts[i+1]
                    if x1 <= target_x <= x2:
                        if x2 == x1:
                            val = y1
                        else:
                            val = y1 + (target_x - x1) / (x2 - x1) * (y2 - y1)
                        break
            if val < r_first:
                val = r_first
            if val > r_last:
                val = r_last
            hour_log_qs.append(val)
        raw_path_b_qs[h] = hour_log_qs

    # Smooth across hours for path_b_hours
    smoothed_path_b_qs = {}
    for h in path_b_hours:
        q_raw = raw_path_b_qs[h]
        candidates = [h-1, h, h+1]
        valid_neighs = []
        for c in candidates:
            if c in path_b_hours and 2 <= c <= 24:
                valid_neighs.append(c)
        
        if not valid_neighs:
            log_qs = q_raw
        else:
            weights = {}
            for c in valid_neighs:
                if c == h-1:
                    weights[c] = 0.25
                elif c == h:
                    weights[c] = 0.5
                elif c == h+1:
                    weights[c] = 0.25
            w_sum = sum(weights.values())
            
            log_qs = []
            for idx in range(len(levels)):
                weighted_val = sum(weights[c] * raw_path_b_qs[c][idx] for c in valid_neighs) / w_sum
                log_qs.append(weighted_val)
        
        viewer_qs = [round2(p1 * math.exp(lq)) for lq in log_qs]
        for i in range(1, len(viewer_qs)):
            if viewer_qs[i] < viewer_qs[i-1]:
                viewer_qs[i] = viewer_qs[i-1]
        smoothed_path_b_qs[h] = viewer_qs

    # Assemble final output rows for hours 2..24
    hours_output = []
    for row in case.get("forecast", []):
        h = row.get("hour")
        if h in replay_map and h not in path_b_hours:
            val = replay_map[h]
            if isinstance(val, list):
                q_list = [round2(v) for v in val]
            else:
                q_list = [round2(val)] * len(levels)
            for i in range(1, len(q_list)):
                if q_list[i] < q_list[i-1]:
                    q_list[i] = q_list[i-1]
        elif h in smoothed_path_b_qs:
            q_list = smoothed_path_b_qs[h]
        elif h in replay_map:
            val = replay_map[h]
            if isinstance(val, list):
                q_list = val
            else:
                q_list = [round2(val)] * len(levels)
        else:
            z_vals = [Z_TABLE.get(lvl, 0.0) for lvl in levels]
            q_list = [round2(p1 * math.exp(z * 0.15 * math.sqrt(h - 1))) for z in z_vals]
            for i in range(1, len(q_list)):
                if q_list[i] < q_list[i-1]:
                    q_list[i] = q_list[i-1]
        
        hours_output.append({"hour": h, "q": q_list})

    return {"hours": hours_output}

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
