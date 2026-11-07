# JANUS — ملفات البرومبت

هاد المجلد فيه كل ما خاصك باش تطلق الـ agent والتطبيق ديالو.

## شنو كاين

| الملف | الاستعمال |
|---|---|
| `AGENT_SYSTEM_PROMPT.md` | هو الـ system prompt ديال الـ agent. هادا اللي كيتحط فـ الـ LLM وقت التشغيل. فيه الشخصية، القواعد الصارمة، الـ skills، طريقة التفكير، الـ approvals، الذاكرة، والتقارير. |
| `BUILD_PROMPT.md` | برومبت كامل باش تعطيه لـ coding agent (Claude Code / Codex / Cursor…) باش يبني التطبيق: Python backend + React frontend + TUI + sandbox + policy engine. |
| `roe.example.yaml` | نموذج ديال Rules of Engagement. هادا هو "الترخيص" اللي كيحدد شنو مسموح وشنو لا. لازم يتعمّر ويتسدّى قبل أي اختبار. |

## كيفاش تستعملهم

### 1. الـ agent

1. خد `roe.example.yaml`، سميه `config/roe.yaml`، وعمّر:
   - الاسم ديال الـ client والـ authorization reference
   - الـ domains / IP ranges / URLs اللي مسموح
   - الـ exclusions
   - الوقت والـ rate limits
   - الـ contact ديال الطوارئ
2. حط `AGENT_SYSTEM_PROMPT.md` كـ system prompt فـ التطبيق.
3. التطبيق خاصو يقرا `roe.yaml` ويعطي للـ agent غير المعلومات المسموحة.
4. أول مرة، خليه يخدم فـ `SAFE_MODE` (planning فقط) حتى تتأكد أن الـ scope صحيح.

### 2. بناء التطبيق

عطي `BUILD_PROMPT.md` + `AGENT_SYSTEM_PROMPT.md` للـ coding agent، وقول ليه:

> "ابني الـ MVP الأول: RoE → scope guard → approval → sandboxed tool → evidence → finding → report. ما تبدلش ولا تضعف أي control ديال الأمان."

من الأفضل تبدأ بـ vertical slice صغير، ماشي بكل الـ skills من أول يوم.

## قرارات تصميم مهمة

### الأمان كاين فـ الكود، ماشي فـ البرومبت

البرومبت وحدو ما كافيش. أي agent عندو terminal وصلاحية admin، خاصو:

- **Policy engine** خارج الـ LLM، كيرفض أي action ماشي فـ الـ scope
- **Scope guard** فـ مستوى الشبكة: DNS، CIDR، redirects، IPv6، metadata endpoints
- **Approval broker**: approval واحد لكل action، single-use، كيتسالى
- **Sandbox**: container/VM، ماشي الـ host مباشرة
- **Kill switch**: كيوقف كلشي فـ أقل من ثانية
- **Audit log** append-only + hash chain

إلا كان الـ agent كيعتمد غير على "أنا متأكد أن هادا فـ الـ scope"، راه خطر. الـ scope خاصو يتفحص فـ الكود قبل كل command.

### "100% ما بقات حتى ثغرة" — مستحيل تتحقق

ما كاينش طريقة تثبت أن نظام فيه صفر ثغرات. اللي ممكن هو **closure within scope**:

- **Gate 1 — Coverage:** كل اختبار مطلوب تدار، ولا مكتوب علاش N/A
- **Gate 2 — Validation:** كل finding تعاود مرتين بطرق مختلفة، ومعاه evidence
- **Gate 3 — Clean sweep:** إعادة كاملة بأدوات/wordlists مختلفة، صفر findings جديدة
- **Gate 4 — Regression & review:** إعادة اختبار كل findings + مراجعة مستقلة + sweep أخير

أي finding جديدة كترجعك لـ Gate 3 و 4. التقرير ما كيقولش "ما كاين حتى ثغرة"، كيقول:

> "No verified findings within the agreed scope and methodology as of <date>."

هادشي هو اللي كيحميك قانونياً ومهنياً. الادعاء ديال "100% secure" كيضر أكثر مما كينفع.

### Terminal + React

طلبتي جوج: terminal UI و React. الحل العملي:

- **TUI** بـ Textual: هي الواجهة الأساسية، خدامة فـ SSH وفـ أي terminal.
- **React** محلي (`127.0.0.1` فقط) فيه dashboard + terminal مدمج بـ xterm.js.

إلا بغيتي terminal فقط بلا React، التطبيق كيبقى خدام؛ React كيبقى اختياري. أما إلا بغيتي React هو الأساس، خاصك تعرف أنه ماشي "terminal-only" حرفياً.

### الذاكرة على نمط Hermes

الذاكرة مقسمة لـ:

- **Working**: context ديال الجلسة الحالية
- **Episodic**: runs، قرارات، approvals، timeline
- **Semantic**: assets، findings، علاقات، embeddings
- **Procedural**: skills و lessons learned

كل record مرتبط بـ `engagement_id`، وفيه confidence و sensitivity. الأسرار ما كيتخزنوش plaintext. الذاكرة عمرها ما كتعطي authorization — الـ scope كيتفحص كل مرة.

إلا "Hermes" عندو API أو storage خاص، الـ build prompt فيه adapter interface باش تربطو بلا ما تبدل الـ agent.

### Windows / Linux و admin/sudo

- Windows: UAC prompt، ما كاينش تخزين ديال الباسورد
- Linux: sudo بتأكيد صريح، ما كاينش `NOPASSWD`
- يفضل تشغل الـ agent فـ VM مخصصة، ماشي على الـ host ديالك
- أي action فيها كتابة خاصها snapshot/rollback

### الاسم

درت `JANUS` كاسم مؤقت (الإله الروماني اللي كيشوف جوج جهات: attack و defense). تبديلو ساهل: بدل `AGENT_NAME` فـ الإعدادات والبرومبت.

## قبل ما تبدأ — قانونياً

هاد الـ agent مسموح غير على:

- الأنظمة اللي كتملكها، أو
- الأنظمة اللي عندك ترخيص مكتوب وموقّع باش تختبرها.

بلا ترخيص، الاختبار ديال أي نظام ماشي ديالك هو جريمة فـ المغرب وفـ معظم الدول. الـ prompt كيحاول يمنع هادشي تقنياً، ولكن المسؤولية القانونية عليك أنت.

## الخطوات الجاية

1. عمّر `roe.yaml` وحدد الـ scope بدقة.
2. جرب الـ system prompt مع نموذج LLM فـ `SAFE_MODE`.
3. أعطي `BUILD_PROMPT.md` للـ coding agent وابدا بالـ vertical slice.
4. اختبر الـ scope guard و kill switch قبل أي أداة هجومية.
5. زيد الـ skills واحدة بواحدة، مع tests.

## ملفات مرتبطة

- `AGENT_SYSTEM_PROMPT.md` — السلوك ديال الـ agent
- `BUILD_PROMPT.md` — البنية والتطبيق
- `roe.example.yaml` — نموذج الترخيص
