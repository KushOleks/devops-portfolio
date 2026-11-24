# Лабораторна робота №5 — контейнеризація Wishlist

Командні репозиторії: [API](https://github.com/KushOleks/withlist-api) і
[UI](https://github.com/KushOleks/wishlist-ui). Продовження проєкту лабораторної №4.

## Внесок

У [API PR №8](https://github.com/KushOleks/withlist-api/pull/8) підготовлено non-root
образ API, runtime lock із хешами, production Compose, dev-профіль і Docker/GHCR/Trivy CI.
У [UI PR №5](https://github.com/KushOleks/wishlist-ui/pull/5) реалізовано multi-stage
Node/nginx, build-time адресу API, SPA fallback і публікацію образу. Обидва PR
схвалені з акаунта Porchuk після зеленого required CI та злиті власником KushOleks.
Поломку для діагностики обирав оператор окремим інтерактивним скриптом;
під час повторного прогону її тип до перевірок не повідомлявся.

## Запуск із клону

Потрібні Git та Docker з Compose 2.24.4+. На Mac запускати Docker Desktop.

```bash
mkdir -p ~/DevOps/lab-05
cd ~/DevOps/lab-05
git clone https://github.com/KushOleks/withlist-api.git
git clone https://github.com/KushOleks/wishlist-ui.git
cd withlist-api
cp .env.example .env
```

Заповнити у `.env` **POSTGRES_PASSWORD** та **SECRET_KEY** різними випадковими
значеннями (для кожного: `openssl rand -hex 32`). Їх не комітити.
За замовчуванням UI_PORT=8080, API_PORT=8000, VITE_API_BASE=http://localhost:8000.
Якщо змінюються порти, узгодити VITE_API_BASE та ALLOWED_ORIGINS і перебудувати UI.

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Відкрити UI http://localhost:8080 та API http://localhost:8000/docs.
Зареєструвати користувача, створити список і бажання, оновити сторінку.
PostgreSQL і Redis доступні лише всередині Compose; host ports є тільки для API та UI.

На Mac власника поточні секрети лабораторної збережено окремо в `.env.lab05`:
в існуючій папці `/Users/mac/Documents/DevOps/lab-04/withlist-api` запускати
`docker compose --env-file .env.lab05 up -d --build`.
Це ті самі командні репозиторії, їх не потрібно повторно клонувати для кожної роботи.

## Основні завдання

1. **API:** Python 3.12.12-slim-bookworm, appuser UID 10001, exec CMD,
   0.0.0.0:8000, залежності окремим кешованим шаром, lock з хешами.
   .dockerignore та явний COPY виключають .env, Git, тести й віртуальні оточення.
   Виміряна зупинка — **0,567 с**. Зміна коментаря коду зберігає CACHED для pip install.
2. **UI:** build на Node 24.21.0-alpine через npm ci; production — nginx 1.28.0-alpine.
   ARG VITE_API_BASE передається до Vite build. Runtime environment nginx не змінює
   вже створений JavaScript. nginx try_files обслуговує глибокі SPA-маршрути без 404.
3. **Compose:** чотири healthcheck, API залежить від здорових PostgreSQL/Redis,
   named volume PostgreSQL, restart для всіх сервісів, required secrets без default.
   UI → API → PostgreSQL перевірено через реальний браузер. Запис окремого тестового
   project пережив down/up, але після down -v/up повернувся 404: його том був видалений.
   Робочі дані та том лабораторної №4 збережено.
4. **GHCR:** Docker jobs запускаються після попередніх перевірок і є required checks
   для main. PR збирає без push; main публікує main та sha-<повний коміт>;
   v* публікує 1.0.0, 1.0, 1 та latest. Вхід лише через GITHUB_TOKEN з явними permissions.
   Релізи v1.0.0 та публічні GHCR-пакети підтверджені:
   [API release](https://github.com/KushOleks/withlist-api/releases/tag/v1.0.0),
   [UI release](https://github.com/KushOleks/wishlist-ui/releases/tag/v1.0.0),
   [API package](https://github.com/KushOleks/withlist-api/pkgs/container/wishlist-api),
   [UI package](https://github.com/KushOleks/wishlist-ui/pkgs/container/wishlist-ui).
   Обидва теги 1.0.0 завантажені без login із порожнім DOCKER_CONFIG.
5. **Діагностика:** контрольний стек мав healthy API й правильний mapping 19000:8000,
   але host HTTP не працював. Внутрішній HTTP повертав 200; /proc/1/cmdline показав
   --host 127.0.0.1. Це крок перевірки bind-адреси в чеклисті лекції 5.
   Повернення до --host 0.0.0.0 відновило зовнішній HTTP 200.

| Локальний образ UI, linux/arm64 | Розмір |
|---|---:|
| build | 327303019 байт / 312,14 MiB |
| production | 49993633 байт / 47,68 MiB |

Найбільше на build-етапі займає /app/node_modules — 153,8 MiB;
/usr/local — 147,3 MiB, dist — 172 KiB. Node/node_modules у production відсутні.

## Бонуси

1. **Розробка:** `docker compose -f compose.yaml -f compose.dev.yaml --profile dev up --build --watch`.
   API sync+restart та Vite bind mount перевірені без зміни image ID.
   Зміна requirements.txt автоматично запустила rebuild/recreate API.
   Після зміни залежностей оновлюється requirements-runtime.txt.
   node_modules UI живе в окремому Linux-томі; npm ci при старті dev-сервісу
   узгоджує його з lock-файлом, не використовуючи host node_modules.
2. **Trivy:** окремі advisory jobs з JSON-артефактами на 14 днів, не required checks.
   [API-прогін](https://github.com/KushOleks/withlist-api/actions/runs/45494531646):
   512 OS та 52 application записи. [UI-прогін](https://github.com/KushOleks/wishlist-ui/actions/runs/45494718518):
   198 OS та 0 application записів. В обох більшість — базові OS-пакети.
   Це записи пакет/CVE, не кількість унікальних CVE; результати змінюються з базою сканера.
3. **Архітектури:** CI публікує linux/amd64 та linux/arm64 під одним тегом.
   [Manifest API](https://github.com/KushOleks/withlist-api/blob/main/docs/containers-assets/release-manifest.txt)
   і [manifest UI](https://github.com/KushOleks/wishlist-ui/blob/main/docs/containers-assets/release-manifest.txt)
   показують обидві архітектури під тегом 1.0.0. unknown/unknown — службові attestations.

## Докладні докази

- [API: контейнери, том, кеш, діагностика](https://github.com/KushOleks/withlist-api/blob/main/docs/containers.md).
- [UI: розміри, nginx та сканування](https://github.com/KushOleks/wishlist-ui/blob/main/docs/containers.md).
- [Сирий лог тому](https://github.com/KushOleks/withlist-api/blob/main/docs/containers-assets/volume-proof.log).
- [Сирий лог кешу](https://github.com/KushOleks/withlist-api/blob/main/docs/containers-assets/api-cache-proof.log).

## Релізні перевірки

- [API release CI](https://github.com/KushOleks/withlist-api/actions/runs/45497369021).
- [UI release CI](https://github.com/KushOleks/wishlist-ui/actions/runs/45496937038).
- [API PR №9 з релізними доказами](https://github.com/KushOleks/withlist-api/pull/9).
- [UI PR №6 з релізними доказами](https://github.com/KushOleks/wishlist-ui/pull/6).

```bash
docker pull ghcr.io/kusholeks/wishlist-api:1.0.0
docker pull ghcr.io/kusholeks/wishlist-ui:1.0.0
docker buildx imagetools inspect ghcr.io/kusholeks/wishlist-api:1.0.0
docker buildx imagetools inspect ghcr.io/kusholeks/wishlist-ui:1.0.0
```

Звіти Trivy та скриншоти показують фактичний стан контрольних прогонів, а не відсутність
вразливостей. Docker образи доступні публічно без особистого токена.
Встановлений Compose 5.0.2 на Mac мав panic при завершенні watch через Ctrl+C;
синхронізація, HMR і rebuild перед цим пройшли. Production після перевірок healthy.
