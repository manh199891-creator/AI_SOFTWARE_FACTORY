# Dual-Agent Phase Checkpoint and Convergence Control — Spec

## Goal

Ngăn Antigravity và Codex lặp vô hạn theo chu kỳ sửa–review, đồng thời cho phép Antigravity chạy liên tục trong phạm vi đã duyệt và báo chính xác tiến độ theo phase/task trước khi Codex review.

## Evidence from the Automatic Formwork case

- Task `automatic_formwork_mvp` đã tiêu hết failure budget `3/3` và dừng ở `BLOCKED_HANDOFF`.
- Mỗi snapshot có thay đổi nên duplicate-snapshot guard không chặn; Codex review toàn bộ artifact và tìm thêm các mâu thuẫn mới sau mỗi lần sửa cục bộ.
- Runtime active tại `E:\Antigravity\RevitAddinSolution\.agents\runtime` khác hash với source tại `E:\AI_SOFTWARE_FACTORY`.
- Project profile active đặt `auto_fix: true` và không có convergence flags. Profile Factory đặt `auto_fix: false`, `convergence_shadow: true`.
- `scripts/sync_dual_agent_pipeline.ps1` chưa deploy `convergence_pipeline.py`; đồng thời mặc định không cập nhật profile đã tồn tại. Vì vậy guard mới có thể không tới runtime active.
- `pipeline_status.json` có thể giữ run cũ trong khi `review_run.json` và task context đã sang run mới; UI phải fallback giữa nhiều nguồn trạng thái.
- Factory đã có finding ledger, `claim-fix`, convergence scoring và failure budget, nhưng chưa có contract bắt buộc để Anti báo phase/task progress và tuyên bố `ready_for_codex` bằng evidence có schema.

## Scope

### In scope

1. Một nguồn trạng thái authoritative cho toàn pipeline.
2. Durable counter theo lifecycle phase; không reset chỉ vì gọi lại command.
3. Writer checkpoint contract để Anti báo phase, task hiện tại, evidence và readiness cho Codex.
4. Hai execution policy:
   - `checkpointed` mặc định: Anti xử lý trọn một finding batch rồi trả quyền điều phối cho harness.
   - `continuous`: Anti chạy hết các task được phép trong phase hiện tại, ghi checkpoint sau mỗi task; Codex chỉ được gọi tại review boundary.
5. Finding closure gate: không review lại cho đến khi mọi finding trong batch có claim/evidence hoặc được đánh dấu blocked rõ ràng.
6. Convergence/no-progress gate bắt buộc cho plan và code.
7. Runtime/profile deployment integrity check và migration an toàn.
8. UI/status output hiển thị Anti đang ở phase/task nào và vì sao Codex đang chờ/chạy/dừng.

### Out of scope

- Cho Anti và Codex cùng ghi vào một worktree.
- Cho Anti tự quyết định PASS hoặc tự đóng finding mà không có Codex verification.
- Tự động chuyển sang release/deploy khi chưa có phase gate PASS.
- Thay đổi logic nghiệp vụ Automatic Formwork.

## Proposed architecture

### 1. Authoritative pipeline state

Nâng state contract lên version mới và bắt buộc mọi transition ghi atomically vào `pipeline_status.json`. Các file review/report là evidence, không được dùng như nguồn trạng thái cạnh tranh.

State tối thiểu gồm:

- `task_id`, `mode`, `lifecycle_phase`;
- `status`, `terminal`, `reason_code`, `next_action`;
- `run_id`, `snapshot_hash`, `previous_snapshot_hash`;
- `writer_checkpoint_id`, `writer_status`;
- `plan_task_current`, `plan_task_total`;
- `phase_review_count`, `failure_budget_remaining`;
- `ready_for_codex`, `updated_at`.

`dual_status.ps1` chỉ đọc authority hợp lệ. Nếu authority lệch run/snapshot thì trả `STATE_DESYNC`, không tự suy diễn rằng review đang chạy.

### 2. Writer checkpoint contract

Thêm command do harness sở hữu, ví dụ `writer-checkpoint`. Anti không ghi trực tiếp `.agent/state/**`.

Checkpoint payload gồm:

- phase và task index/total;
- `IN_PROGRESS`, `TASK_COMPLETE`, `PHASE_COMPLETE`, `BLOCKED`;
- changed files và snapshot hash;
- checks đã chạy và kết quả;
- finding IDs đã claim cùng evidence;
- remaining risks/blockers;
- falsifiable retry hypothesis;
- `ready_for_codex`.

Harness chỉ chấp nhận `ready_for_codex=true` khi snapshot đã đổi, scope hợp lệ, checks bắt buộc pass và toàn bộ finding hiện tại có resolution evidence.

### 3. Execution policies

#### Checkpointed — mặc định

`Codex FAIL → NEEDS_FIX → Anti sửa toàn bộ finding batch → writer-checkpoint → harness validate → Codex review một lần`.

Anti không được gọi Codex hoặc gọi lại dual pipeline. Harness là chủ sở hữu duy nhất của review scheduling.

#### Continuous — opt-in

Anti được chạy tuần tự toàn bộ task còn lại của phase đã approve. Sau mỗi plan task, Anti phải ghi checkpoint và test evidence. Harness không gọi Codex ở mỗi task trừ khi task được đánh dấu `review_boundary=true`, có P0/P1 blocker, scope thay đổi hoặc contract regression.

Review boundary mặc định:

- kết thúc spec/research;
- kết thúc plan artifacts;
- sau mỗi implementation milestone đã khai báo trong plan;
- code-complete;
- release gate.

Continuous không cho phép vượt phase: plan PASS mới mở code; code PASS mới mở release.

### 4. Durable convergence guard

- `phase_review_count` được lưu theo `task_id + phase`, không reset giữa các lần gọi CLI.
- Hai changed snapshots liên tiếp có `net_closure <= 0` → `NO_PROGRESS` và human architecture checkpoint.
- Cùng finding family tái xuất hiện → `REGRESSED`, không tính là tiến triển.
- Mở finding mới nhiều hơn finding đã verify-resolved → không tự retry.
- Review ceiling mặc định: 2 review/finding batch và 6 review/phase; vượt ngưỡng → terminal handoff.
- Failure budget chỉ được mở lại khi có snapshot mới, checkpoint hợp lệ và hypothesis mới có thể kiểm chứng.

### 5. Deployment integrity

- Sync toàn bộ dependency runtime, bao gồm `convergence_pipeline.py`.
- Thêm runtime capability/version manifest và hash verification sau sync.
- Tách profile thành phần project-specific và pipeline-managed; cập nhật pipeline-managed fields không cần ghi đè build/test command của dự án.
- `doctor` trả `RUNTIME_DRIFT`, `PROFILE_DRIFT` hoặc `MISSING_RUNTIME_MODULE` và chặn orchestration trước khi chạy review.
- Sync phải chạy import smoke test và status-contract smoke test trên từng target.

## Required status messages

Anti phải luôn có thể báo theo format máy đọc được và format người đọc được:

```text
ANTI_PHASE: PLAN
ANTI_PROGRESS: 8/13
ANTI_STATUS: IN_PROGRESS
LAST_CHECKPOINT: <checkpoint-id>
READY_FOR_CODEX: NO
NEXT_ACTION: Continue Task 9
```

Khi sẵn sàng review:

```text
ANTI_PHASE: PLAN
ANTI_PROGRESS: 13/13
ANTI_STATUS: PHASE_COMPLETE
READY_FOR_CODEX: YES
CODEX_STATUS: NOT_STARTED
NEXT_ACTION: Harness validates checkpoint, then starts one review
```

## Acceptance criteria

1. Retry cùng snapshot hoặc thiếu checkpoint không khởi chạy Codex.
2. Gọi lại CLI không reset phase review count hay failure budget.
3. Anti continuous hoàn thành nhiều task nhưng không vượt phase gate.
4. UI/status cho biết chính xác phase, task index, writer status và Codex status.
5. `pipeline_status.json`, `review_run.json` và report không thể hiển thị hai run authoritative khác nhau; desync phải thành lỗi rõ ràng.
6. Hai vòng không có net closure dừng ở `NO_PROGRESS`.
7. Sync target thiếu module hoặc profile drift bị doctor chặn trước review.
8. Regression tests bao phủ checkpointed, continuous, crash/resume, stale state, profile drift và review ceiling.

## Open questions for approval

1. Chọn `checkpointed` làm mặc định và `continuous` chỉ bật theo task có đúng ý người dùng không?
2. Với code phase, review boundary nên theo milestone trong plan hay cố định sau mỗi 3 task?
3. Khi Anti báo `BLOCKED`, pipeline dừng chờ người dùng hay cho phép Codex review một phần để tư vấn?

