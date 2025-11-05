import os
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime

from database import db, create_document, get_documents
from schemas import Plan

app = FastAPI(title="FitForge AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "FitForge AI backend is running"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from FitForge AI backend!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# ---------- Plan generation ----------
class GeneratePlanInput(BaseModel):
    name: Optional[str] = None
    goal: str = Field(..., description="Build Muscle | Lose Fat | Get Stronger | Endurance")
    experience: str = Field(..., description="Beginner | Intermediate | Advanced")
    days_per_week: int = Field(..., ge=1, le=7)
    duration_weeks: int = Field(..., ge=1, le=52)
    equipment: List[str] = Field(default_factory=list)
    focus_areas: List[str] = Field(default_factory=list)
    constraints: Optional[str] = None


def pick_exercises(goal: str, equipment: List[str], focus: List[str], experience: str) -> Dict[str, List[Dict[str, Any]]]:
    """Return a mapping of splits to exercise pools based on goal/equipment.
    We keep it deterministic and local (no external API), but varied enough to feel intelligent.
    """
    # Base exercises by equipment availability
    has_barbell = any(e.lower() == "barbell" for e in equipment)
    has_dumbbell = any(e.lower() == "dumbbells" or e.lower() == "dumbbell" for e in equipment)
    has_machines = any(e.lower() == "machines" for e in equipment)
    has_kb = any("kettlebell" in e.lower() for e in equipment)

    def e(name, type_, primary, alt_reps):
        return {"name": name, "type": type_, "primary": primary, "reps": alt_reps}

    chest = [
        e("Barbell Bench Press", "compound", "chest", "3x5-8") if has_barbell else None,
        e("Dumbbell Bench Press", "compound", "chest", "3x8-10") if has_dumbbell else None,
        e("Machine Chest Press", "compound", "chest", "3x8-12") if has_machines else None,
        e("Push-Ups", "bodyweight", "chest", "3xAMRAP"),
        e("Incline Dumbbell Press", "compound", "chest", "3x8-12") if has_dumbbell else None,
        e("Cable Fly", "isolation", "chest", "3x12-15") if has_machines else None,
    ]

    back = [
        e("Deadlift", "compound", "back", "3x3-5") if has_barbell else None,
        e("Barbell Row", "compound", "back", "3x5-8") if has_barbell else None,
        e("Dumbbell Row", "compound", "back", "3x8-12") if has_dumbbell else None,
        e("Lat Pulldown", "compound", "back", "3x8-12") if has_machines else None,
        e("Pull-Ups", "bodyweight", "back", "3xAMRAP"),
        e("Seated Cable Row", "compound", "back", "3x10-12") if has_machines else None,
    ]

    legs = [
        e("Back Squat", "compound", "legs", "4x5-8") if has_barbell else None,
        e("Front Squat", "compound", "legs", "4x5-8") if has_barbell else None,
        e("Goblet Squat", "compound", "legs", "3x10-12") if has_dumbbell else None,
        e("Leg Press", "compound", "legs", "3x10-12") if has_machines else None,
        e("Romanian Deadlift", "compound", "hamstrings", "3x6-10") if has_barbell or has_dumbbell else None,
        e("Lunges", "compound", "legs", "3x10-12 each") ,
        e("Leg Curl", "isolation", "hamstrings", "3x12-15") if has_machines else None,
        e("Calf Raise", "isolation", "calves", "4x12-20") if has_machines or has_dumbbell else None,
        e("Kettlebell Swing", "power", "posterior chain", "5x15") if has_kb else None,
    ]

    shoulders = [
        e("Overhead Press", "compound", "shoulders", "3x5-8") if has_barbell else None,
        e("Dumbbell Shoulder Press", "compound", "shoulders", "3x8-12") if has_dumbbell else None,
        e("Lateral Raise", "isolation", "shoulders", "3x12-15"),
        e("Rear Delt Fly", "isolation", "shoulders", "3x12-15") if has_machines or has_dumbbell else None,
    ]

    arms = [
        e("Barbell Curl", "isolation", "biceps", "3x8-12") if has_barbell else None,
        e("Dumbbell Curl", "isolation", "biceps", "3x10-12") if has_dumbbell else None,
        e("Cable Curl", "isolation", "biceps", "3x12-15") if has_machines else None,
        e("Triceps Pushdown", "isolation", "triceps", "3x10-15") if has_machines else None,
        e("Skull Crushers", "isolation", "triceps", "3x8-12") if has_barbell or has_dumbbell else None,
        e("Dips", "bodyweight", "triceps", "3xAMRAP"),
    ]

    core = [
        e("Plank", "core", "core", "3x60s"),
        e("Hanging Leg Raise", "core", "core", "3x10-15"),
        e("Cable Woodchop", "core", "core", "3x12-15") if has_machines else None,
        e("Crunches", "core", "core", "4x15-20"),
    ]

    # Remove None entries
    def clean(xs):
        return [x for x in xs if x]

    pools = {
        "chest": clean(chest),
        "back": clean(back),
        "legs": clean(legs),
        "shoulders": clean(shoulders),
        "arms": clean(arms),
        "core": clean(core),
    }

    # Adjust reps by goal and experience a bit
    strength_bias = goal.lower() in ["get stronger", "strength"]
    endurance_bias = goal.lower() in ["endurance", "lose fat"]
    if strength_bias:
        for group in pools.values():
            for ex in group:
                ex["reps"] = ex["reps"].replace("8-12", "3-6").replace("10-12", "4-6").replace("12-15", "6-8")
    elif endurance_bias:
        for group in pools.values():
            for ex in group:
                ex["reps"] = ex["reps"].replace("5-8", "10-15").replace("6-10", "12-15").replace("8-12", "12-20")

    return pools


def build_week_structure(days: int, pools: Dict[str, List[Dict[str, Any]]], focus: List[str]) -> List[Dict[str, Any]]:
    """Create a week plan with a common split based on days and focus areas."""
    focus_lower = [f.lower() for f in focus]
    week = []

    def day_template(title, primary_groups):
        exercises = []
        # Warm-up
        exercises.append({"name": "Dynamic Warm-up", "reps": "5-10 min", "type": "warmup"})
        # Add 4-6 exercises per day
        for group in primary_groups:
            take = pools.get(group, [])[:2]
            exercises.extend(take)
        if pools.get("core"):
            exercises.append(pools["core"][0])
        return {"title": title, "exercises": exercises}

    if days == 1:
        week = [day_template("Full Body", ["legs", "chest", "back"])]
    elif days == 2:
        week = [
            day_template("Upper Body", ["chest", "back", "shoulders", "arms"]),
            day_template("Lower Body", ["legs", "core"]),
        ]
    elif days == 3:
        if any("push/pull/legs" in f for f in focus_lower):
            week = [
                day_template("Push", ["chest", "shoulders", "arms"]),
                day_template("Pull", ["back", "arms"]),
                day_template("Legs", ["legs", "core"]),
            ]
        else:
            week = [
                day_template("Full Body A", ["legs", "chest", "back"]),
                day_template("Full Body B", ["legs", "back", "shoulders"]),
                day_template("Full Body C", ["legs", "chest", "arms"]),
            ]
    elif days == 4:
        if any("upper/lower" in f for f in focus_lower):
            week = [
                day_template("Upper A", ["chest", "back", "shoulders"]),
                day_template("Lower A", ["legs", "core"]),
                day_template("Upper B", ["chest", "back", "arms"]),
                day_template("Lower B", ["legs", "core"]),
            ]
        else:
            week = [
                day_template("Full Body A", ["legs", "chest", "back"]),
                day_template("Upper", ["chest", "back", "shoulders", "arms"]),
                day_template("Lower", ["legs", "core"]),
                day_template("Full Body B", ["legs", "back", "arms"]),
            ]
    else:
        # 5-7 days: U/L/PPL rotation style
        templates = [
            day_template("Upper", ["chest", "back", "shoulders", "arms"]),
            day_template("Lower", ["legs", "core"]),
            day_template("Push", ["chest", "shoulders", "arms"]),
            day_template("Pull", ["back", "arms"]),
            day_template("Legs", ["legs", "core"]),
        ]
        # Repeat to fill the week
        while len(templates) < days:
            templates.extend(templates)
        week = templates[:days]

    return week


def generate_program(payload: GeneratePlanInput) -> Dict[str, Any]:
    pools = pick_exercises(payload.goal, payload.equipment, payload.focus_areas, payload.experience)
    weeks: List[Dict[str, Any]] = []
    for w in range(payload.duration_weeks):
        week_plan = build_week_structure(payload.days_per_week, pools, payload.focus_areas)
        weeks.append({"week": w + 1, "days": week_plan})
    title = f"{payload.goal} • {payload.days_per_week}d/wk • {payload.duration_weeks}w"
    program = {"title": title, "weeks": weeks}
    return program


@app.post("/api/generate-plan")
def create_plan(payload: GeneratePlanInput):
    program = generate_program(payload)

    plan_doc = Plan(
        title=program["title"],
        name=payload.name,
        goal=payload.goal,
        experience=payload.experience,
        days_per_week=payload.days_per_week,
        duration_weeks=payload.duration_weeks,
        equipment=payload.equipment,
        focus_areas=payload.focus_areas,
        constraints=payload.constraints,
        program=program,
    )

    try:
        plan_id = create_document("plan", plan_doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return {"id": plan_id, "plan": plan_doc.model_dump()}


@app.get("/api/plans")
def list_plans(limit: int = 10):
    try:
        docs = get_documents("plan", {}, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    # Convert ObjectId and datetime fields
    cleaned = []
    for d in docs:
        d["id"] = str(d.pop("_id", ""))
        for k, v in list(d.items()):
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        cleaned.append(d)

    # Sort newest first by created_at if present
    cleaned.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"items": cleaned}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
