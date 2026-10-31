# CityDraw – máy làm video "vẽ thành phố" cho YouTube

Mỗi video là **1 thành phố**, theo đúng kịch bản:

1. **Hook (0–2.6s):** tranh thành phố đã tô màu hoàn chỉnh, zoom nhẹ + tên thành phố.
2. **Tua ngược (1.6s):** tranh "rewind" thật nhanh, màu biến mất → nét biến mất → **về giấy trắng** (có hiệu ứng băng tua ⏪ + tiếng whoosh).
3. **Vẽ nét (mặc định 40s):** cây bút chì hiện trên màn hình, vẽ từng nét dạng **tua nhanh** (huy hiệu ⏩ x16), công trình biểu tượng được vẽ trước, rồi nhà cửa, rồi mây/mặt trời.
4. **Tô màu (mặc định 40s):** bút dạ (marker) đổi màu theo từng vùng, tô qua lại như người thật.
5. **Kết (4s):** bút rời khung, hiện tên thành phố + câu kêu gọi ("Which city next?").

Âm thanh (tiếng bút chì sột soạt, tiếng bút dạ, tiếng tua) được tự tổng hợp – không lo bản quyền. Có thể trộn thêm nhạc nền của bạn.

## Cài đặt

```bash
sudo apt install ffmpeg            # nếu chưa có
pip install -r requirements.txt
```

## Dùng

```bash
python make_video.py --list                         # xem các thành phố có sẵn
python make_video.py --city paris                   # video ngang 1920x1080 → output/paris.mp4
python make_video.py --city hanoi --short           # Shorts dọc 1080x1920
python make_video.py --city tokyo --draw 60 --color 60 --music nhac.mp3
python make_video.py --city london --seed 99        # đổi bố cục nhà cửa ngẫu nhiên
```

### Dùng tranh của chính bạn (khuyên dùng để có chất lượng cao nhất)

Công cụ nhận **bất kỳ tranh thành phố đã tô màu có viền đen rõ** (tự vẽ, mua, hoặc tạo bằng AI), tự tách nét → cho bút chì vẽ lại → gom vùng theo màu → bút dạ tô lại từng màu:

```bash
python make_video.py --image tranh_roma.png --title "ROMA" --subtitle "Italia" --outro "Which city next?"
```

Mẹo cho tranh đầu vào: phong cách *coloring book / line art*, **viền đen dày, màu phẳng**, nền không quá chi tiết. Prompt AI gợi ý:

> `flat colored illustration of Rome skyline with Colosseum, thick clean black outlines, coloring book style, simple flat colors, no shading, no text, 16:9`

Tùy chọn hữu ích: `--colors 12` (số màu bút dạ), `--short`, `--draw/--color` (số giây), `--no-badge`, `--no-sfx`.

## Thành phố có sẵn

| key | Thành phố | Biểu tượng |
|---|---|---|
| `paris` | Paris | Tháp Eiffel, nhà thờ mái vòm, sông Seine, nhà mái Mansard |
| `london` | London | Tháp đồng hồ, vòng quay, nhà gạch đỏ |
| `tokyo` | Tokyo | Núi Phú Sĩ, chùa 5 tầng, tháp đỏ |
| `hanoi` | Hà Nội | Tháp trên đảo giữa hồ, nhà ống nhiều màu, chùa |

Thêm thành phố mới: thêm 1 mục vào `CITIES` trong `citydraw/cities.py` (bảng màu, kiểu mái, mặt đất `river/lake/street`, danh sách landmark). Landmark có sẵn: `eiffel`, `clock_tower`, `pagoda`, `mountain`, `ferris_wheel`, `dome`, `turtle_tower`.

## Cấu trúc

```
make_video.py           CLI
citydraw/engine.py      renderer: mask lộ nét, bút chì/bút dạ, hook, tua ngược, ffmpeg
citydraw/planning.py    đường tô qua-lại, cắt nét bị che, sắp xếp nét
citydraw/procedural.py  dựng cảnh vẽ tay (rung nét, texture bút dạ, giấy)
citydraw/cities.py      landmark + cấu hình từng thành phố
citydraw/from_image.py  chế độ nhập tranh có sẵn
citydraw/audio.py       âm thanh tổng hợp
assets/fonts/           Baloo 2 + Patrick Hand (SIL OFL, hỗ trợ tiếng Việt)
```

## Gợi ý vận hành kênh

- **Hai định dạng từ 1 thành phố:** bản ngang 60–90s (hoặc kéo `--draw 180 --color 180` thành video thư giãn 6–7 phút) + bản `--short` 45s cho Shorts. Shorts kéo người xem về video dài.
- **Tiêu đề:** `Drawing PARIS in 60 seconds 🗼 | Satisfying Timelapse` / `Vẽ HÀ NỘI từ giấy trắng ✏️`. Thumbnail = khung hình hook (tranh màu) + một nửa là nét chì trắng đen.
- **Hook 2 giây đầu là sống còn:** giữ tranh màu thật rực, tên thành phố to. Có thể đặt câu hỏi ở outro ("Comment the next city!") để lấy bình luận → chọn thành phố kế tiếp theo bình luận.
- **Series:** "Thủ đô châu Á", "Thành phố Việt Nam" (Đà Nẵng – Cầu Rồng, Huế – Kỳ Đài, TP.HCM – Landmark 81 / Bưu điện…), "Kỳ quan thế giới".
- **Không lời thoại** → khán giả toàn cầu; chỉ cần đổi `--title/--subtitle`.

---

# Phiên bản 3D – thành phố pop-up (`city3d/`)

Cùng kịch bản kênh, nhưng toàn bộ dựng 3D bằng three.js:

1. **Hook:** mô hình thành phố 3D hoàn chỉnh đứng trên tờ giấy, camera bay vòng quanh + tên thành phố.
2. **Tua ngược ⏪:** nhà gập xuống, mất màu, mất nét → **giấy trắng**.
3. **Vẽ:** bút chì 3D (có bóng đổ trên giấy) vẽ nét các tấm pop-up đang nằm phẳng, tua nhanh ⏩.
4. **Tô màu:** bút dạ 3D đổi màu theo từng mảng, tô qua lại.
5. **Pop-up:** từng mảng **bật đứng dậy** như sách pop-up (có tiếng giấy "phựt"), trời gập lên thành phông nền, camera hạ xuống và bay vòng quanh mô hình 3D, hiện tên thành phố.

```bash
cd city3d
npm install                 # three.js (+ playwright nếu máy chưa có)
npx playwright install chromium   # chỉ cần nếu máy chưa có Chromium cho Playwright
node render.js --city paris                 # 9:16 (mặc định) → output/paris_3d_short.mp4
node render.js --city hanoi --wide          # 16:9 ngang 1920x1080
node render.js --city tokyo --draw 40 --color 40 --orbit 10 --music nhac.mp3
```

Tùy chọn: `--draw/--color/--pop/--orbit/--hook/--rewind` (giây), `--speed x16` (chữ trên huy hiệu), `--music`, `--w/--h`.
Xem nhanh bản nháp: `--w 960 --h 540 --every 10` (chỉ render 1/10 khung hình).

Thành phố 3D có sẵn: `newyork` (bản "cả thành phố": 4 landmark + cầu Brooklyn + ~45 tòa nhà, ~2 phút 15 giây), `paris`, `london`, `tokyo`, `hanoi` — sửa/thêm trong `city3d/cities.js`
(landmark 3D: `eiffel`, `clockTower`, `pagoda`, `mountain`, `ferrisWheel`, `domeChurch`, `turtleTower`, nhà phố tự sinh `rowOfBuildings`).

Thời gian render (CPU, không GPU): khoảng 0.4–0.6 giây/khung hình ở 1080p → video 75 giây mất ~20 phút. Máy có GPU sẽ nhanh hơn nhiều.
