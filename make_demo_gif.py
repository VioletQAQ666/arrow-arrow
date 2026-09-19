"""把演示视频转成 GIF（README 里放 GIF 比放 mp4 更直观，能在页面上自动播放）。

为什么单独写个脚本：GitHub 的 README 只能内联渲染图片，`<video>` 标签会被过滤，
所以放一段短 GIF 是最省事、助教点开就能看到动画的做法。

依赖（只在需要重新生成 GIF 时才装，游戏本身不需要）：
    pip install imageio-ffmpeg

用法：
    python make_demo_gif.py

默认把 demo/demo.mp4 转成 demo/demo.gif：
  - 缩放到宽 640（GIF 太大又糊又慢，缩到 640 后文字仍然清楚）
  - 抽帧到 12fps（30fps 全保留会让文件暴涨，12fps 已足够看清动画）
  - 用 ffmpeg 两遍调色板（palettegen + paletteuse）而不是简单量化，
    否则渐变背景会出现明显的色带
  - 每一段加一行中文小标题，说明当前在演示什么

GIF 体积主要取决于 尺寸 × 帧率 × 时长，太大就调 width/fps 两个参数。
"""
import os
import subprocess
import sys

import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "demo", "demo.mp4")
DST = os.path.join(HERE, "demo", "demo.gif")

# 每个时间段的说明文字：(起始秒, 结束秒, 文字)
CAPTIONS = [
    (0.0, 2.2, "开始界面"),
    (2.2, 4.2, "选择关卡"),
    (4.2, 8.6, "点击箭头：路径通畅则飞出"),
    (8.6, 12.0, "前方有阻挡：变红顶出，失误 -1"),
    (12.0, 99.0, "清空棋盘，通关结算"),
]

WIDTH = 640
FPS = 12
FONT = "C\\:/Windows/Fonts/msyh.ttc"      # 微软雅黑，ffmpeg 的字体路径要转义冒号


def build_filter(width, fps):
    """拼出 filter_complex：缩放 → 抽帧 → 打标题 → 两遍调色板。

    最后的 split/palettegen/paletteuse 是 ffmpeg 官方推荐的两遍做法：
    先统计整段视频的颜色生成一张调色板，再用抖动把画面映射过去，
    比直接量化成 256 色好看得多（渐变背景不会出现一块块色带）。
    """
    chain = [f"fps={fps}", f"scale={width}:-1:flags=lanczos"]
    # 逐时间段叠加标题：用 enable='between(t,a,b)' 控制显示区间
    for start, end, text in CAPTIONS:
        chain.append(
            f"drawtext=fontfile='{FONT}':text='{text}':"
            f"x=(w-text_w)/2:y=h-th-16:fontsize=22:fontcolor=white:"
            f"box=1:boxcolor=black@0.55:boxborderw=10:"
            f"enable='between(t,{start},{end})'")
    scaled = ",".join(chain)
    return (f"[0:v]{scaled},split[frames][palette_src];"
            f"[palette_src]palettegen=max_colors=256:stats_mode=diff[palette];"
            f"[frames][palette]paletteuse=dither=sierra2_4a:diff_mode=rectangle")


def main():
    if not os.path.exists(SRC):
        print(f"找不到源视频：{SRC}")
        return 1
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    graph = build_filter(WIDTH, FPS)
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-i", SRC,
        "-filter_complex", graph,
        "-loop", "0",
        DST,
    ]
    print("正在转换，参数：宽 %d，%d fps" % (WIDTH, FPS))
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print("转换失败：")
        print(result.stderr)
        return 1
    size = os.path.getsize(DST)
    print(f"完成：{DST}")
    print(f"体积：{size / 1024 / 1024:.2f} MB（GitHub 单文件建议 < 10 MB）")
    if size > 10 * 1024 * 1024:
        print("提示：超过 10MB，建议调小本脚本里的 WIDTH 或 FPS 后重跑。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
