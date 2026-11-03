# AI Review Automation

MVP local dành cho một biên tập viên. Nhập chủ đề, lưu nguồn và storyboard, dựng preview, xem kết quả QC và duyệt thủ công. Các thao tác biên tập và trạng thái được lưu trong SQLite WAL. Mỗi lượt dựng có thư mục riêng.

## Chạy trên máy cá nhân

Cần Python 3.11+, FFmpeg có libass/libx264, ffprobe và eSpeak NG có giọng vi. Dùng font DejaVu Sans hoặc font hệ thống hỗ trợ tiếng Việt. Trên Windows thêm thư mục executable vào PATH hoặc đặt đường dẫn eSpeak NG bằng ESPEAK_BIN.

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn factory.app:app --host 127.0.0.1 --port 8000
```

Mở http://127.0.0.1:8000. Chạy một worker. Cấu hình tùy chọn qua .env dựa trên .env.example. Dùng FACTORY_VOICE=mock cho kiểm thử dựng offline. Audio mock là im lặng và bị chặn tại QC.

## Từ chủ đề đến MP4

1. Tạo dự án và chọn Shorts hoặc video dài. Trong trình biên tập JSON, thêm từng nguồn với `url`, `title`, `checked_at` (ISO 8601), `claim`, `evidence` và tùy chọn `published_at`. Đối chiếu từng claim với trích dẫn. Chỉ mục nguồn bắt đầu từ 1.
2. Sửa từng cảnh có `narration`, `caption`, `seconds`, `citations` và `visual_type`. Với giọng thật, renderer dùng thời lượng audio đo bằng ffprobe. Có thể lưu trước nguồn và gọi **Tạo nháp Ollama** khi đã đặt OLLAMA_MODEL. Đọc và lưu nháp đã sửa trước khi dựng.
3. Với demo thực tế, cài thêm Playwright và Chromium. Chỉ ghi hình trên công cụ được phép ghi và dùng thương mại. Phiên đăng nhập ban đầu không ghi hình. Dừng nếu gặp chặn truy cập.

```sh
python -m pip install playwright
python -m playwright install chromium
python -m factory.capture JOB_UUID https://example.com
```

4. Mở http://127.0.0.1:8000/docs và gửi PUT `/jobs/{job}/verification` với `scenario`, `result`, `recording_source`, `commercial_rights: true` sau khi xem recording.webm. Dùng `visual_type: "demo"` ở cảnh phù hợp. Video hiện dùng cùng điểm bắt đầu của clip ở mọi cảnh demo. Dự án thiếu demo vẫn có thể dựng preview và sẽ bị QC chặn.
5. Dựng và xem preview. Bản dựng xuất MP4, thumbnail, SRT, timeline, báo cáo nguồn, manifest và metadata private. Kiểm tra nội dung và xác nhận duyệt trong UI. Mọi chỉnh sửa storyboard hoặc bằng chứng làm mất hiệu lực duyệt trước đó. Bản đã duyệt có thể chuyển thủ công sang YouTube Studio để tiếp tục quy trình xuất bản.

## Kiểm thử và giới hạn

```sh
python -m pytest -q
```

Test dựng dùng FFmpeg thật và âm thanh mock. Tệp nguồn trong test là fixture, không đại diện cho kiểm chứng Ollama thực tế. Nhánh dựng hiện chạy đồng bộ và giới hạn một video tại một thời điểm. Nếu tiến trình chết giữa chừng, dừng server trước khi dùng SQLite đưa job kẹt từ RENDERING về FAILED rồi dựng lại. Nguồn và storyboard đã lưu vẫn dùng được. Thư mục workspace lưu bản dựng cũ và cần được quản lý dung lượng thủ công.

QC hiện kiểm tra cấu trúc trích dẫn, khoảng thời lượng, demo/quyền đã xác nhận, voice mock và trạng thái rà soát disclosure. Biên tập viên chịu trách nhiệm đối chiếu claim và kiểm tra clip trước khi xác nhận. Chưa có detector clipping, silence, nội dung trùng lặp theo ngữ nghĩa hoặc đánh giá license độc lập.

## Milestone tiếp theo

- Thu thập RSS/search API, chuẩn hóa provenance và xếp hạng Top 20 dựa trên tín hiệu có thật.
- Thêm worker có lease, resume theo cảnh, cancel và retry theo loại lỗi. Bổ sung adapter TTS và OpenAI/Anthropic, kiểm thử có credentials.
- Thêm QC kỹ thuật và kiểm tra quyền theo từng asset, rồi kiểm thử video dài và demo sản phẩm thực tế.
- Thêm OAuth, upload private có idempotency, lịch đăng gắn với bản đã duyệt, analytics và affiliate disclosure.

## M0 trên Windows

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
powershell -NoProfile -File .\scripts\Start-Factory.ps1
```

Mở dashboard ở http://127.0.0.1:8000 và kiểm tra http://127.0.0.1:8000/health.
Health trả phiên bản schema, SQLite journal mode và các executable tìm thấy trên PATH.
Việc tìm thấy NVIDIA hoặc Ollama trên PATH chưa xác nhận encoder hoặc model chạy được.
Dùng POST /jobs/{job}/cancel để hủy job trước khi render hoặc sau khi render lỗi.

## M1 smoke test trên Windows

```powershell
powershell -NoProfile -File .\scripts\Setup-Factory.ps1 -EdgeTts
$env:FACTORY_TTS = "edge"
$env:FACTORY_VOICE = "vi-VN-HoaiMyNeural"
.\.venv\Scripts\python.exe -m factory.smoke ".\workspace\M1 tiếng Việt"
.\.venv\Scripts\python.exe -m pytest -q
powershell -NoProfile -File .\scripts\Start-Factory.ps1
```

Edge TTS cần kết nối mạng. Với eSpeak NG đã cài, đặt FACTORY_TTS=espeak và FACTORY_VOICE=vi.
Smoke test yêu cầu thư mục đích mới và ghi video.mp4, subtitles.srt, thumbnail.jpg và technical.json.
FACTORY_ENCODER=cpu buộc dùng libx264. Mặc định renderer thử mã hóa NVENC trước.
API cancel chờ đến checkpoint tiếp theo, tối đa đến khi lệnh con hiện tại hoàn tất hoặc timeout.

### M1.1 — kiểm tra hai định dạng trên Windows

```powershell
powershell -NoProfile -File .\scripts\Setup-Factory.ps1 -EdgeTts
powershell -NoProfile -File .\scripts\Test-M1.ps1 -Listen
```

Mỗi lần chạy tạo thư mục riêng dưới workspace và kiểm tra hai video có giọng Edge TTS.
Xem technical.json để biết encoder và các đoạn hình đen. Dùng -Listen để nghe WAV của cảnh đầu từng định dạng.
NVENC lỗi khởi tạo trong khi encode sẽ thử lại toàn bộ bằng CPU một lần.
API cancel kiểm tra trong lúc tiến trình con chạy và chỉ dừng cây tiến trình của lệnh thuộc render hiện tại.

### M1.2 — kiểm tra độ ổn định MP4

Render ghi concat vào `video.partial.mp4` trong thư mục riêng của lượt chạy.
Sau khi FFmpeg thoát thành công, ffprobe và các kiểm tra kỹ thuật đọc file tạm.
Renderer đổi tên file sang `video.mp4` trên cùng filesystem sau khi hoàn tất.
API chỉ công bố render ID sau khi xử lý xong. Log INFO của `factory.media` ghi
PID, thư mục render chứa job ID, đích lệnh, exit code và thời gian xử lý.

```powershell
powershell -NoProfile -File .\scripts\Setup-Factory.ps1 -EdgeTts
powershell -NoProfile -File .\scripts\Test-M1.ps1 -Listen
```

Xem encoder trong `technical.json` ở mỗi thư mục output và phát lại cả hai MP4
để kiểm tra phụ đề và narration. Smoke test không gửi yêu cầu cancel qua API.

### Studio Phase 2 trên Windows

Chạy từ thư mục repo sau khi đã thiết lập Python venv và FFmpeg.

```powershell
Push-Location frontend
npm ci
npm run build
Pop-Location
.\.venv\Scripts\python.exe -m uvicorn factory.app:app --host 127.0.0.1 --port 8001
```

Mở http://127.0.0.1:8001. FastAPI phục vụ giao diện HTML cũ khi chưa có bản build.
Để phát triển UI, chạy `npm run dev` trong frontend và giữ FastAPI ở port 8001.

Để chạy Playwright, kích hoạt Python venv, vào frontend và chạy
`npx playwright install chromium` rồi `npm run test:e2e`. Test tự mở backend
trên port 8012 với SQLite tạm và audio mock để kiểm tra cổng QC.

Windows Playwright dùng Chrome đã cài theo mặc định. Đặt
`$env:STUDIO_HEADED = "1"` nếu muốn quan sát trực tiếp. Đặt
`$env:STUDIO_CHANNEL = "chromium"` nếu muốn dùng Chromium của Playwright.
Trace, ảnh chụp và thông tin lỗi nằm trong `frontend/test-results`.

### Prototype hành tinh Three.js

Chạy bản build ở port 8001 theo hướng dẫn Studio Phase 2. Hành tinh được tải
riêng, xoay chậm và đổi góc nhìn theo con trỏ. Khi con trỏ rời khung,
camera trở về giữa. WebGL không khả dụng sẽ hiển thị hình minh họa tĩnh.

Scene có hai đối tượng vẽ, một sphere 64 × 40 và 140 điểm sáng. DPR tối đa
1,35, giảm về 1 sau 30 frame liên tiếp chậm hơn 25 ms. Scene dừng vẽ
liên tục khi tab trình duyệt bị ẩn, khung nằm ngoài viewport, có job render,
đang mở Video Studio hoặc hệ điều hành yêu cầu giảm chuyển động.

Kiểm tra trên Windows với Chrome đã cài, từ thư mục repo:

```powershell
.\.venv\Scripts\Activate.ps1
Push-Location frontend
npm ci
npm run build
npx playwright install ffmpeg
$env:STUDIO_HEADED = "1"
npm run test:planet
Pop-Location
```

Playwright tự mở backend test trên port 8012. Ảnh chụp ở hai viewport,
video WebM và trace lỗi nằm trong `frontend/test-results`.
