#!/bin/bash
# Full render in three parallel chunks: ./render.sh -> out/QuotaCrux-showcase.mp4 (progress in out/progress-*.log)
set -e
cd "$(dirname "$0")"
D=163.5; CUTS=(0 54.5 109 $D)   # chunk edges on whole frames at 30 fps
rm -f out/progress-*.log out/part*.mp4
for i in 0 1 2; do node capture.cjs 30 ${CUTS[$i]} ${CUTS[$((i+1))]} out/part$i.mp4 > out/progress-$i.log 2>&1 & done
wait
printf "file 'part0.mp4'\nfile 'part1.mp4'\nfile 'part2.mp4'\n" > out/parts.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i out/parts.txt -c copy out/video-only.mp4
node events.cjs out/events.json
uv run -q --with numpy --with scipy python sfx.py out/events.json $D out/sfx.wav
ffmpeg -y -loglevel error -i out/video-only.mp4 -i out/sfx.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart out/QuotaCrux-showcase.mp4
echo "RENDER DONE"
