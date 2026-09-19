"""把演示视频转成 GIF（README 里放 GIF 比放 mp4 更直观，能在页面上自动播放）。

为什么单独写个脚本：GitHub 的 README 只能内联渲染图片，`<video>` 标签会被过滤，
所以放一段 GIF 是最省事、助教点开就能看到动画的做法。

依赖（只在需要重新生成 GIF 时才装，游戏本身不需要）：
    pip install imageio-ffmpeg

用法：
    python make_demo_gif.py                                      # 用默认参数
    python make_demo_gif.py --preset long                        # 完整 15 秒版
    python make_demo_gif.py --width 720 --seconds 9 --out demo/x.gif

处理流程：
  1. 先裁掉录屏里的窗口标题栏和黑边（crop_top / crop_bottom），
     否则这些和游戏无关的部分会占掉画面高度，游戏内容被动缩小；
  2. 按目标宽度等比缩放（lanczos）；
  3. 抽帧到目标帧率（30fps 全保留会让文件暴涨）；
  4. 叠加分段中文小标题，说明当前在演示什么；
  5. 用 ffmpeg 两遍调色板（palettegen + paletteuse）而不是简单量化，
     否则游戏的渐变背景会出现明显的色带。

GIF 体积 ≈ 尺寸 × 帧率 × 时长，太大就调小 --width / --fps / --seconds。
"""
import argparse
import os
import subprocess
import sys

import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "demo", "demo.mp4")

FONT = "C\\:/Windows/Fonts/msyh.ttc"   # 微软雅黑，ffmpeg 的字体路径要转义冒号

# 录屏里上下要去掉的部分（像素）：上方是窗口标题栏+菜单，下方是一点黑边
CROP_TOP = 46
CROP_BOTTOM = 4

# 每个时间段的说明文字：(起始秒, 结束秒, 文字)
#
# 注意：这些文字必须和录像里真实发生的画面对应，不能凭想象写。
# 本录像（demo/demo.mp4）从头到尾是"随机·困难"一局的中后段：
# 开局 25 个箭头、计时器已经在 01:12，结尾清到 0 个箭头，
# 里面并没有开始界面、选关界面和通关结算画面，所以这里不写它们。
CAPTIONS = [
    (0.0, 2.0, "随机·困难关卡：开局 25 个箭头"),
    (2.0, 3.6, "使用自动求解逐步清空棋盘"),
    (3.6, 12.4, "点击后沿自身方向飞出棋盘"),
    (12.4, 99.0, "剩余箭头清零"),
]

# 预设：(输出文件, 宽, 帧率, 时长秒数, 是否加小标题)
PRESETS = {
    # README 里实际展示的版本（整段录像 15 秒）
    "default": ("demo/demo.gif", 640, 12, None, True),
    # 追求小体积：只取开头 9 秒、不加字幕
    "small": ("demo/demo-small.gif", 480, 10, 9.0, False),
}


def build_filter(width, fps, seconds, captions, crop_top, crop_bottom):
    """拼出 filter_complex：裁剪 → 缩放 → 抽帧 → 小标题 → 两遍调色板。"""
    chain = []
    if crop_top or crop_bottom:
        # 高度按比例留出上下要裁掉的部分，宽度保持全宽
        chain.append(f"crop=iw:ih-{crop_top + crop_bottom}:0:{crop_top}")
    chain.append(f"scale={width}:-1:flags=lanczos")
    chain.append(f"fps={fps}")
    if seconds:
        chain.append(f"trim=duration={seconds}")
    if captions:
        for start, end, text in CAPTIONS:
            chain.append(
                f"drawtext=fontfile='{FONT}':text='{text}':"
                f"x=(w-text_w)/2:y=h-th-16:fontsize=24:fontcolor=white:"
                f"box=1:boxcolor=black@0.55:boxborderw=10:"
                f"enable='between(t,{start},{end})'")
    chain.append("setpts=PTS-STARTPTS")
    scaled = ",".join(chain)
    return (f"[0:v]{scaled},split[frames][palette_src];"
            f"[palette_src]palettegen=max_colors=256:stats_mode=diff[palette];"
            f"[frames][palette]paletteuse=dither=sierra2_4a:diff_mode=rectangle")


def convert(src, dst, width, fps, seconds, captions,
            crop_top=CROP_TOP, crop_bottom=CROP_BOTTOM):
    """跑一次转换，返回 (是否成功, 输出体积字节)。"""
    if not os.path.exists(src):
        print(f"找不到源视频：{src}")
        return False, 0
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    graph = build_filter(width, fps, seconds, captions, crop_top, crop_bottom)
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
           "-i", src, "-filter_complex", graph, "-loop", "0", dst]
    print(f"转换中：{os.path.basename(dst)}  宽={width}  {fps}fps  "
          f"时长={seconds or '完整'}  小标题={'有' if captions else '无'}")
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print("转换失败：")
        print(result.stderr)
        return False, 0
    return True, os.path.getsize(dst)


def main():
    parser = argparse.ArgumentParser(description="把演示视频转成 GIF")
    parser.add_argument("--preset", choices=sorted(PRESETS), default="default",
                        help="用预设参数（默认 default）")
    parser.add_argument("--width", type=int, help="输出宽度，高度按比例")
    parser.add_argument("--fps", type=int, help="输出帧率")
    parser.add_argument("--seconds", type=float,
                        help="只取视频开头的这么多秒；不填表示整段")
    parser.add_argument("--out", help="输出文件路径")
    parser.add_argument("--no-caption", action="store_true", help="不叠加小标题")
    parser.add_argument("--src", default=SRC, help="源视频路径")
    args = parser.parse_args()

    out, width, fps, seconds, captions = PRESETS[args.preset]
    if args.width:
        width = args.width
    if args.fps:
        fps = args.fps
    if args.seconds is not None:
        seconds = args.seconds
    if args.no_caption:
        captions = False
    dst = os.path.join(HERE, args.out or out)

    ok, size = convert(args.src, dst, width, fps, seconds, captions)
    if not ok:
        return 1
    # 读回真实尺寸，确认裁剪和缩放符合预期
    try:
        from PIL import Image
        with Image.open(dst) as im:
            dims = f"{im.size[0]}x{im.size[1]}，{im.n_frames} 帧"
    except Exception:
        dims = "（未安装 Pillow，跳过尺寸检查）"
    print(f"完成：{os.path.relpath(dst, HERE)}")
    print(f"  {dims}")
    print(f"  体积 {size / 1024:.0f} KB（GitHub 单文件建议 < 10 MB）")
    if size > 10 * 1024 * 1024:
        print("  提示：超过 10MB，建议调小 --width / --fps / --seconds。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
