# یادداشت‌های runtime Xray

Xray در پیکربندی خود outboundها را به‌عنوان مسیر ارسال ترافیک تعریف می‌کند و ساختار کلی outbound شامل `protocol`، `settings`، `streamSettings`، `tag` و تنظیمات حمل‌ونقل است. Kaveh باید مدل `CanonicalConfig` را در adapter به همین ساختار تبدیل کند و برای probe یک inbound محلی موقت بسازد.

راهنمای رسمی نصب Xray می‌گوید binaryهای precompiled در GitHub Releases منتشر می‌شوند. بنابراین deployment production باید نسخهٔ مشخص binary را به‌صورت قابل‌بازتولید نصب و قبل از اجرا hash/checksum آن را تأیید کند؛ runner Kaveh binary را از `XRAY_BINARY` می‌گیرد و نباید در هر اجرای scheduled از وب دانلود کند.

منابع:
- https://xtls.github.io/en/config/outbound.html
- https://xtls.github.io/en/document/install.html
