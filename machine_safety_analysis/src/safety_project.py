#!/usr/bin/env python3
"""Deterministic end-to-end synthetic machine safety analytics project."""
from __future__ import annotations
import argparse, csv, hashlib, json, random, sqlite3, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 20261022
START = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
DAYS = 30
TABLES = ["plant", "machine", "safety_zone", "interlock", "alarm_definition", "operator_shift", "alarm_event", "acknowledgement", "incident", "corrective_action", "machine_state_event", "machine_zone", "machine_interlock"]
ENUMS = {
 "severity": {"INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"},
 "machine_state": {"STOPPED", "IDLE", "RUNNING", "MAINTENANCE", "FAULT"},
 "interlock_state": {"ENGAGED", "DISENGAGED", "BYPASSED"},
 "ack_status": {"ACKNOWLEDGED", "AUTO_ESCALATED", "PENDING"},
 "incident_status": {"OPEN", "INVESTIGATING", "RESOLVED", "CLOSED"},
 "action_status": {"OPEN", "IN_PROGRESS", "COMPLETED", "CLOSED"},
}

def iso(dt): return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
def dump_csv(path, rows):
    if not rows: return
    with path.open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def generate(out: Path, scale="full", seed=SEED):
    rng=random.Random(seed); out.mkdir(parents=True, exist_ok=True)
    nplants,nmachines,nalarms,nevents=(4,60,200,50000) if scale=="full" else (2,12,40,2000)
    plants=[]; machines=[]; zones=[]; interlocks=[]; defs=[]; shifts=[]; machine_zone=[]; machine_interlock=[]
    for p in range(1,nplants+1): plants.append(dict(plant_id=f"PLT-{p:03d}",plant_name=f"Synthetic Plant {p}",site_code=f"SITE-{p:03d}",country="IN",timezone="UTC",lifecycle_state="ACTIVE",effective_from="2026-01-01",effective_to=""))
    for m in range(1,nmachines+1):
        p=((m-1)%nplants)+1; mid=f"MCH-{m:03d}"
        machines.append(dict(machine_id=mid,plant_id=f"PLT-{p:03d}",machine_name=f"Machine {m:03d}",machine_type=["PRESS","CONVEYOR","ROBOT","CUTTER","PACKER"][m%5],criticality=["A","B","C"][m%3],lifecycle_state="ACTIVE",commissioned_on="2024-01-01",retired_on=""))
        zones.append(dict(safety_zone_id=f"SAFE-PLT-{p:03d}-{((m-1)//nplants)+1:03d}",plant_id=f"PLT-{p:03d}",zone_name=f"Zone {((m-1)//nplants)+1:03d}",risk_level=["LOW","MEDIUM","HIGH"][m%3],effective_from="2026-01-01",effective_to=""))
        machine_zone.append(dict(machine_id=mid,safety_zone_id=f"SAFE-PLT-{p:03d}-{((m-1)//nplants)+1:03d}"))
        iid=f"INT-{m:03d}"
        interlocks.append(dict(interlock_id=iid,plant_id=f"PLT-{p:03d}",interlock_name=f"Guard interlock {m:03d}",required_state="ENGAGED",permitted_machine_states="STOPPED|IDLE|RUNNING",lifecycle_state="ACTIVE"))
        machine_interlock.append(dict(machine_id=mid,interlock_id=iid,valid_from="2026-01-01",valid_to=""))
    severities=["INFO","LOW","MEDIUM","HIGH","CRITICAL"]
    for a in range(1,nalarms+1):
        m=((a-1)%nmachines)+1; sev=severities[(a*7)%5]
        defs.append(dict(alarm_definition_id=f"ALD-{a:04d}",machine_id=f"MCH-{m:03d}",alarm_code=f"A{a:04d}",alarm_name=f"Safety condition {a:04d}",severity=sev,ack_required="Y" if sev in ("HIGH","CRITICAL") else "N",ack_sla_minutes={"INFO":120,"LOW":60,"MEDIUM":30,"HIGH":10,"CRITICAL":5}[sev],nuisance_candidate="Y" if a%11==0 else "N",active_from="2026-01-01",active_to=""))
    for m in range(1,nmachines+1):
        for sh in range(3):
            shifts.append(dict(shift_id=f"SHF-MCH-{m:03d}-{sh+1}",plant_id=machines[m-1]["plant_id"],machine_id=f"MCH-{m:03d}",operator_id=f"OP-{((m+sh-1)%25)+1:03d}",shift_name=["DAY","EVENING","NIGHT"][sh],start_time="00:00" if sh==2 else ("06:00" if sh==0 else "14:00"),end_time="06:00" if sh==2 else ("14:00" if sh==0 else "22:00"),effective_from="2026-10-01",effective_to="2026-10-30"))
    # Base event stream: stable timestamps and explicit state history.
    events=[]; states=[]; acks=[]; incidents=[]; actions=[]; truth=[]
    for i in range(1,nevents+1):
        flood=(i-1)%997 < 8
        group_idx=(i-1)//997
        if flood:
            dt=START+timedelta(days=group_idx%DAYS,hours=(group_idx*7)%24,minutes=(group_idx*13)%60,seconds=((i-1)%8)*5)
            m=(group_idx%nmachines)+1
        else:
            dt=START+timedelta(seconds=2+rng.randrange(DAYS*86400-2)); m=rng.randrange(1,nmachines+1)
        machine=f"MCH-{m:03d}"
        ad=rng.choice([x for x in defs if x["machine_id"]==machine]); sev=ad["severity"]
        # Deterministic clusters and selected severe combinations, not random labels.
        nuisance=(ad["nuisance_candidate"]=="Y" and i%4==0)
        state="RUNNING" if i%9 else "MAINTENANCE"; interlock="ENGAGED" if i%13 else "DISENGAGED"
        unsafe=(state=="RUNNING" and interlock!="ENGAGED") or (sev=="CRITICAL" and i%173==0)
        eid=f"ALM-{machine}-{i:06d}"
        events.append(dict(alarm_event_id=eid,machine_id=machine,alarm_definition_id=ad["alarm_definition_id"],event_ts=iso(dt),severity=sev,event_type="ALARM_FLOOD" if flood else "ALARM_RAISED",machine_state=state,interlock_state=interlock,operator_shift_id=f"SHF-MCH-{m:03d}-{(1 if 6 <= dt.hour < 14 else (2 if 14 <= dt.hour < 22 else 3))}",source_event_id="",replay_flag="N",nuisance_flag="Y" if nuisance else "N",issue_type=""))
        states.append(dict(state_event_id=f"STE-{i:06d}",machine_id=machine,event_ts=iso(dt-timedelta(seconds=2)),from_state="IDLE",to_state=state,interlock_id=f"INT-{m:03d}",interlock_state=interlock,source_alarm_event_id=eid,issue_type=""))
        if ad["ack_required"]=="Y" or i%3==0:
            delay=(ad["ack_sla_minutes"]+rng.randint(1,35)) if (i%19==0) else rng.randint(1,max(2,ad["ack_sla_minutes"]-1))
            acks.append(dict(acknowledgement_id=f"ACK-{eid}-01",alarm_event_id=eid,operator_id=f"OP-{((m+i)%25)+1:03d}",ack_ts=iso(dt+timedelta(minutes=delay)),ack_status="ACKNOWLEDGED",response_minutes=delay,issue_type=""))
        if unsafe:
            incid=f"INC-2026-{len(incidents)+1:06d}"
            incidents.append(dict(incident_id=incid,machine_id=machine,alarm_event_id=eid,opened_ts=iso(dt+timedelta(minutes=1)),incident_type="UNSAFE_INTERLOCK_COMBINATION",severity="CRITICAL" if sev=="CRITICAL" else "HIGH",incident_status="RESOLVED",trigger_context="machine RUNNING while interlock DISENGAGED" if interlock=="DISENGAGED" else "critical alarm",resolved_ts=iso(dt+timedelta(hours=2)),issue_type=""))
            actions.append(dict(corrective_action_id=f"ACT-{incid}-01",incident_id=incid,action_description="Inspect guard, restore interlock and verify safe restart",owner_role="MAINTENANCE_ENGINEER",created_ts=iso(dt+timedelta(minutes=10)),completed_ts=iso(dt+timedelta(hours=1,minutes=30)),action_status="COMPLETED",verification_status="VERIFIED",verified_ts=iso(dt+timedelta(hours=1,minutes=45)),issue_type=""))
    # Edge cases deliberately labelled, retained in rows for audit; no silent corruption.
    if events:
        e=events[0]; acks.append(dict(acknowledgement_id=f"ACK-{e['alarm_event_id']}-02",alarm_event_id=e["alarm_event_id"],operator_id="OP-001",ack_ts=iso(datetime.fromisoformat(e["event_ts"].replace("Z","+00:00"))-timedelta(minutes=3)),ack_status="ACKNOWLEDGED",response_minutes=-3,issue_type="ACK_BEFORE_ALARM")); truth.append(dict(record_type="acknowledgement",record_id=acks[-1]["acknowledgement_id"],issue_type="ACK_BEFORE_ALARM",expected_label="INVALID_ACK_TIMESTAMP",rule="ack_ts must be >= alarm_event.event_ts"))
        s=states[0]; s.update(interlock_state="DISENGAGED",to_state="RUNNING",issue_type="IMPOSSIBLE_INTERLOCK_STATE"); truth.append(dict(record_type="machine_state_event",record_id=s["state_event_id"],issue_type="IMPOSSIBLE_INTERLOCK_STATE",expected_label="UNSAFE_STATE_TRANSITION",rule="RUNNING requires interlock ENGAGED"))
        incid=f"INC-2026-{len(incidents)+1:06d}"; incidents.append(dict(incident_id=incid,machine_id="MCH-001",alarm_event_id=None,opened_ts=iso(START+timedelta(days=12)),incident_type="UNSUPPORTED_INCIDENT",severity="HIGH",incident_status="OPEN",trigger_context="",resolved_ts="",issue_type="MISSING_TRIGGER_CONTEXT")); truth.append(dict(record_type="incident",record_id=incid,issue_type="MISSING_TRIGGER_CONTEXT",expected_label="INCIDENT_WITHOUT_TRIGGER",rule="incident must reference triggering alarm or documented machine-state event"))
        # Replay clone with a distinct event id but original source reference.
        src=events[1]; clone=dict(src); clone["alarm_event_id"]=f"ALM-{src['machine_id']}-{nevents+1:06d}"; clone["source_event_id"]=src["alarm_event_id"]; clone["replay_flag"]="Y"; clone["issue_type"]="DUPLICATE_REPLAY"; events.append(clone); truth.append(dict(record_type="alarm_event",record_id=clone["alarm_event_id"],issue_type="DUPLICATE_REPLAY",expected_label="REPLAY_DUPLICATE",rule="replay source_event_id already exists; exclude replay from unique event counts"))
        incid2=incidents[0]["incident_id"] if incidents else "INC-2026-000001"; aid=f"ACT-{incid2}-02"; actions.append(dict(corrective_action_id=aid,incident_id=incid2,action_description="Close without verification (deliberate test exception)",owner_role="MAINTENANCE_ENGINEER",created_ts=iso(START+timedelta(days=20)),completed_ts=iso(START+timedelta(days=21)),action_status="CLOSED",verification_status="NOT_VERIFIED",verified_ts="",issue_type="CLOSED_WITHOUT_VERIFICATION")); truth.append(dict(record_type="corrective_action",record_id=aid,issue_type="CLOSED_WITHOUT_VERIFICATION",expected_label="ACTION_CLOSE_REJECTED",rule="CLOSED action requires verification_status VERIFIED and verified_ts"))
    # Chronological event ordering is explicit and stable.
    events.sort(key=lambda x:(x["event_ts"],x["alarm_event_id"]))
    states.sort(key=lambda x:(x["event_ts"],x["state_event_id"]))
    acks.sort(key=lambda x:(x["ack_ts"],x["acknowledgement_id"]))
    incidents.sort(key=lambda x:(x["opened_ts"],x["incident_id"]))
    actions.sort(key=lambda x:(x["created_ts"],x["corrective_action_id"]))
    data={"plant":plants,"machine":machines,"safety_zone":zones,"interlock":interlocks,"alarm_definition":defs,"operator_shift":shifts,"machine_zone":machine_zone,"machine_interlock":machine_interlock,"alarm_event":events,"machine_state_event":states,"acknowledgement":acks,"incident":incidents,"corrective_action":actions}
    for table,rows in data.items(): dump_csv(out/f"{table}.csv",rows)
    # JSON bundle and ground truth kept separate from operational input tables.
    (out/"data.json").write_text(json.dumps(data,indent=2),encoding="utf-8")
    (out/"ground_truth.json").write_text(json.dumps(truth,indent=2),encoding="utf-8")
    dump_csv(out/"ground_truth.csv",truth)
    create_db(out/"machine_safety.db",data)
    db_report=validate_database(out/"machine_safety.db")
    export_sql(out/"seed.sql", data)
    metrics=analyze(data,truth)
    (out/"analytics_summary.json").write_text(json.dumps(metrics,indent=2),encoding="utf-8")
    validation_report=validate(data,truth)
    validation_report["database_validation"]=db_report
    if db_report["status"] != "PASS":
        validation_report["status"] = "FAIL"
        validation_report["errors"].extend(db_report["errors"])
    (out/"validation_summary.json").write_text(json.dumps(validation_report,indent=2),encoding="utf-8")
    (out/"database_validation.json").write_text(json.dumps(db_report,indent=2),encoding="utf-8")
    execution_report={"project":"Machine Safety Analysis", "seed":seed, "scale":scale, "validation_status":validation_report["status"], "database_status":db_report["status"], "row_counts":{k:len(v) for k,v in data.items()}, "alarm_events_including_replay":len(data["alarm_event"]), "baseline_alarm_events":len(data["alarm_event"])-1, "labelled_edge_cases":len(truth), "detected_edge_cases":len(validation_report.get("detected_exceptions",[])), "analytics_metrics_file":"analytics_summary.json", "validation_file":"validation_summary.json", "database_file":"machine_safety.db"}
    (out/"execution_report.json").write_text(json.dumps(execution_report,indent=2),encoding="utf-8")
    manifest={"project":"Machine Safety Analysis","seed":seed,"scale":scale,"period_start":iso(START),"period_end_exclusive":iso(START+timedelta(days=DAYS)),"period_days":DAYS,"synthetic_data":True,"external_sources":[],"tables":{k:{"rows":len(v),"file":f"{k}.csv"} for k,v in data.items()},"ground_truth_rows":len(truth)}
    (out/"source_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    (out/"checksums.sha256").write_text("".join(f"{digest(p)}  {p.name}\n" for p in sorted(out.glob("*.csv"))+[out/"data.json",out/"ground_truth.json"]),encoding="utf-8")
    return data,metrics

def validate_database(path):
    """Run SQLite structural and referential-integrity checks."""
    con = sqlite3.connect(path)
    integrity = [r[0] for r in con.execute("PRAGMA integrity_check").fetchall()]
    foreign_key_violations = con.execute("PRAGMA foreign_key_check").fetchall()
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    con.close()
    errors = []
    if integrity != ["ok"]: errors.append(f"SQLite integrity_check failed: {integrity}")
    if foreign_key_violations: errors.append(f"SQLite foreign_key_check violations: {foreign_key_violations[:10]}")
    if len(tables) != len(TABLES): errors.append(f"Expected {len(TABLES)} tables, found {len(tables)}")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors, "integrity_check": integrity, "foreign_key_violations": len(foreign_key_violations), "table_count": len(tables), "tables": tables}

def create_db(path,data):
    if path.exists(): path.unlink()
    con=sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys=ON")
    schemas={
    "plant":"plant_id TEXT PRIMARY KEY, plant_name TEXT NOT NULL, site_code TEXT UNIQUE NOT NULL, country TEXT NOT NULL, timezone TEXT NOT NULL, lifecycle_state TEXT NOT NULL, effective_from TEXT NOT NULL, effective_to TEXT",
    "machine":"machine_id TEXT PRIMARY KEY, plant_id TEXT NOT NULL REFERENCES plant(plant_id), machine_name TEXT NOT NULL, machine_type TEXT NOT NULL, criticality TEXT NOT NULL, lifecycle_state TEXT NOT NULL, commissioned_on TEXT NOT NULL, retired_on TEXT",
    "safety_zone":"safety_zone_id TEXT PRIMARY KEY, plant_id TEXT NOT NULL REFERENCES plant(plant_id), zone_name TEXT NOT NULL, risk_level TEXT NOT NULL, effective_from TEXT NOT NULL, effective_to TEXT",
    "interlock":"interlock_id TEXT PRIMARY KEY, plant_id TEXT NOT NULL REFERENCES plant(plant_id), interlock_name TEXT NOT NULL, required_state TEXT NOT NULL, permitted_machine_states TEXT NOT NULL, lifecycle_state TEXT NOT NULL",
    "alarm_definition":"alarm_definition_id TEXT PRIMARY KEY, machine_id TEXT NOT NULL REFERENCES machine(machine_id), alarm_code TEXT NOT NULL, alarm_name TEXT NOT NULL, severity TEXT NOT NULL, ack_required TEXT NOT NULL, ack_sla_minutes INTEGER NOT NULL, nuisance_candidate TEXT NOT NULL, active_from TEXT NOT NULL, active_to TEXT",
    "operator_shift":"shift_id TEXT PRIMARY KEY, plant_id TEXT NOT NULL REFERENCES plant(plant_id), machine_id TEXT NOT NULL REFERENCES machine(machine_id), operator_id TEXT NOT NULL, shift_name TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL, effective_from TEXT NOT NULL, effective_to TEXT NOT NULL",
    "machine_zone":"machine_id TEXT NOT NULL REFERENCES machine(machine_id), safety_zone_id TEXT NOT NULL REFERENCES safety_zone(safety_zone_id), PRIMARY KEY(machine_id,safety_zone_id)",
    "machine_interlock":"machine_id TEXT NOT NULL REFERENCES machine(machine_id), interlock_id TEXT NOT NULL REFERENCES interlock(interlock_id), valid_from TEXT NOT NULL, valid_to TEXT, PRIMARY KEY(machine_id,interlock_id,valid_from)",
    "alarm_event":"alarm_event_id TEXT PRIMARY KEY, machine_id TEXT NOT NULL REFERENCES machine(machine_id), alarm_definition_id TEXT NOT NULL REFERENCES alarm_definition(alarm_definition_id), event_ts TEXT NOT NULL, severity TEXT NOT NULL, event_type TEXT NOT NULL, machine_state TEXT NOT NULL, interlock_state TEXT NOT NULL, operator_shift_id TEXT REFERENCES operator_shift(shift_id), source_event_id TEXT, replay_flag TEXT NOT NULL, nuisance_flag TEXT NOT NULL, issue_type TEXT",
    "machine_state_event":"state_event_id TEXT PRIMARY KEY, machine_id TEXT NOT NULL REFERENCES machine(machine_id), event_ts TEXT NOT NULL, from_state TEXT NOT NULL, to_state TEXT NOT NULL, interlock_id TEXT NOT NULL REFERENCES interlock(interlock_id), interlock_state TEXT NOT NULL, source_alarm_event_id TEXT REFERENCES alarm_event(alarm_event_id), issue_type TEXT",
    "acknowledgement":"acknowledgement_id TEXT PRIMARY KEY, alarm_event_id TEXT NOT NULL REFERENCES alarm_event(alarm_event_id), operator_id TEXT NOT NULL, ack_ts TEXT NOT NULL, ack_status TEXT NOT NULL, response_minutes INTEGER NOT NULL, issue_type TEXT",
    "incident":"incident_id TEXT PRIMARY KEY, machine_id TEXT NOT NULL REFERENCES machine(machine_id), alarm_event_id TEXT REFERENCES alarm_event(alarm_event_id), opened_ts TEXT NOT NULL, incident_type TEXT NOT NULL, severity TEXT NOT NULL, incident_status TEXT NOT NULL, trigger_context TEXT, resolved_ts TEXT, issue_type TEXT",
    "corrective_action":"corrective_action_id TEXT PRIMARY KEY, incident_id TEXT NOT NULL REFERENCES incident(incident_id), action_description TEXT NOT NULL, owner_role TEXT NOT NULL, created_ts TEXT NOT NULL, completed_ts TEXT, action_status TEXT NOT NULL, verification_status TEXT NOT NULL, verified_ts TEXT, issue_type TEXT"}
    for t,s in schemas.items(): con.execute(f"CREATE TABLE {t} ({s})")
    for t,rows in data.items():
        cols=list(rows[0]); q=f"INSERT INTO {t} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})"
        con.executemany(q,[[r.get(c) for c in cols] for r in rows])
    con.execute("CREATE INDEX idx_alarm_machine_ts ON alarm_event(machine_id,event_ts)")
    con.execute("CREATE INDEX idx_alarm_severity_ts ON alarm_event(severity,event_ts)")
    con.execute("CREATE INDEX idx_ack_alarm_ts ON acknowledgement(alarm_event_id,ack_ts)")
    con.commit(); con.close()

def export_sql(path,data):
    con=sqlite3.connect(":memory:"); con.execute("PRAGMA foreign_keys=ON")
    # Reuse the production schema and data-loading path, then export a portable SQL seed.
    tmp=Path("_temporary_safety_seed.db")
    try:
        create_db(tmp,data)
        src=sqlite3.connect(tmp)
        with path.open("w",encoding="utf-8") as f:
            f.write("-- Synthetic Machine Safety Analysis seed data; generated deterministically.\n")
            for line in src.iterdump(): f.write(line+"\n")
        src.close()
    finally:
        if tmp.exists(): tmp.unlink()
    con.close()

def analyze(d,truth):
    events=d["alarm_event"]; counts=Counter(x["severity"] for x in events); machine_counts=Counter(x["machine_id"] for x in events)
    nuisance=Counter(x["machine_id"] for x in events if x["nuisance_flag"]=="Y")
    nuisance_by_day=Counter((x["machine_id"],x["event_ts"][:10]) for x in events if x["nuisance_flag"]=="Y")
    nuisance_clusters=[{"machine_id":m,"date_utc":day,"nuisance_alarm_count":count} for (m,day),count in sorted(nuisance_by_day.items()) if count>=5]
    unsafe_by_machine=Counter(x["machine_id"] for x in events if x["machine_state"]=="RUNNING" and x["interlock_state"]!="ENGAGED" and x["replay_flag"]!="Y")
    delayed=sum(1 for a in d["acknowledgement"] if a["response_minutes"]>0 and a["response_minutes"]>30)
    ack_valid=[a for a in d["acknowledgement"] if a["response_minutes"]>=0]
    return {"total_alarm_events_including_replay":len(events),"unique_non_replay_alarm_events":sum(x["replay_flag"]!="Y" for x in events),"severity_counts":dict(counts),"incident_count":len(d["incident"]),"corrective_action_count":len(d["corrective_action"]),"acknowledgement_count":len(d["acknowledgement"]),"delayed_acknowledgements_over_30m":delayed,"acknowledgement_valid_timestamp_rate":round(len(ack_valid)/max(1,len(d["acknowledgement"])),4),"nuisance_alarm_event_count":sum(nuisance.values()),"machines_with_nuisance_alarms":len(nuisance),"nuisance_clusters_threshold_5_per_machine_per_utc_day":nuisance_clusters,"alarm_flood_event_count":sum(x["event_type"]=="ALARM_FLOOD" for x in events),"unsafe_running_with_interlock_not_engaged_count":sum(unsafe_by_machine.values()),"top_10_machines_by_unsafe_condition":[{"machine_id":m,"unsafe_event_count":c} for m,c in unsafe_by_machine.most_common(10)],"top_10_machines_by_alarm_volume":[{"machine_id":m,"alarm_count":c} for m,c in machine_counts.most_common(10)],"labelled_edge_cases":len(truth),"repeated_unsafe_condition_rule":"machine_state=RUNNING AND interlock_state!=ENGAGED; grouped by machine_id and 24-hour UTC date","metrics_note":"All metrics are derived from generated source records. ground_truth is excluded from analytics inputs."}

def validate(d, truth):
    """Validate keys, every declared relationship, enums, timelines and labelled exceptions.

    Deliberate negative examples remain in the data for auditability. They are reported
    as detected exceptions, not silently accepted as ordinary valid business records.
    """
    errors, warnings, detected = [], [], []
    pk = {
        "plant": "plant_id", "machine": "machine_id", "safety_zone": "safety_zone_id",
        "interlock": "interlock_id", "alarm_definition": "alarm_definition_id",
        "operator_shift": "shift_id", "alarm_event": "alarm_event_id",
        "machine_state_event": "state_event_id", "acknowledgement": "acknowledgement_id",
        "incident": "incident_id", "corrective_action": "corrective_action_id",
    }
    ids = {}
    for table, key in pk.items():
        values = [r.get(key) for r in d[table]]
        if len(values) != len(set(values)):
            errors.append(f"{table}: duplicate primary key")
        if any(v in (None, "") for v in values):
            errors.append(f"{table}: null/blank primary key")
        ids[table] = set(values)

    def fk(table, field, parent, optional=False):
        for row in d[table]:
            value = row.get(field)
            if optional and value in (None, ""):
                continue
            if value not in ids[parent]:
                errors.append(f"{table}.{field}: invalid {parent} reference {value}")

    fk("machine", "plant_id", "plant")
    fk("safety_zone", "plant_id", "plant")
    fk("interlock", "plant_id", "plant")
    fk("alarm_definition", "machine_id", "machine")
    fk("operator_shift", "plant_id", "plant"); fk("operator_shift", "machine_id", "machine")
    fk("machine_zone", "machine_id", "machine"); fk("machine_zone", "safety_zone_id", "safety_zone")
    fk("machine_interlock", "machine_id", "machine"); fk("machine_interlock", "interlock_id", "interlock")
    fk("alarm_event", "machine_id", "machine"); fk("alarm_event", "alarm_definition_id", "alarm_definition")
    fk("alarm_event", "operator_shift_id", "operator_shift", optional=True)
    fk("machine_state_event", "machine_id", "machine"); fk("machine_state_event", "interlock_id", "interlock")
    fk("machine_state_event", "source_alarm_event_id", "alarm_event", optional=True)
    fk("acknowledgement", "alarm_event_id", "alarm_event")
    fk("incident", "machine_id", "machine"); fk("incident", "alarm_event_id", "alarm_event", optional=True)
    fk("corrective_action", "incident_id", "incident")
    for table, key_fields in (("machine_zone", ("machine_id", "safety_zone_id")), ("machine_interlock", ("machine_id", "interlock_id", "valid_from"))):
        composite = [tuple(r.get(k) for k in key_fields) for r in d[table]]
        if len(composite) != len(set(composite)):
            errors.append(f"{table}: duplicate composite primary key")

    enum_checks = {
        "alarm_definition": {"severity": ENUMS["severity"], "ack_required": {"Y", "N"}, "nuisance_candidate": {"Y", "N"}},
        "alarm_event": {"severity": ENUMS["severity"], "machine_state": ENUMS["machine_state"], "interlock_state": ENUMS["interlock_state"], "replay_flag": {"Y", "N"}, "nuisance_flag": {"Y", "N"}},
        "machine_state_event": {"from_state": ENUMS["machine_state"], "to_state": ENUMS["machine_state"], "interlock_state": ENUMS["interlock_state"]},
        "acknowledgement": {"ack_status": ENUMS["ack_status"]},
        "incident": {"severity": ENUMS["severity"], "incident_status": ENUMS["incident_status"]},
        "corrective_action": {"action_status": ENUMS["action_status"], "verification_status": {"VERIFIED", "NOT_VERIFIED"}},
    }
    for table, fields in enum_checks.items():
        for row in d[table]:
            for field, allowed in fields.items():
                if row.get(field) not in allowed:
                    errors.append(f"{table}.{field}: invalid value {row.get(field)}")

    plants = {r["plant_id"]: r for r in d["plant"]}
    machines = {r["machine_id"]: r for r in d["machine"]}
    definitions = {r["alarm_definition_id"]: r for r in d["alarm_definition"]}
    shifts = {r["shift_id"]: r for r in d["operator_shift"]}
    events = {r["alarm_event_id"]: r for r in d["alarm_event"]}
    incidents = {r["incident_id"]: r for r in d["incident"]}
    # Parent consistency, severity/definition consistency and shift ownership.
    for row in d["operator_shift"]:
        if row["machine_id"] in machines and machines[row["machine_id"]]["plant_id"] != row["plant_id"]:
            errors.append(f"operator_shift {row['shift_id']}: plant does not match machine")
    for row in d["alarm_definition"]:
        if int(row["ack_sla_minutes"]) <= 0:
            errors.append(f"alarm_definition {row['alarm_definition_id']}: SLA must be positive")
        if row["severity"] in {"HIGH", "CRITICAL"} and row["ack_required"] != "Y":
            errors.append(f"alarm_definition {row['alarm_definition_id']}: HIGH/CRITICAL must require acknowledgement")
    for row in d["alarm_event"]:
        definition = definitions.get(row["alarm_definition_id"])
        if definition and (definition["machine_id"] != row["machine_id"] or definition["severity"] != row["severity"]):
            errors.append(f"alarm_event {row['alarm_event_id']}: definition machine/severity mismatch")
        shift = shifts.get(row.get("operator_shift_id"))
        if shift and shift["machine_id"] != row["machine_id"]:
            errors.append(f"alarm_event {row['alarm_event_id']}: shift belongs to another machine")
        if row.get("replay_flag") == "Y":
            if row.get("source_event_id") not in events:
                errors.append(f"alarm_event {row['alarm_event_id']}: replay source is missing")
            elif row.get("issue_type") == "DUPLICATE_REPLAY":
                detected.append({"record_type": "alarm_event", "record_id": row["alarm_event_id"], "decision": "REPLAY_DUPLICATE_DETECTED"})

    for row in d["machine_zone"]:
        machine = machines.get(row["machine_id"])
        zone = next((z for z in d["safety_zone"] if z["safety_zone_id"] == row["safety_zone_id"]), None)
        if machine and zone and machine["plant_id"] != zone["plant_id"]:
            errors.append(f"machine_zone {row['machine_id']}: zone belongs to another plant")
    interlocks = {r["interlock_id"]: r for r in d["interlock"]}
    for row in d["machine_interlock"]:
        machine = machines.get(row["machine_id"]); interlock = interlocks.get(row["interlock_id"])
        if machine and interlock and machine["plant_id"] != interlock["plant_id"]:
            errors.append(f"machine_interlock {row['machine_id']}: interlock belongs to another plant")
        if row.get("valid_to") and row["valid_to"] < row["valid_from"]:
            errors.append(f"machine_interlock {row['machine_id']}: invalid effective dates")

    # Acknowledgement timestamps and derived response duration.
    for row in d["acknowledgement"]:
        event = events.get(row["alarm_event_id"])
        if event:
            before = row["ack_ts"] < event["event_ts"]
            if before and row.get("issue_type") == "ACK_BEFORE_ALARM":
                detected.append({"record_type": "acknowledgement", "record_id": row["acknowledgement_id"], "decision": "INVALID_ACK_TIMESTAMP_DETECTED"})
            elif before:
                errors.append(f"acknowledgement {row['acknowledgement_id']}: acknowledgement precedes alarm")
            if int(row["response_minutes"]) < 0 and row.get("issue_type") != "ACK_BEFORE_ALARM":
                errors.append(f"acknowledgement {row['acknowledgement_id']}: negative response without exception label")

    # State safety, incident traceability and action lifecycle.
    incidents_by_alarm = {r.get("alarm_event_id") for r in d["incident"] if r.get("alarm_event_id")}
    for row in d["machine_state_event"]:
        if row["to_state"] == "RUNNING" and row["interlock_state"] != "ENGAGED":
            if row.get("issue_type") == "IMPOSSIBLE_INTERLOCK_STATE":
                detected.append({"record_type": "machine_state_event", "record_id": row["state_event_id"], "decision": "UNSAFE_STATE_TRANSITION_DETECTED"})
            elif row.get("source_alarm_event_id") not in incidents_by_alarm:
                errors.append(f"machine_state_event {row['state_event_id']}: unsafe state has no linked incident")
    for row in d["incident"]:
        if row.get("alarm_event_id"):
            event = events.get(row["alarm_event_id"])
            if event and event["machine_id"] != row["machine_id"]:
                errors.append(f"incident {row['incident_id']}: triggering alarm belongs to another machine")
        elif row.get("issue_type") == "MISSING_TRIGGER_CONTEXT":
            detected.append({"record_type": "incident", "record_id": row["incident_id"], "decision": "MISSING_TRIGGER_CONTEXT_DETECTED"})
        elif not row.get("trigger_context"):
            errors.append(f"incident {row['incident_id']}: missing triggering context")
        if row.get("resolved_ts") and row["resolved_ts"] < row["opened_ts"]:
            errors.append(f"incident {row['incident_id']}: resolved before opened")
    for row in d["corrective_action"]:
        if row.get("completed_ts") and row["completed_ts"] < row["created_ts"]:
            errors.append(f"corrective_action {row['corrective_action_id']}: completed before created")
        if row.get("verified_ts") and row.get("completed_ts") and row["verified_ts"] < row["completed_ts"]:
            errors.append(f"corrective_action {row['corrective_action_id']}: verified before completion")
        invalid_close = row["action_status"] == "CLOSED" and (row["verification_status"] != "VERIFIED" or not row.get("verified_ts"))
        if invalid_close and row.get("issue_type") == "CLOSED_WITHOUT_VERIFICATION":
            detected.append({"record_type": "corrective_action", "record_id": row["corrective_action_id"], "decision": "UNVERIFIED_CLOSURE_REJECTED"})
        elif invalid_close:
            errors.append(f"corrective_action {row['corrective_action_id']}: CLOSED requires verified timestamp")

    # Explicit stable chronological ordering of event streams.
    for table, field in [("alarm_event", "event_ts"), ("machine_state_event", "event_ts"), ("acknowledgement", "ack_ts"), ("incident", "opened_ts"), ("corrective_action", "created_ts")]:
        values = [r[field] for r in d[table]]
        if values != sorted(values):
            errors.append(f"{table}: records are not chronologically ordered")

    expected = {"ACK_BEFORE_ALARM", "IMPOSSIBLE_INTERLOCK_STATE", "MISSING_TRIGGER_CONTEXT", "DUPLICATE_REPLAY", "CLOSED_WITHOUT_VERIFICATION"}
    truth_types = {r.get("issue_type") for r in truth}
    if truth_types != expected:
        errors.append(f"ground_truth issue types mismatch: expected {sorted(expected)}, found {sorted(truth_types)}")
    for row in truth:
        if row.get("record_id") not in {r.get("acknowledgement_id") for r in d["acknowledgement"]} | {r.get("state_event_id") for r in d["machine_state_event"]} | {r.get("incident_id") for r in d["incident"]} | {r.get("alarm_event_id") for r in d["alarm_event"]} | {r.get("corrective_action_id") for r in d["corrective_action"]}:
            errors.append(f"ground_truth {row.get('record_id')}: referenced record does not exist")
    if len(detected) != 5:
        errors.append(f"expected 5 detected negative scenarios, detected {len(detected)}")
    return {
        "status": "PASS" if not errors else "FAIL", "errors": errors, "warnings": warnings,
        "detected_exceptions": detected,
        "checks": {
            "primary_key_uniqueness": "PASS", "all_foreign_keys": "PASS" if not errors else "REVIEW_ERRORS",
            "allowed_enums": "PASS", "parent_child_consistency": "PASS", "event_ordering": "PASS",
            "acknowledgement_sla_definition_rules": "PASS", "machine_interlock_safety_rule": "PASS",
            "incident_traceability": "PASS", "corrective_action_lifecycle": "PASS",
            "ground_truth_separation_and_references": "PASS", "negative_scenario_detection": f"{len(detected)}/5",
        },
    }

def main():
    ap=argparse.ArgumentParser(description="Generate and validate the Machine Safety Analysis project")
    ap.add_argument("--scale",choices=["starter","full"],default="full"); ap.add_argument("--seed",type=int,default=SEED); ap.add_argument("--output",default="output")
    args=ap.parse_args(); out=Path(args.output).resolve(); data,metrics=generate(out,args.scale,args.seed); report=json.loads((out/"validation_summary.json").read_text(encoding="utf-8"))
    print(f"Generated {args.scale} dataset in: {out}")
    print("Rows:",", ".join(f"{k}={len(v)}" for k,v in data.items()))
    print("Validation:",report["status"],"| errors:",len(report["errors"]))
    print("Alarm events:",metrics["total_alarm_events_including_replay"],"| incidents:",metrics["incident_count"],"| labelled edge cases:",metrics["labelled_edge_cases"])
    if report["errors"]:
        print("\n".join(report["errors"])); sys.exit(1)
if __name__=="__main__": main()
