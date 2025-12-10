# Public Export — Автоматический экспорт задач

## Обзор

**Public Export** — механизм автоматического экспорта задач из приватного репозитория преподавателей (`private`) в публичный репозиторий (`public`), доступный студентам.

### Как это работает

```
┌─────────────────┐      CI Pipeline      ┌─────────────────┐
│     private     │ ──────────────────▶   │     public      │
│  (преподаватели)│   checker export      │   (студенты)    │
│                 │      --commit         │                 │
│  - решения      │                       │  - шаблоны      │
│  - тесты        │                       │  - публичные    │
│  - конфиги      │                       │    тесты        │
└─────────────────┘                       └─────────────────┘
```

При пуше в `main` ветку `private` репозитория:
1. Запускается CI pipeline
2. Job `deploy-public` копирует публичные файлы
3. Решения заменяются на шаблоны (`.template` файлы)
4. Изменения коммитятся и пушатся в `public`

---

## Структура репозиториев

### Private репозиторий (преподаватели)

```
private/
├── .checker.yml          # Конфигурация checker (приватный)
├── .manytask.yml         # Конфигурация курса (приватный)
├── .releaser-ci.yml      # CI для преподавателей (приватный)
├── .gitlab-ci.yml        # CI для студентов (публичный)
├── base.docker           # Dockerfile базового образа
├── testenv.docker        # Dockerfile тестового окружения
├── pyproject.toml        # Зависимости Python
├── tools/                # Инструменты тестирования (публичный)
│   ├── plugins/
│   └── testlib/
└── Python/               # Группа задач
    ├── .group.yml
    ├── add/              # Задача
    │   ├── .task.yml
    │   ├── add.py            # Решение (НЕ экспортируется)
    │   ├── add.py.template   # Шаблон (экспортируется как add.py)
    │   ├── test_public.py    # Публичные тесты
    │   └── test_private.py   # Приватные тесты (НЕ экспортируется)
    └── subtract/
        └── ...
```

### Public репозиторий (студенты)

```
public/
├── .gitlab-ci.yml        # CI для проверки
├── pyproject.toml
├── tools/
└── Python/
    ├── .group.yml
    ├── add/
    │   ├── .task.yml
    │   ├── add.py            # Шаблон (из add.py.template)
    │   └── test_public.py
    └── subtract/
        └── ...
```

---

## Конфигурация

### 1. `.checker.yml` — структура и экспорт

```yaml
version: 1

structure:
  # Игнорируемые файлы/папки
  ignore_patterns:
    - ".git"
    - "__pycache__"
    - ".venv"
    - "*.pyc"
  
  # Публичные файлы — экспортируются, перезаписываются при тестировании
  public_patterns:
    - ".gitlab-ci.yml"
    - ".task.yml"
    - ".group.yml"
    - "README.md"
    - "test_public.py"
    - "tools"
    - ".gitignore"
  
  # Приватные файлы — НЕ экспортируются
  private_patterns:
    - ".*"              # Все dot-файлы
    - "test_private.py"

export:
  destination: https://gitlab.manytask.org/sandbox/public
  default_branch: main
  commit_message: "chore(auto): export new tasks"
  templates: search_or_create  # search, create, search_or_create
```

### 2. `.manytask.yml` — расписание задач

```yaml
version: 1

settings:
  course_name: MyCourseName
  gitlab_base_url: https://gitlab.manytask.org
  public_repo: sandbox/public
  students_group: sandbox/students

deadlines:
  timezone: Europe/Moscow
  deadlines: hard

  schedule:
    - group: Python
      start: 2025-01-01 18:00:00
      end: 2025-06-01 23:59:00
      enabled: true
      tasks:
        - task: add
          score: 100
        - task: subtract
          score: 100
```

### 3. `.releaser-ci.yml` — CI для экспорта

```yaml
variables:
  REGISTRY: gitlab.manytask.org:5050/sandbox/public

stages:
  - build
  - deploy

deploy-public:
  image: $REGISTRY/base-image:latest
  stage: deploy
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      when: on_success
    - when: never
  script:
    # Клонируем публичный репозиторий
    - git clone https://oauth2:$GITLAB_API_TOKEN@gitlab.manytask.org/sandbox/public ./export
    - cd ./export && git config user.email "ci@manytask.org" && git config user.name "CI Bot" && cd ..
    # Экспортируем и пушим
    - python3 -m checker export --commit
```

---

## Настройка CI/CD Variables

### Обязательные переменные

| Переменная | Описание | Где создать |
|------------|----------|-------------|
| `GITLAB_API_TOKEN` | Токен для push в public репо | Project Settings → CI/CD → Variables |
| `DOCKER_AUTH_CONFIG` | Аутентификация в Docker Registry | Group Settings → CI/CD → Variables |
| `TESTER_TOKEN` | Токен Manytask API | Group Settings → CI/CD → Variables |

### Создание GITLAB_API_TOKEN

1. Перейдите в GitLab → **Group Settings → Access Tokens**
2. Создайте токен:
   - **Name:** `ci-deploy-public`
   - **Role:** **Maintainer**
   - **Scopes:** `write_repository`
3. Добавьте в **CI/CD Variables** репозитория `private`:
   - **Key:** `GITLAB_API_TOKEN`
   - **Value:** созданный токен

---

## Шаблоны задач

### Вариант 1: `.template` файлы (рекомендуется)

Создайте файл `solution.py.template` рядом с `solution.py`:

**solution.py** (решение):
```python
def add(a, b):
    return a + b
```

**solution.py.template** (шаблон для студентов):
```python
def add(a, b):
    # Implement me
```

При экспорте `solution.py.template` заменит `solution.py`.

### Вариант 2: Template comments

Используйте комментарии в коде:

```python
def add(a, b):
    # SOLUTION BEGIN
    return a + b
    # SOLUTION END
```

При экспорте код между комментариями заменится на `# TODO: Your solution`.

---

## Добавление новой задачи

### 1. Создайте структуру

```bash
mkdir -p Python/new_task
```

### 2. Создайте файлы

**Python/new_task/.task.yml:**
```yaml
version: 1
```

**Python/new_task/solution.py:**
```python
def solve():
    return 42
```

**Python/new_task/solution.py.template:**
```python
def solve():
    # Implement me
```

**Python/new_task/test_public.py:**
```python
from solution import solve

def test_solve():
    assert solve() == 42
```

### 3. Добавьте в `.manytask.yml`

```yaml
tasks:
  - task: new_task
    score: 100
```

### 4. Закоммитьте и запушьте

```bash
git add .
git commit -m "Add new_task"
git push origin main
```

Pipeline автоматически экспортирует задачу в `public`.
