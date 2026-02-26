# TSETMC Companies By Industry (CSV Export)

این پروژه لیست شرکت‌های بورسی را بر اساس گروه/صنعت استخراج می‌کند و خروجی CSV می‌سازد.

خروجی اصلی برای هر صنعت یک فایل CSV جداگانه است که **دقیقاً ۳ ستون** دارد:

- `id` (شناسه/insCode)
- `symbol` (نماد)
- `name` (نام شرکت)

همچنین یک فایل تجمیعی هم ساخته می‌شود که ستون `industry` هم دارد.

---

## خروجی‌ها

پس از اجرا:

- پوشه `industries/`
  - برای هر صنعت یک فایل CSV با ۳ ستون: `id, symbol, name`
- فایل `all_companies_with_industry.csv`
  - ستون‌ها: `industry, id, symbol, name`

---

## پیش‌نیازها

- Python 3.10+ (ترجیحاً 3.11 یا 3.12)
- کتابخانه‌ها:
  - `requests`

---

## نصب

### با venv
```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install requests
