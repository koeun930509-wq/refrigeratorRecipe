# 아키텍처 다이어그램

이 문서의 다이어그램은 `app.py`와 `templates/index.html`에 실제로 정의된 함수/라우트/DOM 이벤트 핸들러와, 코드에 실제로 존재하는 호출·요청 흐름만을 근거로 작성했습니다. 코드에 없는 호출은 그리지 않았습니다.

## 1. 함수/컴포넌트 관계도

```mermaid
flowchart TD
  subgraph FE["Frontend — templates/index.html (인라인 JS)"]
    direction TB

    EV_IMG_CHANGE["imageInput 'change' 핸들러"]
    EV_ADD_CLICK["addBtn 'click' 핸들러"]
    EV_RECOG_CLICK["recognizeBtn 'click' 핸들러"]
    EV_RECIPE_CLICK["recipeBtn 'click' 핸들러"]
    EV_PROFILE_CLICK["profileBtn 'click' 핸들러"]
    EV_LOGOUT_CLICK["logoutBtn 'click' 핸들러"]
    IIFE_RESTORE["IIFE: 로그인 상태 복원"]

    renderChips["renderChips()"]
    renderRecipes["renderRecipes(recipes)"]
    setLoggedInUI["setLoggedInUI(loggedIn)"]
    loadSavedList["loadSavedList()"]
    renderSavedList["renderSavedList(recipes)"]
    showSavedDetail["showSavedDetail(id)"]
    stripStepNumber["stripStepNumber(step)"]

    H_REMOVE["removeBtn 'click' (renderChips 내부에서 칩마다 생성)"]
    H_SAVE["saveBtn 'click' (renderRecipes 내부에서 카드마다 생성)"]
    H_DEL["delBtn 'click' (renderSavedList 내부에서 행마다 생성)"]
    H_TITLE["title 'click' (renderSavedList 내부에서 행마다 생성)"]

    renderChips -. 생성 .-> H_REMOVE
    H_REMOVE --> renderChips

    EV_ADD_CLICK --> renderChips
    EV_RECOG_CLICK --> renderChips

    EV_RECIPE_CLICK --> renderRecipes
    renderRecipes --> stripStepNumber
    renderRecipes -. 생성 .-> H_SAVE
    H_SAVE --> loadSavedList

    EV_PROFILE_CLICK --> setLoggedInUI
    EV_PROFILE_CLICK --> loadSavedList
    EV_LOGOUT_CLICK --> setLoggedInUI
    EV_LOGOUT_CLICK --> renderChips
    IIFE_RESTORE --> setLoggedInUI
    IIFE_RESTORE --> loadSavedList

    loadSavedList --> renderSavedList
    renderSavedList -. 생성 .-> H_DEL
    renderSavedList -. 생성 .-> H_TITLE
    H_DEL --> loadSavedList
    H_TITLE --> showSavedDetail
    showSavedDetail --> stripStepNumber
  end

  subgraph BE["Backend — app.py (Flask)"]
    direction TB

    index_route["index() · GET /"]
    profile_endpoint["profile_endpoint() · POST /api/profile"]
    save_recipe_endpoint["save_recipe_endpoint() · POST /api/recipes/save"]
    list_saved_recipes_endpoint["list_saved_recipes_endpoint() · GET /api/recipes/saved"]
    get_saved_recipe_endpoint["get_saved_recipe_endpoint() · GET /api/recipes/saved/&lt;id&gt;"]
    delete_saved_recipe_endpoint["delete_saved_recipe_endpoint() · DELETE /api/recipes/saved/&lt;id&gt;"]
    generate_recipes_endpoint["generate_recipes_endpoint() · POST /api/generate-recipes"]
    recognize_ingredients_endpoint["recognize_ingredients_endpoint() · POST /api/recognize-ingredients"]
    chat_route["chat() · POST /api/chat (프론트에서 호출 안 함)"]

    call_openrouter["call_openrouter(model, messages)"]
    extract_json_object["extract_json_object(text)"]
    recognize_ingredients_fn["recognize_ingredients(image_data_uri, retry)"]
    generate_recipes_fn["generate_recipes(ingredients, options, retry)"]
    is_valid_recipe["is_valid_recipe(recipe)"]
    is_clean_text["is_clean_text(text)"]

    UserModel[("User 테이블")]
    SavedRecipeModel[("SavedRecipe 테이블")]

    recognize_ingredients_endpoint --> recognize_ingredients_fn
    recognize_ingredients_endpoint --> extract_json_object
    recognize_ingredients_fn --> call_openrouter

    generate_recipes_endpoint --> generate_recipes_fn
    generate_recipes_endpoint --> extract_json_object
    generate_recipes_endpoint --> is_valid_recipe
    generate_recipes_fn --> call_openrouter
    is_valid_recipe --> is_clean_text

    profile_endpoint --> UserModel
    save_recipe_endpoint --> UserModel
    save_recipe_endpoint --> SavedRecipeModel
    list_saved_recipes_endpoint --> SavedRecipeModel
    get_saved_recipe_endpoint --> SavedRecipeModel
    delete_saved_recipe_endpoint --> SavedRecipeModel

    chat_route --> chat_direct_request["requests.post() 직접 호출"]
  end

  OpenRouterAPI[["OpenRouter API"]]
  call_openrouter --> OpenRouterAPI
  chat_direct_request --> OpenRouterAPI

  EV_RECOG_CLICK -->|"fetch POST"| recognize_ingredients_endpoint
  EV_RECIPE_CLICK -->|"fetch POST"| generate_recipes_endpoint
  EV_PROFILE_CLICK -->|"fetch POST"| profile_endpoint
  H_SAVE -->|"fetch POST"| save_recipe_endpoint
  loadSavedList -->|"fetch GET"| list_saved_recipes_endpoint
  H_DEL -->|"fetch DELETE"| delete_saved_recipe_endpoint
  showSavedDetail -->|"fetch GET"| get_saved_recipe_endpoint
```

## 2. 데이터 플로우

세 흐름을 잇는 코드가 없어서(서로 다른 진입점에서 시작), 하나로 억지로 합치지 않고 각각 독립된 다이어그램으로 나눴습니다.

### 2.1 재료 인식 흐름

```mermaid
flowchart TD
    A1["사용자가 선택한 이미지 파일\n(imageInput.files[0])"] --> A2["FormData(image)"]
    A2 --> A3["POST /api/recognize-ingredients"]
    A3 --> A4["request.files['image'] 읽기 → image_bytes"]
    A4 --> A5{"image_bytes 크기 > 5MB?"}
    A5 -->|"예"| A6["400 에러 응답"]
    A5 -->|"아니오"| A7["base64 인코딩 →\nimage_data_uri"]
    A7 --> A8["call_openrouter\n(model: google/gemma-4-26b-a4b-it:free)"]
    A8 --> A9["OpenRouter 응답\nchoices[0].message.content"]
    A9 --> A10["extract_json_object(content)"]
    A10 --> A11{"파싱 성공하고\n'ingredients' 키 있음?"}
    A11 -->|"아니오"| A12["retry=True로\n1회 재요청·재파싱"]
    A12 --> A13{"재파싱 성공?"}
    A13 -->|"아니오"| A14["422 에러 응답"]
    A11 -->|"예"| A15["JSON 응답\n{ingredients: [...]}"]
    A13 -->|"예"| A15
    A15 --> A16["프론트: ingredients 배열 갱신"]
    A16 --> A17["renderChips() → 화면에 chip 표시"]
```

### 2.2 레시피 생성 흐름

```mermaid
flowchart TD
    B1["프론트 ingredients 배열"] --> B2["POST /api/generate-recipes\nbody: {ingredients, options}"]
    B2 --> B3["generate_recipes(): 프롬프트 문자열 구성"]
    B3 --> B4["call_openrouter\n(model: openai/gpt-oss-20b:free)"]
    B4 --> B5["OpenRouter 응답 content"]
    B5 --> B6["extract_json_object(content)\n→ parsed.recipes"]
    B6 --> B7["is_valid_recipe()로 필터링\n(title/steps/estimated_time_minutes +\nis_clean_text 검사)"]
    B7 --> B8{"valid_recipes\n비어있음?"}
    B8 -->|"예"| B9["retry=True로 1회 재요청 →\n재파싱 → 재필터링"]
    B9 --> B10{"그래도 비어있음?"}
    B10 -->|"예"| B11["422 에러 응답"]
    B8 -->|"아니오"| B12["JSON 응답 {recipes: [...]}"]
    B10 -->|"아니오"| B12
    B12 --> B13["프론트: renderRecipes(data.recipes)"]
    B13 --> B14["stripStepNumber()로 단계 번호 중복 제거\n→ recipe-card 렌더링"]
```

### 2.3 프로필 · 레시피 저장 흐름

```mermaid
flowchart TD
    C1["email, nickname 입력값"] --> C2["POST /api/profile"]
    C2 --> C3{"EMAIL_RE 형식 검증\n통과?"}
    C3 -->|"아니오"| C4["400 에러 응답"]
    C3 -->|"예"| C5["User.query.filter_by(email)\n조회"]
    C5 --> C6{"기존 User\n있음?"}
    C6 -->|"아니오"| C7["User row 생성 후 commit"]
    C6 -->|"예"| C8["기존 user_id 사용"]
    C7 --> C9["{user_id, email, nickname} 응답"]
    C8 --> C9
    C9 --> C10["프론트: currentUser 변수 +\nlocalStorage('fridge_user') 저장"]

    C10 --> C11["레시피 카드 '저장' 클릭"]
    C11 --> C12["POST /api/recipes/save\nbody: {user_id, title, used_ingredients,\nadditional_ingredients, steps,\nestimated_time_minutes}"]
    C12 --> C13{"User.query.get(user_id)\n존재?"}
    C13 -->|"아니오"| C14["404 에러 응답"]
    C13 -->|"예"| C15["SavedRecipe row 생성 후 commit"]
    C15 --> C16["프론트: loadSavedList() 재호출"]

    C16 --> C17["GET /api/recipes/saved?user_id="]
    C17 --> C18["SavedRecipe.query.filter_by(user_id)\n.order_by(created_at desc)"]
    C18 --> C19["renderSavedList() → 목록 표시"]

    C19 --> C20["행 클릭 → GET /api/recipes/saved/&lt;id&gt;"]
    C20 --> C21["SavedRecipe.query.get(id)\n→ to_detail_dict()"]
    C21 --> C22["showSavedDetail() → 상세 표시"]

    C19 --> C23["삭제 클릭 →\nDELETE /api/recipes/saved/&lt;id&gt;?user_id="]
    C23 --> C24{"recipe.user_id ==\n요청 user_id?"}
    C24 -->|"아니오"| C25["403 에러 응답"]
    C24 -->|"예"| C26["db.session.delete() 후 commit"]
    C26 --> C16
```
