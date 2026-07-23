# HÆ°á»›ng dáº«n sá»­ dá»¥ng Skill `/hermes` (AI Software Factory Auto-Orchestrator)

Skill `/hermes` lÃ  trÃ¡i tim cá»§a há»‡ thá»‘ng **AI Software Factory tá»± Ä‘á»™ng hÃ³a hoÃ n toÃ n**. Thay vÃ¬ báº¡n pháº£i copy-paste prompt cho tá»«ng bÆ°á»›c nhÆ° trÆ°á»›c Ä‘Ã¢y, `/hermes` Ä‘Ã³ng vai trÃ² lÃ  Nháº¡c trÆ°á»Ÿng (Orchestrator) tá»± Ä‘á»™ng gá»i cÃ¡c Subagents vÃ  cháº¡y lá»‡nh, giÃºp báº¡n tiáº¿t kiá»‡m tá»‘i Ä‘a thá»i gian.

DÆ°á»›i Ä‘Ã¢y lÃ  cÃ¡ch sá»­ dá»¥ng:

## CÃ¡ch KÃ­ch Hoáº¡t

Báº¥t cá»© lÃºc nÃ o báº¡n muá»‘n báº¯t Ä‘áº§u má»™t luá»“ng cÃ´ng viá»‡c má»›i trong Factory, chá»‰ cáº§n gÃµ vÃ o chat:
```
/hermes
```
(Hoáº·c cÃ¡c tá»« khÃ³a tÆ°Æ¡ng Ä‘Æ°Æ¡ng nhÆ° `hermes`, `tá»± Ä‘á»™ng triá»ƒn khai`, `auto factory`).

Há»‡ thá»‘ng sáº½ ngay láº­p tá»©c há»i báº¡n **1 cÃ¢u duy nháº¥t**:
> "ÄÃ¢y lÃ  dá»± Ã¡n Má»šI hay task Má»šI cho dá»± Ã¡n CÅ¨?"

TÃ¹y vÃ o cÃ¢u tráº£ lá»i, luá»“ng cÃ´ng viá»‡c sáº½ ráº½ nhÃ¡nh nhÆ° sau:

---

## NhÃ¡nh 1: Dá»± Ã¡n Má»šI hoÃ n toÃ n

Náº¿u báº¡n chá»n **[M] Dá»± Ã¡n má»›i**:

1. **Chuáº©n bá»‹ Spec:** Báº¡n má»Ÿ file `E:\AI_SOFTWARE_FACTORY\PROJECT_ONBOARDING_SPEC.md` vÃ  Ä‘iá»n **Ä‘Ãºng 3 thÃ´ng tin**:
   - TÃªn dá»± Ã¡n (Project Name)
   - BÃ­ danh lá»‡nh (Alias)
   - Ã tÆ°á»Ÿng / Má»¥c tiÃªu dá»± Ã¡n
2. **Setup tá»± Ä‘á»™ng:** Tráº£ lá»i "ok" trong chat. `/hermes` sáº½ tá»± Ä‘á»™ng cháº¡y lá»‡nh setup Ä‘á»ƒ táº¡o toÃ n bá»™ cáº¥u trÃºc thÆ° má»¥c, scaffold cÃ¡c file cáº¥u hÃ¬nh vÃ  `PROJECT_CONTEXT.md` cho dá»± Ã¡n cá»§a báº¡n.
3. **ÄÄƒng kÃ½ Alias:** Sau khi táº¡o xong thÆ° má»¥c, `/hermes` sáº½ cung cáº¥p cho báº¡n má»™t Ä‘oáº¡n mÃ£ ngáº¯n (1 dÃ²ng) Ä‘á»ƒ báº¡n copy paste vÃ o file `harness.py` nháº±m Ä‘Äƒng kÃ½ alias.
4. **Báº¯t Ä‘áº§u Pipeline:** GÃµ "ok" má»™t láº§n ná»¯a Ä‘á»ƒ `/hermes` khá»Ÿi Ä‘á»™ng toÃ n bá»™ tiáº¿n trÃ¬nh 8 bÆ°á»›c.

---

## NhÃ¡nh 2: Task Má»šI cho dá»± Ã¡n CÅ¨

Náº¿u báº¡n chá»n **[C] Task má»›i cho dá»± Ã¡n cÅ©** (vÃ­ dá»¥: RevitAddinSolution, TrendingUpdate...):

1. **Cung cáº¥p yÃªu cáº§u:** Báº¡n chá»‰ cáº§n nÃ³i vá»›i `/hermes`: "Cho dá»± Ã¡n `[alias]`, task lÃ : `[MÃ´ táº£ yÃªu cáº§u/tÃ­nh nÄƒng má»›i]`".
2. **Cáº­p nháº­t Context:** `/hermes` sáº½ tá»± Ä‘á»™ng ghi yÃªu cáº§u cá»§a báº¡n vÃ o `PROJECT_CONTEXT.md` cá»§a dá»± Ã¡n Ä‘Ã³.
3. **Báº¯t Ä‘áº§u Pipeline:** `/hermes` sáº½ tá»± Ä‘á»™ng cháº¡y lá»‡nh status vÃ  khá»Ÿi Ä‘á»™ng tiáº¿n trÃ¬nh 8 bÆ°á»›c.

---

## Tiáº¿n TrÃ¬nh 8 BÆ°á»›c Tá»± Äá»™ng (Äiá»u gÃ¬ xáº£y ra sau cÃ¡nh gÃ ?)

Sau khi qua bÆ°á»›c Khá»Ÿi Ä‘á»™ng, `/hermes` sáº½ tá»± Ä‘á»™ng Ä‘iá»u phá»‘i tiáº¿n trÃ¬nh sau mÃ  **khÃ´ng cáº§n báº¡n can thiá»‡p á»Ÿ giá»¯a**:

*   **BÆ¯á»šC 1 â€” PLANNER:** Gá»i Planner Agent ngáº§m Ä‘á»ƒ láº­p `PLAN.md`, Ä‘á»‹nh nghÄ©a cÃ¡c Phase vÃ  Acceptance Criteria.
*   **BÆ¯á»šC 2 â€” ARCHITECT:** Gá»i Architect Agent ngáº§m Ä‘á»ƒ thiáº¿t káº¿ ká»¹ thuáº­t (`TECHNICAL_DESIGN.md`).
*   **BÆ¯á»šC 3 â€” IMPLEMENTER:** Gá»i Implementer Agent ngáº§m Ä‘á»ƒ viáº¿t code. Sau khi code xong, tá»± Ä‘á»™ng cháº¡y build test.
*   **BÆ¯á»šC 4 â€” QA:** Gá»i QA Agent ngáº§m Ä‘á»ƒ kiá»ƒm thá»­ Acceptance Criteria. Náº¿u cÃ³ lá»—i, tá»± Ä‘á»™ng gá»i **FIXER** tá»‘i Ä‘a 2 láº§n.
*   **BÆ¯á»šC 5 â€” CODEX REVIEW:** Tá»± Ä‘á»™ng cháº¡y review mÃ£ nguá»“n báº±ng AI. Náº¿u cÃ³ lá»—i style/convention, tá»± Ä‘á»™ng gá»i **FIXER** sá»­a lá»—i.
*   **BÆ¯á»šC 6 â€” RELEASE GATE:** Tá»± Ä‘á»™ng cháº¡y táº¥t cáº£ cÃ¡c khÃ¢u kiá»ƒm tra (Build, Tests, Lint, Runtime Validation, Guardrails) Ä‘á»ƒ Ä‘áº£m báº£o cháº¥t lÆ°á»£ng.
*   **BÆ¯á»šC 7 â€” RELEASE AGENT:** Gá»i Release Agent ngáº§m Ä‘á»ƒ tá»•ng há»£p `FINAL_REPORT.md`, `RELEASE_NOTES.md`.
*   **BÆ¯á»šC 8 â€” PROMOTE:** Ghi Ä‘Ã¨ mÃ£ nguá»“n Ä‘Ã£ hoÃ n thiá»‡n vÃ o repository gá»‘c cá»§a báº¡n.

---

## Hai Checkpoint Quan Trá»ng (Báº¡n cáº§n tham gia)

Äá»ƒ Ä‘áº£m báº£o an toÃ n vÃ  Ä‘Ãºng hÆ°á»›ng, `/hermes` chá»‰ dá»«ng láº¡i **Ä‘Ãºng 2 láº§n** Ä‘á»ƒ chá» quyáº¿t Ä‘á»‹nh cá»§a báº¡n:

### ðŸŸ¡ CHECKPOINT 1: Sau BÆ°á»›c 1 (User Approve Plan)

TrÆ°á»›c khi viáº¿t báº¥t ká»³ dÃ²ng code nÃ o (cost cao), `/hermes` sáº½ tÃ³m táº¯t `PLAN.md` vÃ  há»i báº¡n:
> *"Plan cÃ³ há»£p lÃ½ khÃ´ng? [ok / cáº§n chá»‰nh: ...]"*

*   **Náº¿u báº¡n gÃµ 'ok':** Tiáº¿n trÃ¬nh cháº¡y tiáº¿p (Architect, Implementer...).
*   **Náº¿u báº¡n yÃªu cáº§u chá»‰nh sá»­a:** Planner Agent sáº½ Ä‘Æ°á»£c gá»i láº¡i Ä‘á»ƒ sá»­a `PLAN.md` theo Ã½ báº¡n, cho Ä‘áº¿n khi báº¡n 'ok'.

### ðŸŸ¡ CHECKPOINT 2: Sau BÆ°á»›c 7 (User Approve Promote)

Khi code Ä‘Ã£ hoÃ n thiá»‡n vÃ  vÆ°á»£t qua má»i bÃ i test (Release Gate), `/hermes` sáº½ tÃ³m táº¯t `FINAL_REPORT.md` vÃ  há»i báº¡n láº§n cuá»‘i:
> *"Má»i thá»© Ä‘Ã£ sáºµn sÃ ng. Báº¡n cÃ³ muá»‘n Promote code vá» repo gá»‘c khÃ´ng? [promote / dá»«ng]"*

*   **Náº¿u báº¡n gÃµ 'promote':** MÃ£ nguá»“n sáº½ Ä‘Æ°á»£c chÃ©p Ä‘Ã¨ vÃ o repo gá»‘c cá»§a báº¡n. HoÃ n thÃ nh!
*   **Náº¿u báº¡n muá»‘n dá»«ng:** Báº¡n cÃ³ thá»ƒ kiá»ƒm tra source code ká»¹ hÆ¡n, vÃ  cháº¡y lá»‡nh `python harness.py [proj] promote` thá»§ cÃ´ng sau nÃ y.

---

**TÃ³m láº¡i:** Vá»›i `/hermes`, cÃ´ng viá»‡c cá»§a báº¡n chá»‰ cÃ²n lÃ  ÄÆ°a yÃªu cáº§u â†’ Approve Plan â†’ Approve Promote. Pháº§n cÃ²n láº¡i, AI tá»± lo!
