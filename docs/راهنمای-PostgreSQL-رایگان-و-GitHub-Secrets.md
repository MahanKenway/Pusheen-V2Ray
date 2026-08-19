# راهنمای اتصال PostgreSQL رایگان و GitHub Secrets برای Pusheen V2Ray

این راهنما Pusheen V2Ray را به یک PostgreSQL میزبان‌شده وصل می‌کند تا workflow گیت‌هاب بتواند history اعتبارسنجی و وضعیت configها را نگه دارد. مسیر پیشنهادی از **Neon** استفاده می‌کند، زیرا یک PostgreSQL مدیریت‌شده با مسیر اتصال استاندارد ارائه می‌دهد. پیش از ساخت حساب، شرایط و سقف‌های پلن رایگانِ فعلی را در صفحهٔ ثبت‌نام سرویس بررسی کنید؛ این سقف‌ها ممکن است تغییر کنند.

> **قاعدهٔ امنیتی:** کل `connection string` شامل رمز است. آن را فقط در GitHub **Secret** بگذارید؛ نه در repository variable، نه در فایل source، نه در Issue و نه در پیام عمومی.

## 1. ساخت PostgreSQL رایگان در Neon

ابتدا به [Neon](https://neon.com/) بروید، ثبت‌نام کنید و یک **Project** جدید با نامی مانند `kaveh-prod` بسازید. نزدیک‌ترین region به runner یا کاربران اولیه را انتخاب کنید. پس از ساخت project، Neon معمولاً یک database و role اولیه ایجاد می‌کند.

در Dashboard پروژه روی **Connect** بزنید. در پنجرهٔ اتصال، branch، database و role درست را انتخاب کنید. برای Kaveh در این مرحله **Connection pooling** را خاموش کنید و **direct connection string** را کپی کنید؛ زیرا workflow Kaveh در هر اجرا اتصال کمی دارد و migration اولیه نیز انجام می‌دهد. Connection string فرمی شبیه نمونهٔ زیر دارد:

```text
postgresql://ROLE:PASSWORD@HOST/DATABASE?sslmode=require
```

Neon اعلام می‌کند که connection string شامل role، password، hostname و database است و از پنجرهٔ **Connect** در Dashboard قابل دریافت است. [1]

## 2. ثبت `KAVEH_DATABASE_URL` به‌عنوان GitHub Secret

در [مخزن Pusheen-V2Ray](https://github.com/MahanKenway/Pusheen-V2Ray) مسیر زیر را باز کنید:

```text
Settings → Secrets and variables → Actions → Secrets → New repository secret
```

در بخش **Name** دقیقاً این نام را وارد کنید:

```text
KAVEH_DATABASE_URL
```

در بخش **Secret** همان direct connection string کپی‌شده از Neon را paste کنید و **Add secret** را بزنید. GitHub برای ساخت repository secret همین مسیر Settings → Secrets and variables → Actions → Secrets → New repository secret را مستند کرده است. [2]

پس از ثبت، GitHub فقط نام secret را نشان می‌دهد و مقدار آن را دوباره نمایش نمی‌دهد؛ بنابراین پیش از ذخیره از کامل‌بودن URL مطمئن شوید. اگر رمز را گم کردید، در Neon آن را reset کنید و secret را update کنید.

## 3. ثبت Repository Variableهای غیرحساس

در همان صفحهٔ **Secrets and variables → Actions** این بار tab **Variables** را انتخاب کنید. برای هر مورد روی **New repository variable** بزنید و مقادیر زیر را وارد کنید.

| نام variable | مقدار پیشنهادی آغازین | کاربرد |
|---|---|---|
| `KAVEH_PROBE_URL` | یک URL HTTPS مورد اعتماد که پاسخ `204` می‌دهد | مقصد آزمایش از درون SOCKS موقت Xray |
| `KAVEH_VANTAGE_ID` | `github-actions` | مشخص‌کردن محل/دید اجرای probe |
| `KAVEH_CANDIDATE_LIMIT` | `12` | حداکثر config برای هر اجرای ۱۵ دقیقه‌ای |
| `KAVEH_AUTOMATION_ENABLED` | ابتدا خالی یا `false` | کلید روشن‌کردن workflow |

برای `KAVEH_PROBE_URL` بهتر است endpoint خودتان داشته باشید؛ این endpoint باید فقط HTTPS باشد و به درخواست `HEAD` با status `204` پاسخ دهد. اگر هنوز endpoint اختصاصی ندارید، فقط برای شروع از endpointی استفاده کنید که صریحاً آن را تأیید می‌کنید و بعداً آن را با endpoint تحت کنترل خودتان جایگزین کنید.

> `KAVEH_DATABASE_URL` هرگز نباید در Variables قرار گیرد؛ تنها در Secrets باشد. GitHub مقدار Secret را به workflow با `secrets` context می‌دهد، درحالی‌که variableها برای تنظیمات غیرحساس هستند. [2]

## 4. اجرای migration و آزمون نخست

workflow Pusheen V2Ray پیش از validation، migrationها را اجرا می‌کند. بعد از ثبت secret و سه variable اول، ابتدا یک اجرای دستی انجام دهید:

1. به tab **Actions** مخزن بروید.
2. از فهرست سمت چپ **Pusheen V2Ray Subscription Pipeline** را انتخاب کنید.
3. روی **Run workflow** بزنید و branch `main` را انتخاب کنید.
4. logها را باز کنید و نتیجهٔ مرحلهٔ `Validate and build subscriptions` را بررسی کنید.

در نخستین اجرای موفق، schema PostgreSQL شامل configها، source observationها، validation runها، probe resultها، status، scorecard و publication snapshotها ساخته می‌شود. اگر هیچ configی end-to-end qualified نشود، workflow با رفتار امن اجرا می‌شود اما subscription خالی می‌ماند و commit جدید نمی‌زند.

## 5. روشن‌کردن اجرای خودکار

پس از آن‌که اجرای دستی موفق شد، مقدار variable زیر را دقیقاً روی `true` بگذارید:

```text
KAVEH_AUTOMATION_ENABLED=true
```

Workflow سپس در دقیقه‌های **07، 22، 37 و 52** هر ساعت اجرا می‌شود. این یعنی cadence هدف ۱۵ دقیقه است. اجراهای schedule در GitHub best-effort هستند؛ ممکن است هنگام بار بالا کمی تأخیر داشته باشند، پس این زمان یک SLA قطعی نیست. workflow Pusheen V2Ray هم‌پوشانی اجراها را با concurrency block می‌کند، Xray را cache می‌کند، timeout دارد و فقط زمانی commit می‌زند که محتوای qualified feed واقعاً تغییر کرده باشد.

## 6. بررسی نتیجه و subscription

پس از نخستین انتشار qualified، این URLها باید محتوا داشته باشند:

| خروجی | URL |
|---|---|
| Raw همهٔ configهای qualified | `https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/all.txt` |
| Base64 subscription | `https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/all.base64` |
| manifest کیفیت | `https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/manifest.v1.json` |

از `manifest.v1.json` برای دیدن تعداد config، زمان snapshot، policy version و وضعیت منبع‌ها استفاده کنید. فایل‌های `subscriptions/vless.*`، `subscriptions/vmess.*`، `subscriptions/trojan.*` و `subscriptions/ss.*` فقط پس از آن‌که نخستین مورد qualified از آن protocol منتشر شود ایجاد می‌شوند.

## رفع اشکال سریع

| نشانه | علت محتمل | اقدام |
|---|---|---|
| workflow اجرا نمی‌شود | `KAVEH_AUTOMATION_ENABLED` دقیقاً `true` نیست | variable را در repository actions variables بررسی کنید |
| `password authentication failed` | password یا connection string اشتباه/قدیمی است | از Neon یک direct URL تازه بگیرید و Secret را update کنید |
| `connection timed out` | URL اتصال عمومی نیست یا تنظیمات شبکهٔ سرویس مانع شده | direct URL دارای `sslmode=require` را استفاده کنید؛ ابتدا اتصال را در Neon SQL Editor بررسی کنید |
| subscription خالی است | هیچ candidate مسیر end-to-end را با موفقیت طی نکرده | logهای workflow و `manifest.v1.json` را بررسی کنید؛ source policy و probe endpoint را بازبینی کنید |
| workflow طولانی یا timeout است | `KAVEH_CANDIDATE_LIMIT` برای runner زیاد است | مقدار را به 6 یا 8 کاهش دهید و دوباره اجرا کنید |

## منابع

[1] [Neon — Connect from any application](https://neon.com/docs/connect/connect-from-any-app)

[2] [GitHub Docs — Using secrets in GitHub Actions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)
