# یافته‌های پژوهشی برای delivery در اختلال‌های اینترنت ایران

## منابع و نکات کلیدی

### Cloudflare Radar

- URL: https://blog.cloudflare.com/iran-protests-internet-shutdown/
- در ۸ ژانویهٔ ۲۰۲۶، Cloudflare ترافیک خروجی از ایران را در مرحلهٔ نهایی به نزدیک صفر مشاهده کرد؛ این رخداد نشان می‌دهد هیچ CDN خارجی، از جمله Cloudflare، هنگام قطع کامل بین‌الملل نمی‌تواند در دسترس‌بودن ساب‌لینک را تضمین کند.
- پیش از سقوط کامل، ترافیک IPv6 و استفاده از HTTP/3/QUIC در برخی ISPها به‌شدت کاهش یافت. این یک سیگنال عملی است که تکیهٔ انحصاری بر QUIC/TUIC/Hysteria برای resilience خطاست.
- دسترسی به DNS عمومی و برخی ASNها در دوره‌هایی کوتاه بازگشت و سپس از دست رفت؛ بنابراین delivery باید cacheable، short-lived و دارای fallback باشد، نه مبتنی بر یک hostname یا یک provider.

### IODA

- URL: https://ioda.inetintel.cc.gatech.edu/reports/a-comparative-look-at-internet-shutdowns-in-iran-2019-2022-2026-and-2026/
- IODA میان اتصال بین‌المللی و دسترسی به شبکهٔ ملی اطلاعات (NIN) تمایز می‌گذارد. در قطع‌های ۲۰۱۹ و ۲۰۲۶، دسترسی به اینترنت جهانی می‌تواند تقریباً از بین برود، هرچند NIN یا دسترسی whitelist‌شده ممکن است باقی بماند.
- قطع ۲۰۲۵ بدون withdrawal گستردهٔ BGP و با allowlisting/filtering در gateway ملی رخ داد؛ بنابراین فقط نگاه‌کردن به BGP یا DNS برای health-check کافی نیست.
- نتایج میان ISP، fixed-line و mobile و حتی مکان‌های جغرافیایی متفاوت است. هیچ source یا protocol نمی‌تواند «حتماً کار می‌کند» نام‌گذاری شود.

### مقالهٔ مرور shutdown ژانویهٔ ۲۰۲۶

- URL: https://arxiv.org/html/2603.28753v1
- مقاله یک censorship stack چندلایه را توصیف می‌کند: DNS interception/poisoning، HTTP/HTTPS/SNI inspection، RST injection و پایش/فیلتر انتخابی UDP/QUIC.
- مقاله بر تفاوت vantage و تغییرپذیری ISP/ASN تاکید می‌کند و پیشنهاد ضمنی طراحی، سنجش evidence از چند vantage و ثبت failure classهای aggregate است.

## نتیجهٔ معماری برای Pusheen V2Ray

1. Cloudflare Gateway مسیر delivery مستقل از GitHub است، اما guarantee در قطع کامل بین‌الملل نیست.
2. Tierهای TCP/evidence باید صریحاً محدودیت vantage را نمایش دهند و strict فقط با E2E evidence تازه تغییر کند.
3. پروتکل‌ها باید به‌صورت portfolio منتشر شوند: ترکیب TCP+TLS/Reality و WebSocket/TLS همراه با QUIC-nativeها؛ نه برجسته‌سازی یک پروتکل به‌عنوان راه‌حل قطعی.
4. اولویت بعدی، افزوده‌شدن vantageهای داخل/نزدیک ایران با consent و کنترل امنیتی، و health score جداگانه برحسب ASN/ISP/path است.
5. انتشار aggregate failure histogram در status، بدون URI یا credential، برای تشخیص DNS، TCP، runtime و E2E failure ضروری است.
