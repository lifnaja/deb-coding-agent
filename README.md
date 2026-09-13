# Currency Data Platform

Data platform สำหรับข้อมูลอัตราแลกเปลี่ยนสกุลเงิน ingest ด้วย Apache Airflow
transform ด้วย dbt และเก็บข้อมูลบน Google BigQuery

```text
currency-api (CDN)  ──▶  Airflow  ──▶  BigQuery raw  ──▶  dbt staging (view)  ──▶  dbt marts (table)
```

แหล่งข้อมูลคือ [`@fawazahmed0/currency-api`](https://github.com/fawazahmed0/exchange-api)
ซึ่งเป็น API สาธารณะ ไม่ต้องใช้ API key และออกข้อมูลเป็นชุดต่อหนึ่งวัน

> อัตราแลกเปลี่ยนของแต่ละเจ้าไม่เท่ากัน ตัวเลขที่ได้จึงไม่ตรงกับ Google หรือ ธนาคาร

ขั้นตอน setup และใช้งานโปรเจกต์อยู่ในไฟล์นี้ ส่วนคำแนะนำสำหรับ AI coding
agent อยู่ที่ [AGENTS.md](AGENTS.md)

## โครงสร้างโปรเจกต์

```text
.
├── airflow/             # Airflow Docker Compose environment
│   ├── dags/            # DAG files
│   ├── config/          # local Airflow config ที่ container สร้างให้
│   └── plugins/         # Airflow plugins
├── dbt/                 # dbt project สำหรับ BigQuery จัดการด้วย Poetry
│   ├── models/          # staging (view) และ marts (table)
│   ├── profiles.yml     # dbt profile (อยู่ที่ root ของ dbt/)
│   ├── .sqlfluff        # rule ของ SQL linter
│   └── pyproject.toml   # dependencies
├── scripts/             # Python utilities (stdlib อย่างเดียว)
├── example-mcp/         # PostgreSQL + MCP server สำหรับข้อมูล Greeenery
├── greeenery/           # CSV เริ่มต้นที่โหลดเข้า PostgreSQL
├── secrets/             # GCP key file (gitignore ทั้งโฟลเดอร์)
├── .devcontainer/       # GitHub Codespaces configuration
├── .agents/skills/      # skill สำหรับ AI coding agent
└── docs/                # เอกสาร environment และการดูแล workshop
```

## ข้อกำหนดเบื้องต้น

สำหรับรันบนเครื่องตัวเอง:

- Docker Desktop พร้อม Docker Compose v2 และ memory อย่างน้อย 4 GB
- Python 3.10–3.13
- Poetry
- ruff สำหรับ lint โค้ด Python — `pipx install ruff` หรือ `uv tool install ruff`
- Google Cloud CLI (`gcloud`) พร้อม GCP project ที่ใช้ BigQuery ได้

---

## Google Cloud service account

Airflow และ dbt ใช้ service account ตัวเดียวกันชื่อ `currency-platform`

### login ก่อน

คำสั่งในหัวข้อนี้ใช้สิทธิ์ของ user account ไม่ใช่ service account ต้อง login ก่อน

```bash
gcloud auth login
gcloud auth list
```

### สร้าง service account

```bash
export GCP_PROJECT=your-gcp-project-id
export SA_EMAIL="currency-platform@${GCP_PROJECT}.iam.gserviceaccount.com"

gcloud iam service-accounts create currency-platform \
  --project "$GCP_PROJECT" \
  --display-name "Currency platform (Airflow + dbt)"

gcloud projects add-iam-policy-binding "$GCP_PROJECT" \
  --member "serviceAccount:${SA_EMAIL}" \
  --role roles/bigquery.jobUser

gcloud projects add-iam-policy-binding "$GCP_PROJECT" \
  --member "serviceAccount:${SA_EMAIL}" \
  --role roles/bigquery.dataEditor

gcloud iam service-accounts keys create secrets/credentials.json \
  --iam-account "$SA_EMAIL"
```

| role | ใช้ทำอะไร |
| --- | --- |
| `roles/bigquery.jobUser` | สร้าง job ทั้ง load job ของ Airflow และ query ของ dbt |
| `roles/bigquery.dataEditor` | อ่าน/เขียน table ใน dataset ปลายทาง |

key file เก็บไว้ที่ `secrets/credentials.json` ที่ root ของ repo **ที่เดียว**
ทั้งสองฝั่งอ่านจากไฟล์เดียวกัน ไม่ต้อง copy ซ้ำ:

| ใช้โดย | อ่านยังไง |
| --- | --- |
| dbt | `profiles.yml` ชี้มาที่ `../secrets/credentials.json` ให้แล้ว |
| Airflow | compose mount ให้ พร้อมตั้ง `GOOGLE_APPLICATION_CREDENTIALS` |

> โฟลเดอร์ `secrets/` ถูก gitignore ทั้งโฟลเดอร์ ไฟล์อะไรวางในนั้นก็ไม่เข้า git
> ไม่ว่าตั้งชื่อว่าอะไร **อย่าวาง key ไว้ใน `airflow/dags/`** เพราะโฟลเดอร์นั้น
> git track อยู่ ตั้งชื่อไฟล์พลาดนิดเดียวก็ commit key ขึ้น repo ได้

### ปิดการใช้งานหลังจบ workshop

key ที่สร้างไว้ไม่มีวันหมดอายุ ทำ workshop เสร็จแล้วให้ปิดทิ้งทุกครั้ง

**ปิดชั่วคราว** — เร็วที่สุด เปิดกลับมาใช้ใหม่ได้ด้วย `enable`

```bash
gcloud iam service-accounts disable "$SA_EMAIL" --project "$GCP_PROJECT"
```

**ลบถาวร** — ถอน role ลบ service account แล้วลบ key ในเครื่อง

```bash
gcloud projects remove-iam-policy-binding "$GCP_PROJECT" \
  --member "serviceAccount:${SA_EMAIL}" \
  --role roles/bigquery.jobUser

gcloud projects remove-iam-policy-binding "$GCP_PROJECT" \
  --member "serviceAccount:${SA_EMAIL}" \
  --role roles/bigquery.dataEditor

gcloud iam service-accounts delete "$SA_EMAIL" --project "$GCP_PROJECT"

rm secrets/credentials.json
```

ถ้าเปิด shell ใหม่แล้ว `$SA_EMAIL` กับ `$GCP_PROJECT` หายไป ให้ `export` ใหม่
ตามหัวข้อด้านบนก่อน

> การลบ service account จะทำให้ key ที่สร้างไปแล้วใช้ไม่ได้ทันที แต่ไฟล์ในเครื่อง
> ยังอยู่ ต้อง `rm` เองเพื่อไม่ให้ค้างอยู่ในโฟลเดอร์ของคนเรียน

---

## Airflow

ใช้ official Docker Compose quick-start ของ Airflow (image
`apache/airflow:3.3.1`) ตั้งเป็น `LocalExecutor` และ PostgreSQL 16

```bash
cd airflow
cp .env.example .env       # บน Linux ตั้ง AIRFLOW_UID=$(id -u) ด้วย
docker compose up airflow-init
docker compose up -d
```

path ที่ container mount จากโฟลเดอร์ `airflow/`:

| host | container |
| --- | --- |
| `airflow/dags/` | `/opt/airflow/dags` |
| `airflow/logs/` | `/opt/airflow/logs` |
| `airflow/config/` | `/opt/airflow/config` |
| `airflow/plugins/` | `/opt/airflow/plugins` |
| `secrets/` (repo root) | `/opt/airflow/secrets` (read-only) |

---

## dbt + BigQuery

dbt ใช้ Poetry จัดการ dependencies และใช้ official `dbt-bigquery` adapter
authentication ใช้ key file ของ service account `currency-platform` ผ่าน
`method: service-account` (ดูวิธีสร้างที่หัวข้อด้านบน)

### ตั้งค่าครั้งแรก

```bash
cd dbt
poetry install
poetry run dbt debug
```

### รัน dbt

รันจากโฟลเดอร์ `dbt/` เสมอ

```bash
poetry run dbt debug    # ตรวจสอบการเชื่อมต่อ BigQuery
poetry run dbt build    # seed + run + test
poetry run dbt run
poetry run dbt test
```

Lint SQL — rule ตั้งไว้ที่ `dbt/.sqlfluff` (dialect `bigquery`, keyword และ
identifier ต้องเป็นตัวเล็ก):

```bash
poetry run sqlfluff lint models/
poetry run sqlfluff fix  models/
```

### โครงสร้าง models

- `models/staging/` — materialize เป็น `view` ตั้งชื่อ `stg_<source>_<entity>`
- `models/marts/` — materialize เป็น `table` ตั้งชื่อตาม business concept
- ค่า materialization ตั้งไว้ที่ `dbt_project.yml` แล้ว ไม่ต้องใส่
  `{{ config() }}` ซ้ำ นอกจากโมเดลนั้นต่างจากค่าเริ่มต้นจริง ๆ

`models/example/example.sql` เป็น smoke test สำหรับทดสอบการเชื่อมต่อ ลบได้
เมื่อมี staging และ marts models จริงแล้ว

---

## Scripts

`scripts/load_currency.py` ดึงข้อมูล BTC หนึ่งวันจาก currency API แล้วเขียนเป็น
JSON ไม่รับ argument ค่าทั้งหมด hardcode ไว้ในไฟล์ ใช้ Python standard library
ล้วน ไม่ต้องติดตั้ง dependency เพิ่ม

```bash
python scripts/load_currency.py
```

```text
Loaded https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@2026-09-01/v1/currencies/btc.json
Wrote  scripts/data/2026-09-01/btc.json
```

ค่าที่ hardcode ไว้ แก้ได้ที่หัวไฟล์:

| ค่า | ตัวแปรใน script |
| --- | --- |
| `btc` | `CURRENCY` |
| `2026-09-01` | `DATE` |
| `scripts/data` | `OUTPUT_DIR` |
| URL template | `URL_TEMPLATE` |

เขียนไปที่ `scripts/data/<DATE>/btc.json` แยกโฟลเดอร์ตามวันที่ เปลี่ยน `DATE`
แล้วรันใหม่จึงไม่ทับของเดิม เนื้อในโฟลเดอร์ `scripts/data/` ถูก gitignore ไว้
เก็บแค่ `.gitkeep` ถ้าโหลดไม่สำเร็จ script จะพิมพ์ error ลง stderr และ exit
ด้วย code 1

script นี้ครอบเฉพาะขั้น "ดึงข้อมูลจาก API" การวนวันที่เพื่อ backfill และการ
โหลดขึ้น BigQuery จะไปทำใน Airflow DAG

---

## Example MCP + PostgreSQL

`example-mcp/` สร้าง PostgreSQL จาก CSV ทั้ง 7 ไฟล์ใน `greeenery/` และเปิด MCP
server แบบ Streamable HTTP ที่มี tool เดียวชื่อ `query` สำหรับรัน SQL แบบ
read-only

```bash
cd example-mcp
docker compose up --build -d
docker compose ps
```

บริการที่เปิดบนเครื่อง:

| บริการ | endpoint |
| --- | --- |
| PostgreSQL | `localhost:5433` |
| MCP | `http://localhost:8000/mcp` |

ส่ง argument ให้ tool `query` ในรูป `{"sql": "select * from products"}`
ผลลัพธ์จะคืนไม่เกิน 1,000 แถว และ query จะ timeout หลัง 5 วินาที บัญชีที่ MCP
ใช้มีสิทธิ์อ่านอย่างเดียว จึงแก้ไขข้อมูลหรือ schema ไม่ได้

ตรวจ integration ผ่าน MCP protocol ได้ด้วย:

```bash
docker compose exec -T \
  -e MCP_URL=http://127.0.0.1:8000/mcp \
  mcp python -m unittest tests.test_server.HttpSmokeTest
```

PostgreSQL โหลด CSV เฉพาะตอนสร้าง volume ครั้งแรก ถ้าต้องการโหลด CSV ใหม่ให้ลบ
volume แล้วเริ่มบริการอีกครั้ง (ข้อมูลใน database เดิมจะถูกลบ):

```bash
docker compose down -v
docker compose up --build -d
```

หยุดบริการโดยไม่ลบข้อมูล:

```bash
docker compose down
```

---

## ข้อมูลอ้างอิง

- [Apache Airflow Docker Compose](https://airflow.apache.org/docs/apache-airflow/stable/howto/docker-compose.html)
- [GCP service-account keys](https://cloud.google.com/iam/docs/keys-create-delete)
- [dbt BigQuery adapter](https://docs.getdbt.com/docs/core/connect-data-platform/bigquery-setup)
- [currency-api (fawazahmed0)](https://github.com/fawazahmed0/exchange-api)
