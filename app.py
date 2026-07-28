import base64
import json
import os
import re
from datetime import datetime

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy

load_dotenv()

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("SUPABASE_DB_URL") or "sqlite:///recipes.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, unique=True, nullable=False)
    nickname = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SavedRecipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String, nullable=False)
    used_ingredients = db.Column(db.JSON, nullable=False)
    additional_ingredients = db.Column(db.JSON, nullable=False)
    steps = db.Column(db.JSON, nullable=False)
    estimated_time_minutes = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_summary_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
        }

    def to_detail_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "used_ingredients": self.used_ingredients,
            "additional_ingredients": self.additional_ingredients,
            "steps": self.steps,
            "estimated_time_minutes": self.estimated_time_minutes,
            "created_at": self.created_at.isoformat(),
        }


with app.app_context():
    db.create_all()


def call_openrouter(model, messages):
    return requests.post(
        url=OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": model, "messages": messages},
        timeout=60,
    )


def openrouter_error_message(response):
    if response.status_code == 429:
        return "무료 모델의 일일 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요."
    return response.text


def extract_json_object(text):
    if not isinstance(text, str):
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def recognize_ingredients(image_data_uri, retry=False):
    prompt = (
        "이 이미지는 냉장고 내부 사진이야. 보이는 식재료 이름만 한글로 JSON 배열로 알려줘. "
        '형식: {"ingredients": ["계란", "우유"]}. 다른 설명은 붙이지 마.'
    )
    if retry:
        prompt += " 이전 응답이 JSON 형식이 아니었습니다. 반드시 JSON 객체만 출력하세요."

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_data_uri}},
            ],
        }
    ]
    return call_openrouter("google/gemma-4-26b-a4b-it:free", messages)


CLEAN_TEXT_RE = re.compile(r"^[가-힣ㄱ-ㅎㅏ-ㅣ\x20-\x7E]*$")


def is_clean_text(text):
    return isinstance(text, str) and bool(CLEAN_TEXT_RE.match(text))


def is_valid_recipe(recipe):
    if not isinstance(recipe, dict):
        return False

    title = recipe.get("title")
    steps = recipe.get("steps")
    estimated_time = recipe.get("estimated_time_minutes")

    if not title or not isinstance(estimated_time, (int, float)):
        return False
    if not isinstance(steps, list) or len(steps) == 0:
        return False
    if not is_clean_text(title):
        return False
    if not all(is_clean_text(step) for step in steps):
        return False

    return True


def generate_recipes(ingredients, options, retry=False):
    options = options or {}
    servings = options.get("servings")
    max_cook_time = options.get("max_cook_time_minutes")
    exclude = options.get("exclude")

    constraints = []
    if servings:
        constraints.append(f"{servings}인분 기준")
    if max_cook_time:
        constraints.append(f"조리 시간은 {max_cook_time}분 이내")
    if exclude:
        constraints.append(f"다음은 제외: {', '.join(exclude)}")
    constraints_text = (" " + ", ".join(constraints) + ".") if constraints else ""

    prompt = (
        f"다음 재료를 활용한 한식 위주 레시피를 3개 추천해줘: {', '.join(ingredients)}."
        f"{constraints_text} "
        "각 레시피는 title(제목), used_ingredients(위 재료 중 사용한 것), "
        "additional_ingredients(보유 재료 외 추가로 필요한 것), "
        "steps(조리 순서, 문자열 배열), estimated_time_minutes(예상 조리 시간, 숫자)를 포함해서 "
        '{"recipes": [...]} 형태의 JSON으로만 응답해줘. 다른 설명은 붙이지 마.'
    )
    if retry:
        prompt += " 이전 응답이 JSON 형식이 아니었습니다. 반드시 JSON 객체만 출력하세요."

    messages = [{"role": "user", "content": prompt}]
    return call_openrouter("openai/gpt-oss-20b:free", messages)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/profile", methods=["POST"])
def profile_endpoint():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip()
    nickname = (body.get("nickname") or "").strip()

    if not email or not EMAIL_RE.match(email):
        return jsonify({"error": "올바른 email이 필요합니다."}), 400
    if not nickname:
        return jsonify({"error": "nickname이 필요합니다."}), 400

    user = User.query.filter_by(email=email).first()
    if user is None:
        user = User(email=email, nickname=nickname)
        db.session.add(user)
        db.session.commit()

    return jsonify({"user_id": user.id, "email": user.email, "nickname": user.nickname})


@app.route("/api/recipes/save", methods=["POST"])
def save_recipe_endpoint():
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    title = body.get("title")
    steps = body.get("steps")
    estimated_time_minutes = body.get("estimated_time_minutes")

    if not user_id or not title or not steps or estimated_time_minutes is None:
        return jsonify({"error": "user_id, title, steps, estimated_time_minutes가 필요합니다."}), 400

    if User.query.get(user_id) is None:
        return jsonify({"error": "존재하지 않는 user_id입니다."}), 404

    recipe = SavedRecipe(
        user_id=user_id,
        title=title,
        used_ingredients=body.get("used_ingredients") or [],
        additional_ingredients=body.get("additional_ingredients") or [],
        steps=steps,
        estimated_time_minutes=estimated_time_minutes,
    )
    db.session.add(recipe)
    db.session.commit()

    return jsonify({"id": recipe.id, "message": "저장되었습니다."}), 201


@app.route("/api/recipes/saved", methods=["GET"])
def list_saved_recipes_endpoint():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id가 필요합니다."}), 400

    recipes = (
        SavedRecipe.query.filter_by(user_id=user_id)
        .order_by(SavedRecipe.created_at.desc())
        .all()
    )
    return jsonify({"recipes": [r.to_summary_dict() for r in recipes]})


@app.route("/api/recipes/saved/<int:recipe_id>", methods=["GET"])
def get_saved_recipe_endpoint(recipe_id):
    recipe = SavedRecipe.query.get(recipe_id)
    if recipe is None:
        return jsonify({"error": "레시피를 찾을 수 없습니다."}), 404
    return jsonify(recipe.to_detail_dict())


@app.route("/api/recipes/saved/<int:recipe_id>", methods=["DELETE"])
def delete_saved_recipe_endpoint(recipe_id):
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id가 필요합니다."}), 400

    recipe = SavedRecipe.query.get(recipe_id)
    if recipe is None:
        return jsonify({"error": "레시피를 찾을 수 없습니다."}), 404
    if str(recipe.user_id) != str(user_id):
        return jsonify({"error": "본인 소유의 레시피만 삭제할 수 있습니다."}), 403

    db.session.delete(recipe)
    db.session.commit()
    return jsonify({"message": "삭제되었습니다."})


@app.route("/api/generate-recipes", methods=["POST"])
def generate_recipes_endpoint():
    body = request.get_json(silent=True) or {}
    ingredients = body.get("ingredients")
    if not ingredients:
        return jsonify({"error": "ingredients가 필요합니다."}), 400

    options = body.get("options")

    response = generate_recipes(ingredients, options)
    if not response.ok:
        return jsonify({"error": openrouter_error_message(response)}), 502

    content = response.json()["choices"][0]["message"]["content"]
    parsed = extract_json_object(content)
    valid_recipes = [r for r in parsed.get("recipes", [])] if parsed else []
    valid_recipes = [r for r in valid_recipes if is_valid_recipe(r)]

    if not valid_recipes:
        retry_response = generate_recipes(ingredients, options, retry=True)
        if not retry_response.ok:
            return jsonify({"error": openrouter_error_message(retry_response)}), 502
        retry_content = retry_response.json()["choices"][0]["message"]["content"]
        retry_parsed = extract_json_object(retry_content)
        retry_recipes = [r for r in retry_parsed.get("recipes", [])] if retry_parsed else []
        valid_recipes = [r for r in retry_recipes if is_valid_recipe(r)]

    if not valid_recipes:
        return jsonify({"error": "유효한 레시피를 생성하지 못했습니다. 다시 시도해주세요."}), 422

    return jsonify({"recipes": valid_recipes})


@app.route("/api/recognize-ingredients", methods=["POST"])
def recognize_ingredients_endpoint():
    image_file = request.files.get("image")
    if not image_file or image_file.filename == "":
        return jsonify({"error": "image 파일이 필요합니다."}), 400

    image_bytes = image_file.read()
    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        return jsonify({"error": "이미지 용량은 5MB를 초과할 수 없습니다."}), 400

    mime_type = image_file.mimetype or "image/jpeg"
    image_data_uri = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('utf-8')}"

    response = recognize_ingredients(image_data_uri)
    if not response.ok:
        return jsonify({"error": openrouter_error_message(response)}), 502

    content = response.json()["choices"][0]["message"]["content"]
    parsed = extract_json_object(content)

    if parsed is None or "ingredients" not in parsed:
        retry_response = recognize_ingredients(image_data_uri, retry=True)
        if not retry_response.ok:
            return jsonify({"error": openrouter_error_message(retry_response)}), 502
        retry_content = retry_response.json()["choices"][0]["message"]["content"]
        parsed = extract_json_object(retry_content)

    if parsed is None or "ingredients" not in parsed:
        return jsonify({"error": "모델 응답을 JSON으로 파싱하지 못했습니다."}), 422

    return jsonify({"ingredients": parsed["ingredients"]})


@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json(silent=True) or {}
    message = body.get("message")
    if not message:
        return jsonify({"error": "message가 필요합니다."}), 400

    response = requests.post(
        url=OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": message}],
        },
    )

    if not response.ok:
        return jsonify({"error": openrouter_error_message(response)}), response.status_code

    reply = response.json()["choices"][0]["message"]["content"]
    return jsonify({"reply": reply})


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
