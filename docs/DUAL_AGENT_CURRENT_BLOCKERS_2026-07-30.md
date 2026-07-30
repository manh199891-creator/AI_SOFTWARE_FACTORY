# Báo cáo vướng mắc Dual Agent và nguy cơ vòng lặp vô tận

- Ngày tổng hợp: 2026-07-30
- Phạm vi: `E:\AI_SOFTWARE_FACTORY`
- Mục tiêu: xác định các khe hở còn lại trước khi cho phép Dual Agent chạy tự động trở lại.

## Kết luận điều hành

Circuit breaker theo số lần Codex trả về `FAIL` đã hoạt động và vượt qua các test hiện có. Tuy nhiên, hệ thống chưa an toàn trước bốn tình huống:

1. Nhiều tiến trình review chạy đồng thời.
2. Gọi trực tiếp các hàm review để bỏ qua governance.
3. Cho phép `MaxCycles > 1` và các đường auto-fix còn tồn tại.
4. Các file trạng thái không đồng nhất nhưng chưa luôn được terminal hóa thành `STATE_DESYNC`.

Vì vậy, chưa nên cho Dual Agent chạy tự động trên task thật cho đến khi các hạng mục P0 trong báo cáo này được đóng và canary thành công.

## Các vướng mắc P0

### 1. Chưa có execution lease chống chạy đồng thời

Hai invocation cùng `task_id + mode` vẫn có thể cùng được cấp quyền và khởi chạy Codex. Khóa hiện tại chủ yếu bảo vệ thao tác ghi counter, chưa khóa toàn bộ vòng đời review.

Các entry point liên quan:

- `review_pipeline.py:1128` — `run_codex_artifact_review()`.
- `review_pipeline.py:1349` — `run_multi_lens_artifact_review()`.
- `review_pipeline.py:868` và `review_pipeline.py:1285` — các vị trí tạo process.

Hậu quả có thể xảy ra:

- Hai runner review cùng một snapshot.
- Báo cáo trùng lặp hoặc ghi đè nhau.
- Counter chỉ được cập nhật sau khi review kết thúc, nên không ngăn được hai process đã khởi chạy.
- Trạng thái `RUNNING`, `REVIEWING` và terminal có thể bị ghi sai thứ tự.

Yêu cầu khắc phục:

- Thêm atomic lease theo `project + task_id + mode`.
- Lease phải chứa owner PID, process start time, invocation token, thời điểm acquire và heartbeat.
- Invocation thứ hai phải thoát với `RUN_ALREADY_ACTIVE`.
- Chỉ release lease sau khi terminal manifest và authoritative status đã được ghi bền vững và có cùng identity.

### 2. `MaxCycles > 1` vẫn được chấp nhận

Parser hiện chỉ ép giá trị tối thiểu là 1:

- `harness.py:899` — `opts["max_cycles"] = max(1, int(...))`.

Sau đó giá trị này được dùng trong các vòng lặp:

- `harness.py:1634`.
- `harness.py:1900`.

Như vậy, production command vẫn có thể chạy nhiều chu kỳ trong cùng một invocation.

Yêu cầu khắc phục:

- Mặc định `MaxCycles=1`.
- Từ chối mọi giá trị lớn hơn 1 với reason code `AUTOMATIC_MULTI_REVIEW_DISABLED`.
- Áp dụng cho cả `research`, `plan`, `code` và `release`.
- Bổ sung test cho wrapper PowerShell và parser Python.

### 3. Các đường auto-fix vẫn còn trong production path

Profile canonical của Navis và Revit đã có `dual_agents.auto_fix=false`. Tuy nhiên, harness vẫn có thể chạy fixer qua `--fix-command`, hoặc kích hoạt lại Antigravity nếu profile bị thay đổi.

Các nhánh liên quan:

- `harness.py:1823` — chạy `fix_command`.
- `harness.py:1830` — chạy Antigravity auto-fixer.
- `harness.py:2047` và `harness.py:2050` — các nhánh tương ứng trong luồng khác.

Rủi ro:

- Chỉ cần profile drift hoặc tham số `--fix-command` là chuỗi `review → fix → review` có thể quay lại.
- Antigravity có thể gọi lại dual pipeline nếu prompt/handoff không được khóa chặt.

Yêu cầu khắc phục:

- Codex `FAIL` chỉ ghi một `FIXER_HANDOFF.json`, trả về `NEEDS_FIX` và kết thúc invocation.
- Loại `fix_command` và Antigravity auto-fix khỏi production review path.
- Chỉ giữ lại fixer runtime cho test cô lập hoặc policy có phê duyệt thủ công rõ ràng.
- Prompt của writer phải cấm gọi Codex, `dual_run`, `dual_orchestrate` và lệnh chuyển phase.

### 4. Trạng thái Revit hiện bị desync

Task `auto_foundation_cleanup_fix`, run `8b580489-ab57-4007-87d0-88c9c4a13f4e` hiện có các trạng thái mâu thuẫn:

| Nguồn | Trạng thái |
|---|---|
| `.agent/state/pipeline_status.json` | `REVIEWED_APPROVED` |
| `.agent/state/review_run.json` | `INFRA_FAIL` |
| `.agent/context/TASK_CONTEXT.json` | `running` |

`REVIEWED_APPROVED` không nằm trong enum của `schemas/pipeline_status.schema.json`. Ngoài ra, `updated_at` trong status cũ hơn sự kiện cuối cùng trong history.

Rủi ro:

- Status reader có thể xem một run hạ tầng thất bại là đã được phê duyệt.
- Runner mới có thể tiếp tục từ state không hợp lệ.
- Manual override đã làm sai authoritative status.

Yêu cầu khắc phục:

- Không resume task Revit này.
- Mọi identity/status mismatch phải được terminal hóa thành `STATE_DESYNC`.
- `pipeline_status.json` hợp schema là authoritative state duy nhất.
- `review_run.json`, task context và Markdown chỉ là evidence; không được dùng là fallback authority.
- Khi desync, không được khởi chạy Codex hoặc fixer.

### 5. Có thể bỏ qua governance bằng direct entry point

`run_codex_artifact_review()` và `run_multi_lens_artifact_review()` chấp nhận `checkpoint_authorization=None`. Việc authorization hiện chủ yếu nằm trong `cmd_dual`, không nằm ngay tại lớp sở hữu thao tác tạo process.

Do đó, script hoặc module khác có thể gọi review trực tiếp mà không qua:

- Durable phase budget.
- Snapshot authorization.
- Execution lease.
- Kiểm tra authoritative state.

Yêu cầu khắc phục:

- Centralize review launch authorization trong `workflow_governance.py`.
- Mọi public production entry point phải yêu cầu authorization hợp lệ.
- Authorization phải bind với task, mode, snapshot, budget counter, invocation và lease.
- Các bypass test phải chứng minh unauthorized call khởi chạy zero process.

## Các vướng mắc P1

### 6. Hạ tầng agent chưa READY

Doctor gần nhất của Navis cho biết:

- Codex: `READY`.
- Antigravity: `AUTH_REQUIRED`.
- Tổng thể: `ready=false`.

Log Revit cũng ghi nhận các lỗi hạ tầng:

- Codex usage/quota limit.
- Model cache không tương thích trường `supports_reasoning_summaries`.
- Review cuối cùng kết thúc `INFRA_FAIL`.

Doctor hiện có ngày 2026-07-22, không phản ánh chính xác runtime tại ngày lập báo cáo.

Hành động cần thiết:

- Đăng nhập Antigravity CLI tương tác.
- Xử lý quyền ghi app-data/log của Antigravity.
- Sửa hoặc cập nhật Codex/model cache.
- Kiểm tra quota trước khi launch review.
- Chạy doctor mới và chỉ tiếp tục khi cả hai runtime đều `READY`.

### 7. Lịch sử cho thấy `NO_PROGRESS` chưa từng chặn bền vững

`NavisAddinSolution/.agent/state/convergence_state.json` có 13 review. Từ review thứ hai trở đi, hệ thống liên tục trả `NO_PROGRESS`, nhưng các snapshot mới vẫn tiếp tục được review.

Đây là bằng chứng rằng convergence controller trước đây chủ yếu ghi nhận quyết định, nhưng không ngăn bền vững invocation tiếp theo.

Navis hiện đã ở `BLOCKED_HANDOFF`, nhưng chưa có canary chứng minh runtime mới không tái diễn sự cố.

### 8. Chưa hoàn tất triển khai containment

Kế hoạch `docs/superpowers/plans/2026-07-22-dual-agent-loop-containment.md` vẫn chưa xác nhận hoàn tất các task.

Các phần còn thiếu hoặc chưa có bằng chứng:

- Concurrent invocation test.
- Direct-entry-point bypass test.
- Test bắt buộc từ chối `MaxCycles > 1`.
- Crash recovery test tại các fault point của lease/review.
- Deployment containment test chuyên biệt.
- Canary Navis trước khi triển khai cùng bundle sang Revit.
- Xác nhận runtime đã deploy có cùng hash với canonical source.

### 9. Tài liệu và cấu hình còn mâu thuẫn

`docs/DUAL_AGENT_AND_EVOLUTION.md` vẫn mô tả trường hợp có thể giữ `auto_fix: true`, trong khi containment yêu cầu production path không được auto-fix.

Profile cũng có `max_reviews_per_phase=6`, trong khi durable content failure circuit breaker dùng giới hạn 3. Hai budget này có mục đích khác nhau nhưng chưa được giải thích rõ, dễ dẫn đến cấu hình sai hoặc manual override.

## Kết quả kiểm thử hiện tại

### Các test đã pass

- `python -m unittest test_dual_loop_guards.py test_runtime_integrity.py test_sync_dual_agent_pipeline.py`
  - 29 test pass.
- `python test_pipeline.py`
  - Toàn bộ test pass.
  - Bao gồm fixture 10 invocation `FAIL`, chỉ cho phép ba content review.
  - Bao gồm durable phase counter và single-use human approval.

### Khoảng trống của test suite

Kết quả xanh hiện tại chưa bao phủ:

- Hai invocation thật cạnh tranh cùng lease.
- Direct call vào các hàm review.
- Bắt buộc từ chối `MaxCycles > 1`.
- Crash sau acquire lease, sau launch, trước terminal write và trước release lease.
- Reconcile state khi authoritative status và evidence có cùng run ID nhưng status mâu thuẫn.
- Canary trên runtime đã deploy thật.

Do đó, test suite hiện tại xác nhận circuit breaker cơ bản, nhưng chưa đủ để kết luận toàn bộ hệ thống không thể lặp vô tận.

## Thứ tự xử lý đề xuất

1. Dừng resume task Revit hiện tại và terminal hóa desync thành `STATE_DESYNC`.
2. Thêm atomic execution lease bao quanh toàn bộ vòng đời review.
3. Bắt buộc authorization ngay trong các hàm có khả năng tạo Codex process.
4. Từ chối mọi `MaxCycles > 1`.
5. Loại `fix_command` và Antigravity auto-fix khỏi production review path.
6. Bổ sung concurrency, bypass, state-desync và crash-recovery tests.
7. Chạy doctor mới; xử lý Antigravity auth, Codex quota và model cache.
8. Build bundle có manifest/hash và validate-only deployment.
9. Canary trên Navis với task dùng một lần.
10. Chỉ deploy cùng bundle sang Revit sau khi Navis canary pass.

## Acceptance gate trước khi chạy lại Dual Agent

- [ ] Mười invocation `FAIL` liên tiếp chỉ tạo tối đa ba content review.
- [ ] Hai invocation đồng thời chỉ tạo đúng một logical review.
- [ ] Invocation thứ hai nhận `RUN_ALREADY_ACTIVE` và không tạo process.
- [ ] Không production command nào chấp nhận `MaxCycles > 1`.
- [ ] Codex `FAIL` không tự chạy fixer.
- [ ] Failed phase không tự chuyển sang phase tiếp theo.
- [ ] Direct review call không có authorization khởi chạy zero process.
- [ ] State mismatch trả `STATE_DESYNC` và khởi chạy zero process.
- [ ] Stale lease chỉ được reconcile khi owner process không còn và heartbeat đã hết hạn.
- [ ] Antigravity và Codex doctor đều `READY`.
- [ ] Navis canary pass trước khi deploy Revit.
- [ ] Runtime đã deploy có hash trùng với containment bundle.
- [ ] Không cò process Codex/Antigravity sau terminal status.

## Tài liệu và bằng chứng liên quan

- `docs/superpowers/plans/2026-07-22-dual-agent-loop-containment.md`.
- `docs/superpowers/plans/2026-07-22-dual-agent-phase-checkpoint-implementation.md`.
- `docs/DUAL_AGENT_AND_EVOLUTION.md`.
- `workflow_governance.py`.
- `convergence_pipeline.py`.
- `review_pipeline.py`.
- `harness.py`.
- `test_dual_loop_guards.py`.
- `test_pipeline.py`.
- `NavisAddinSolution/.agent/state/convergence_state.json`.
- `NavisAddinSolution/.agent/state/pipeline_status.json`.
- `RevitAddinSolution/.agent/state/pipeline_status.json`.
- `RevitAddinSolution/.agent/state/review_run.json`.

