# AI Review Automation

MVP local dành cho một biên tập viên. Nhập chủ đề, lưu nguồn và storyboard, dựng preview, xem kết quả QC và duyệt thủ công. Các thao tác biên tập và trạng thái được lưu trong SQLite WAL. Mỗi lượt dựng có thư mục riêng.

## Chạy trên máy cá nhân

Cần Python 3.11+, FFmpeg có libass/libx264, ffprobe và eSpeak NG có giọng vi. Dùng font DejaVu Sans hoặc font hệ thống hỗ trợ tiếng Việt. Trên Windows thêm thư mục executable vào PATH hoặc đặt đường dẫn eSpeak NG bằng ESPEAK_BIN.

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
python -m uvicorn factory.app:app --host 127.0.0.1 --port 8000
```

Trên Windows, chạy `.\scripts\Start-Factory.ps1`. Script tạo `.venv` nếu thiếu, cài Python dependencies vào đúng môi trường, kiểm tra import, cài dependencies frontend, build và mở server. Python 3.12 và Node.js cần được cài trước. Nếu vừa pull mà vẫn thấy UI cũ, dừng server và build lại frontend.

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

Test dựng dùng FFmpeg thật và âm thanh mock. Tệp nguồn trong test là fixture, không đại diện cho kiểm chứng Ollama thực tế. POST render trả 202 và đưa job vào hàng đợi SQLite. Worker chạy một render tại một thời điểm. Nếu tiến trình chết, lease hết hạn sau 30 giây và job chuyển FAILED khi server hoạt động lại; bấm Render để thử lại, tối đa ba lần trước khi cần lưu lại nội dung. Không chỉnh SQLite bằng tay. Nguồn và storyboard đã lưu vẫn dùng được. Thư mục workspace lưu bản dựng cũ và cần được quản lý dung lượng thủ công.

QC hiện kiểm tra cấu trúc trích dẫn, khoảng thời lượng, demo/quyền đã xác nhận, voice mock và trạng thái rà soát disclosure. Biên tập viên chịu trách nhiệm đối chiếu claim và kiểm tra clip trước khi xác nhận. Có kiểm tra đoạn đen và audio gần như im lặng. Chưa có detector clipping, nội dung trùng lặp theo ngữ nghĩa hoặc đánh giá license độc lập.

## Phạm vi còn thiếu (chưa hoàn thiện toàn bộ sản phẩm)

- Mở rộng hai feed RSS chính thức hiện có thành tìm kiếm đa nguồn, đối chiếu claim và tín hiệu nhu cầu có thật.
- Thêm resume theo cảnh và phân loại lỗi chi tiết trên hàng đợi đã có lease/cancel/retry. Bổ sung adapter TTS và OpenAI/Anthropic, kiểm thử có credentials.
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

### Tải asset thực vật từ Poly Haven

Từ thư mục gốc, chạy `python scripts/fetch_botanical_assets.py` trước khi
`npm run build` trong frontend. Script tìm tối đa năm ứng viên mỗi nhóm,
chọn glTF 1K, xác minh MD5 và đóng gói các dependency vào GLB. Tổng ngân
sách là 12 MB, tối đa 4 MB mỗi nhóm. Manifest ghi SHA-256 và giấy phép CC0.
Frontend hiện credit Powered by Poly Haven khi có asset được nạp.
Nếu mạng hoặc asset lỗi, scene vẫn sử dụng hình học dự phòng.

## Cập nhật độ ổn định và nguồn nghiên cứu

- Trend Discovery đọc các feed chính thức OpenAI/Google AI, lưu snapshot vào `workspace/research`. Có lọc từ khóa trong feed, chưa phải công cụ tìm kiếm web tổng quát. Mọi claim mới là UNVERIFIED; điểm mới chỉ là heuristic theo ngày đăng, không phải lượng tìm kiếm.
- Research có trạng thái claim và giải thích xác minh. QC yêu cầu claim được biên tập viên xác nhận VERIFIED kèm giải thích.
- Settings lưu model Ollama, giọng Việt, tốc độ/âm lượng và encoder vào `workspace/settings.json`. Cấu hình được chụp cho mỗi render. Nút nghe thử sử dụng giọng thật đã lưu. Edge TTS được cài cùng requirements; eSpeak NG cần executable trên PATH.
- Render tiếp tục khi đóng/tải lại trình duyệt. Giao diện nhớ dự án/tab và theo dõi trạng thái; thay đổi chưa lưu có cảnh báo khi đóng trang.
- Schema v3 thêm `render_queue`, `audit` và `media_assets`. Bản duyệt cũ chưa có checksum được lưu trong lịch sử và yêu cầu dựng/duyệt lại. Trước nâng cấp database đã có, ứng dụng sao lưu SQLite bằng backup API vào `workspace/backups`. Không xóa media cũ.
- Approval so khớp SHA-256 của MP4, bộ artifact, metadata và nội dung nghiên cứu/storyboard. Artifact bị sửa hoặc thiếu phải dựng lại. Lịch sử thao tác hiển thị trong dự án.
- Khi dừng server đột ngột, có thể cần chờ tối đa khoảng 30 giây sau lần heartbeat cuối trước khi job được phục hồi. File tạm trong thư mục render gián đoạn chưa tự xóa; không được công bố như bản dựng hoàn tất.

Chạy một server `Start-Factory.ps1` từ thư mục repo; mở http://127.0.0.1:8000.
Xem [sổ triển khai](docs/IMPLEMENTATION_LEDGER.md) để biết yêu cầu đã kiểm tra, phần còn thiếu và bước tiếp theo. YouTube OAuth/upload và analytics chưa được triển khai; không có video nào được tự đăng.

### Media và viết lại từng cảnh

Trong tab **Media**, nhập MP4/WebM/WAV/MP3/PNG/JPEG (tối đa 100 MB), khai báo nguồn và giấy phép, rồi xác nhận quyền thương mại. Server kiểm tra signature và FFprobe, giữ SHA-256 và tránh trùng tệp trong cùng dự án. Media có URL phạm vi dự án; tệp hỏng hoặc quá lớn bị từ chối.

Chọn **Chọn làm bằng chứng demo** trên video, nhập kịch bản kiểm thử, kết quả quan sát và URL sản phẩm. Chỉ xác nhận khi đây là bản ghi thực tế bạn đã xem. Ứng dụng tạo bản sao riêng của video để chỉnh thư viện không phá bằng chứng. Cảnh storyboard phải chọn hình ảnh **Demo** để renderer sử dụng footage.

Sau khi lưu nghiên cứu/kịch bản, nút **Viết lại cảnh bằng Ollama** tạo đề xuất cho riêng cảnh đó, không tự lưu và không thay các cảnh còn lại. Kiểm tra nội dung rồi bấm Lưu. Chưa có kiểm thử live Ollama trong môi trường bàn giao.
