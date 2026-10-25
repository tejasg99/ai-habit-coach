from pydantic import ValidationError

from app.models.enums import DietaryPref, FitnessLevel, Goal
from app.models.profile import Profile
from app.schemas.plan_generation import GeneratedPlan
from app.services.llm_client import LLMError, chat_completion
from app.services.plan_generator import clean_json_text
from app.services.plan_prompt import build_plan_messages

PROFILES = [
    Profile(user_id=1, goal=Goal.build_muscle, fitness_level=FitnessLevel.beginner,
            dietary_pref=DietaryPref.vegetarian, equipment=["dumbbells", "resistance bands"]),
    Profile(user_id=1, goal=Goal.lose_weight, fitness_level=FitnessLevel.intermediate,
            dietary_pref=DietaryPref.non_vegetarian, equipment=[]),
    Profile(user_id=1, goal=Goal.improve_endurance, fitness_level=FitnessLevel.advanced,
            dietary_pref=DietaryPref.vegan, equipment=["pull-up bar", "kettlebell"]),
]
RUNS_PER_PROFILE = 3

ok = total = 0
for profile in PROFILES:
    for _ in range(RUNS_PER_PROFILE):
        total += 1
        try:
            raw = chat_completion(build_plan_messages(profile))
            GeneratedPlan.model_validate_json(clean_json_text(raw))
            ok += 1
            print("valid")
        except ValidationError as exc:
            print("INVALID:", exc.error_count(), "errors; first:", exc.errors()[0]["msg"])
        except LLMError as exc:
            print("LLM error:", exc)

print(f"\n{ok}/{total} valid")