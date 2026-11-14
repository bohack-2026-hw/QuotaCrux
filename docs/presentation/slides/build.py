"""Builds docs/presentation/QuotaCrux.pptx: native PowerPoint shapes and text only, laid out on a 1920 x 1080 px grid.

    uv run --with python-pptx --with lxml python build.py [out.pptx]
Numbers mirror the sources listed in each slide's speaker notes.
"""
import os
import sys

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Emu

from pptkit import CJK, MONO, NUM, line, oval, pic, rect, set_transition, shape, text

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "QuotaCrux.pptx")
A = lambda n: os.path.join(HERE, "assets", n)  # noqa: E731

BG, CARD = "#F7F6F1", "#FFFFFF"
INK, INK2, MUTE, RULE = "#111111", "#4A4A4F", "#8C8A85", "#D9D6CD"
BLUE, BLUE_L, BLUE_M = "#2E49D6", "#E9EDFC", "#9AA9EE"
ORANGE, ORANGE_L = "#F0532D", "#FDECE6"
GREY_BAR = "#C9C6BE"

prs = Presentation()
prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)
BLANK = prs.slide_layouts[6]
SLIDES = []
TOTAL = 23
L, R, W = 76, 1844, 1768  # content edges


def T(s, x, y, w, h, paras, size=16, **kw):
    if isinstance(paras, str) and "\n" in paras:
        paras = paras.split("\n")
    return text(s, x, y, w, h, paras, size=size, **kw)


def mono(s, x, y, w, h, paras, size=14, **kw):
    return text(s, x, y, w, h, paras, size=size, font=MONO, latin=MONO, **kw)


def hi(*parts):
    """Title runs: plain strings in ink, (text,) tuples in blue."""
    return [[(p[0], {"color": BLUE}) if isinstance(p, tuple) else (p, {}) for p in parts]]


def new(title=None, kicker=None, sub=None, notes=""):
    s = prs.slides.add_slide(BLANK)
    rect(s, 0, 0, 1920, 1080, BG)
    set_transition(s, "fade")
    n = len(SLIDES) + 1
    SLIDES.append(s)
    rect(s, L, 47, 10, 26, ORANGE)
    T(s, 96, 40, 600, 40, "BoHack 2026", size=14, bold=True, anchor="m")
    T(s, 1144, 40, 700, 40, "倍漾量化 · Research Agent 赛道", size=14, align="r", anchor="m")
    line(s, L, 88, R, 88, INK, 2)
    if kicker:
        T(s, L, 112, 1400, 36, kicker, size=14, color=ORANGE, bold=True)
    if title:
        T(s, L, 146, W, 80, title, size=32, bold=True)
    if sub:
        T(s, L, 226, W, 40, sub, size=15, color=INK2)
    if n > 1:
        line(s, L, 1020, R, 1020, RULE, 1.5)
        T(s, L, 1028, 800, 32, "QuotaCrux 枢决 · 技术演示", size=11, color=MUTE)
        T(s, 1444, 1028, 400, 32, f"{n:02d} / {TOTAL}", size=11, color=MUTE, align="r", latin=NUM)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def box(s, x, y, w, h, title, sub=None, hot=False, ts=17, ss=12, fill=CARD):
    shape(s, MSO_SHAPE.SNIP_1_RECTANGLE, x, y, w, h, fill, line=BLUE if hot else "#BDBAB2", line_w=3 if hot else 1.5,
          adj=[0.12])
    if sub:
        T(s, x, y + h / 2 - 40, w, 40, title, size=ts, bold=True, color=BLUE if hot else INK, align="c", anchor="b")
        T(s, x + 8, y + h / 2 + 4, w - 16, 34, sub, size=ss, color=INK2, align="c")
    else:
        T(s, x, y, w, h, title, size=ts, bold=True, color=BLUE if hot else INK, align="c", anchor="m")


def arrow(s, x1, y1, x2, y2, color=INK2, w=2, dash=None):
    line(s, x1, y1, x2, y2, color, w, dash=dash, arrow=True)


def pill(s, x, y, w, h, label, fill, color, size=12, font=CJK):
    rect(s, x, y, w, h, fill, radius=h / 2)
    T(s, x, y, w, h, label, size=size, color=color, bold=True, align="c", anchor="m", font=font,
      latin=MONO if font == MONO else NUM)


def stat(s, x, y, w, label, value, desc, color=BLUE, vs=60, label_color=None):
    T(s, x, y, w, 36, label, size=15, bold=True, color=label_color or color)
    T(s, x, y + 38, w, vs * 2.2, value, size=vs, bold=True, color=color, latin=NUM)
    T(s, x, y + 46 + vs * 2.2, w, 90, desc, size=14, color=INK2, spacing=1.15)


def table(s, x, y, cols, rows, rh=64, head_size=12, size=15, hot_col=None, first_bold=True, aligns=None):
    """cols: widths; rows[0] is the header."""
    tw = sum(cols)
    if hot_col is not None:
        hx = x + sum(cols[:hot_col])
        rect(s, hx, y, cols[hot_col], rh * len(rows), BLUE_L)
    for r, row in enumerate(rows):
        cx = x
        yy = y + r * rh
        for c, cell in enumerate(row):
            al = (aligns or ["l"] * len(cols))[c]
            if r == 0:
                T(s, cx + 12, yy, cols[c] - 24, rh, cell, size=head_size, color=MUTE if c != hot_col else BLUE, bold=True,
                  anchor="m", align=al)
            else:
                st = dict(size=size, anchor="m", align=al, spacing=1.1)
                if c == 0 and first_bold:
                    st.update(bold=True)
                if isinstance(cell, tuple):
                    cell, extra = cell
                    st.update(extra)
                T(s, cx + 12, yy, cols[c] - 24, rh, cell, **st)
            cx += cols[c]
        line(s, x, yy + rh, x + tw, yy + rh, INK if r == 0 else RULE, 2 if r == 0 else 1)


# ============================================================== 1 cover
s = new(notes="开场：QuotaCrux（枢决）是一个在预算里做研究的 Agent。三个关键词：动作与模型解耦路由、隔离沙箱里的独立裁判、可回退的可执行经验快照。")
T(s, 60, 120, 1300, 240, "QuotaCrux", size=118, bold=True, color=BLUE, latin=NUM)
T(s, 76, 360, 400, 170, "枢决", size=80, bold=True)
T(s, 420, 420, 900, 60, "预算感知的 Research Agent", size=24, color=INK2)
T(s, 76, 560, 1400, 90, [[("把有限预算，用在", {}), ("关键节点", {"color": BLUE})]], size=40, bold=True)
line(s, 76 + 8 * 80, 664, 76 + 12 * 80, 664, ORANGE, 5)
# research loop chain
steps = ["规划", "取证", "假设", "实验", "验证", "修正"]
for i, st_ in enumerate(steps):
    x = L + i * 300
    box(s, x, 740, 200, 96, st_, hot=(st_ == "验证"), ts=22)
    if i < 5:
        arrow(s, x + 210, 788, x + 290, 788, BLUE, 2.5)
line(s, L + 100, 846, L + 100, 880, ORANGE, 2.5)
line(s, L + 100, 880, L + 5 * 300 + 100, 880, ORANGE, 2.5)
arrow(s, L + 5 * 300 + 100, 880, L + 5 * 300 + 100, 846, ORANGE, 2.5)
T(s, L + 560, 884, 700, 40, "验证反馈 → 更新假设与预算", size=16, color=ORANGE, align="c", bold=True)
# decorative step line, right
pts = [(1380, 600), (1500, 600), (1500, 470), (1640, 470), (1640, 400), (1760, 400), (1760, 360), (1844, 360)]
for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
    line(s, x1, y1, x2, y2, BLUE, 6)
for x, y in [(1380, 600), (1500, 470), (1640, 400), (1760, 360)]:
    oval(s, x, y, 12, BG, line=BLUE, line_w=4)
oval(s, 1844, 360, 14, ORANGE)
T(s, 1380, 620, 464, 40, "每一步都由外部裁判实测", size=14, color=INK2, align="r")
T(s, L, 960, 1300, 40, "github.com/bohack-2026-hw/QuotaCrux　·　技术演示　·　2026-11", size=14, color=MUTE, latin=NUM)

# ============================================================== 2 numbers
s = new(hi("五个数字看懂 ", ("QuotaCrux",)), "00 · 一页看懂",
        notes="先给结论。最大的数字来自 AtCoder 启发式竞赛真题 ahc026：15 个隐藏用例总能耗降 44.7%。其余四个数字分别代表函数级优化、经验复用、在线任务流和交付可靠性。\n\n来源：docs/research/native-routing/20261114 · docs/archive/memory-learning-results.md · README 核心实测成果")
T(s, L, 290, 840, 36, "ALE-Bench ahc026 搬箱子 · 15 个隐藏用例总能耗", size=16, bold=True, color=ORANGE)
T(s, L - 6, 330, 900, 250, "−44.7%", size=118, bold=True, color=ORANGE, latin=NUM)
for i, (lab, v, w, c) in enumerate([("初始程序", "18,136", 560, GREY_BAR), ("QuotaCrux", "10,028", 310, BLUE)]):
    y = 620 + i * 70
    T(s, L, y, 170, 50, lab, size=15, anchor="m", bold=(i == 1))
    rect(s, L + 180, y + 10, w, 30, c)
    T(s, L + 180 + w + 16, y, 200, 50, v, size=18, bold=True, anchor="m", latin=NUM)
T(s, L, 790, 840, 80, "15/15 通过隐藏测试 · 总分 131,864 → 139,972", size=16, color=INK2)
line(s, 960, 290, 960, 960, RULE, 1.5)
line(s, 1000, 625, R, 625, RULE, 1.5)
line(s, 1422, 290, 1422, 960, RULE, 1.5)
cells = [("AlgoTune · 函数级", "25.0×", "PageRank 提速\n稀疏矩阵直接幂迭代", BLUE), ("D 封存留出 · 经验复用", "18/18", "零模型调用直接交付\n加速比中位数 1.20× → 1.73×", BLUE),
         ("S 在线任务流 · 分流器", "−78%", "大模型请求 27 → 6\n费用 $0.402 → $0.086", ORANGE), ("ALE 正式消融 · 交付", "15/15", "交付候选全部通过隐藏测试\n96 个候选 60 个通过开发验证", BLUE)]
for i, (lab, v, d, c) in enumerate(cells):
    x, y = 1000 + (i % 2) * 462, 300 + (i // 2) * 345
    stat(s, x, y, 430, lab, v, d, color=c, vs=54)

# ============================================================== 3 problem
s = new(hi("研究型 Agent 贵在一次又一次的", ("“再试一次”",)), "01 · 问题",
        notes="研究型 Agent 常见两种低效：一直用大模型试错，钱花在重复改写上；或者只用小模型、只存文字心得，原地打转。两条证据都来自我们自己的受控实验。\n\n来源：docs/research/onehour-20261114 · docs/archive/memory-learning-results.md 第 3 节")
for i, (k, h, items, ev_n, ev_t) in enumerate([
        ("低效 A", "一直让大模型盲目试错", ["每一次改写都要付费、要等待", "预算消耗在重复改写和无效分析上", "没有外部裁判，“看起来变好了”无法验证"], "6–7 次", "固定大模型每轮的大模型请求，得分提升 5.50%–5.73%"),
        ("低效 B", "弱模型 + 文字经验原地打转", ["小模型在复杂约束下难以突破", "只存文字心得：好程序要重新写一遍", "达标即停，更好的方案不会被再用"], "0%", "固定小模型两台机器均无提升；文字经验让加速比 1.41× → 1.29×")]):
    x = L + i * 904
    T(s, x, 300, 800, 34, k, size=15, bold=True, color=ORANGE)
    T(s, x, 340, 840, 60, h, size=26, bold=True)
    T(s, x, 420, 840, 200, ["·  " + t for t in items], size=17, color=INK2, space_after=8)
    line(s, x, 640, x + 840, 640, RULE, 1.5)
    T(s, x, 660, 300, 90, ev_n, size=44, bold=True, color=ORANGE, latin=NUM)
    T(s, x + 300, 668, 540, 90, ev_t, size=15, color=INK2, anchor="m")
rect(s, L, 820, W, 120, ORANGE_L)
rect(s, L, 820, 10, 120, ORANGE)
T(s, L + 50, 820, 1700, 120, "有限预算下：何时思考、何时实验、何时升级模型、何时停止？", size=28, bold=True, anchor="m")

# ============================================================== 4 inspiration
s = new(hi("灵感来源：把", ("研究决策",), "独立出来"), "01 · 灵感来源",
        notes="三个灵感：DeepSeek SuperAgent 的 Router/Worker 分层；中间是赛题的 Built for Better——会自我进化的智能；右边是 Jev 与 OpenAI Decisions 的类型化决策。\n\n来源：README「设计定位与灵感」 · github.com/deepseek-ai/dsh-superagent-prototype · docs.typesafe.ai")
cards = [(L, 310, 540, 640, False, "DeepSeek SuperAgent", "编排与执行分离", "Router 负责交互与任务分派，Worker 在独立会话和工作目录中执行。",
          "拆成三个边界：动作、模型、任务与评测 adapter"),
         (L + 590, 280, 588, 700, True, "BUILT FOR BETTER", "会自我进化的智能", "每次沙箱评测的真实反馈，都沉淀为可检验、可对比、可回退的资产。",
          "下一次运行更快、更省、更稳——而且能拿数据证明"),
         (L + 1228, 310, 540, 640, False, "Jev · OpenAI Decisions", "类型化的小决策", "把“状态 + 类型化问题”映射为选择及概率；gpt-6-luna 已接入。",
          "下一步做什么交给决策模型；与生成共用一份预算")]
for x, y, w, h, big, tag, head, idea, to in cards:
    rect(s, x, y, w, h, BLUE if big else CARD, radius=14, line=None if big else RULE, line_w=1.5)
    fg, fg2 = ("#FFFFFF", "#DCE2FB") if big else (INK, INK2)
    T(s, x + 40, y + 40, w - 80, 34, tag, size=15 if not big else 18, bold=True, color=ORANGE if not big else "#FFD2C4", latin=NUM)
    T(s, x + 40, y + 90, w - 80, 70, head, size=26 if not big else 30, bold=True, color=fg)
    T(s, x + 40, y + 190, w - 80, 200, idea, size=17 if not big else 20, color=fg2, spacing=1.3)
    line(s, x + 40, y + h - 220, x + w - 40, y + h - 220, "#FFFFFF" if big else RULE, 1.5, alpha=0.5 if big else None)
    T(s, x + 40, y + h - 200, w - 80, 34, "在 QuotaCrux 中", size=13, bold=True, color="#FFD2C4" if big else BLUE)
    T(s, x + 40, y + h - 160, w - 80, 140, to, size=17 if not big else 20, bold=True, color=fg, spacing=1.3)

# ============================================================== 5 principles
s = new("五条设计原则", "01 · 设计原则", notes="五条原则贯穿所有设计。\n\n来源：README · docs/design/action-model-routing.md")
for i, (p, d) in enumerate([("预算是一等公民", "请求数、候选数、研究时长由程序硬约束，耗尽即停，不为总结额外调用"),
                            ("模型不自评", "正确性与性能只由外部裁判实测；判定“支持 / 反驳”的是程序，不是模型"),
                            ("经验必须可执行", "保存已验证的完整程序与它成立的输入条件，而不只是文字心得"),
                            ("每一笔都记账", "角色、Token、延迟、费用逐次落账；服务方未返回用量记为 null，绝不写 0"),
                            ("任何进化都可回退", "经验以不可变快照 v0, v1, … 原子发布；切换默认版本留审计记录")]):
    y = 300 + i * 136
    T(s, L, y, 120, 100, f"0{i + 1}", size=36, bold=True, color=BLUE, latin=NUM, anchor="m")
    T(s, L + 140, y, 520, 100, p, size=26, bold=True, anchor="m")
    T(s, L + 700, y, 1068, 100, d, size=18, color=INK2, anchor="m")
    line(s, L, y + 118, R, y + 118, RULE, 1)

# ============================================================== 6 architecture
s = new("系统架构", "02 · 系统架构",
        notes="一次运行的完整路径：先复验经验里最接近的已验证程序；不达标再由分流器决定从哪个模型开始；进入受预算约束的研究循环；动作路由和模型路由分别决定做什么、由谁做；所有候选进隔离沙箱实测；冻结最佳候选做一次隐藏测试；最后导出报告并发布新快照。\n\n来源：README「系统架构与研究闭环」 · backend/src/quotacrux/agent/{runner,routing}.py")
box(s, L, 340, 280, 100, "冻结任务包", "契约 · c0 · 开发 / final")
box(s, L, 500, 280, 100, "经验快照 vN", "不可变 · 已验证程序")
box(s, 430, 410, 300, 110, "模型前复验", "≤ 3 个最相近程序")
box(s, 430, 620, 300, 110, "经验覆盖分流器", "相近 → 小 · 新族 → 大", hot=True)
arrow(s, 356, 390, 430, 450); arrow(s, 356, 550, 430, 485)
arrow(s, 580, 520, 580, 620); T(s, 594, 550, 120, 40, "未达标", size=13, color=INK2)
shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 800, 300, 820, 600, None, line=ORANGE, line_w=2, dash="dash", adj=[0.04])
T(s, 830, 312, 500, 40, "受预算约束的研究循环", size=16, bold=True, color=ORANGE)
T(s, 1260, 312, 340, 40, "360 s · 20 次请求 · 10 个候选", size=12, color=INK2, align="r")
box(s, 840, 370, 320, 100, "可见状态", "契约 · 候选 · 裁判事实")
box(s, 1220, 370, 320, 100, "ActionRouter", "llm | decisions", hot=True)
box(s, 1220, 550, 320, 100, "ModelRouter", "rule | decisions", hot=True)
box(s, 840, 550, 320, 100, "生成", "Qwen 小模型 · gpt-6.1-sol")
box(s, 840, 730, 320, 100, "静态检查", "动作参数 · 允许范围")
box(s, 1220, 730, 320, 100, "隔离沙箱裁判", "正确性 · 用例 · 计时", hot=True)
arrow(s, 1160, 420, 1220, 420); arrow(s, 1380, 470, 1380, 550); T(s, 1392, 492, 220, 36, "分析 / 提出候选", size=12, color=INK2)
arrow(s, 1220, 600, 1160, 600); arrow(s, 1000, 650, 1000, 730); arrow(s, 1160, 780, 1220, 780)
line(s, 1540, 420, 1580, 420, INK2, 2); line(s, 1580, 420, 1580, 780, INK2, 2); arrow(s, 1580, 780, 1540, 780)
T(s, 1586, 520, 30, 180, "取证复验结束", size=11, color=INK2)
line(s, 1380, 830, 1380, 866, ORANGE, 2, dash="dash"); line(s, 1380, 866, 822, 866, ORANGE, 2, dash="dash")
line(s, 822, 866, 822, 420, ORANGE, 2, dash="dash"); arrow(s, 822, 420, 840, 420, ORANGE, 2)
T(s, 840, 862, 400, 34, "仅严格优于当前最佳才更新", size=12, color=ORANGE)
arrow(s, 730, 675, 800, 675)
box(s, 1660, 340, 184, 110, "冻结最佳", "隐藏 final 一次", ts=16)
box(s, 1660, 520, 184, 110, "报告 · 账本", "复现包", ts=16)
box(s, 1660, 700, 184, 110, "快照 vN+1", "原子发布", hot=True, ts=16)
arrow(s, 1620, 395, 1660, 395); arrow(s, 1752, 450, 1752, 520); arrow(s, 1752, 630, 1752, 700)
line(s, 580, 410, 580, 282, MUTE, 2, dash="dash"); line(s, 580, 282, 1752, 282, MUTE, 2, dash="dash"); arrow(s, 1752, 282, 1752, 340, MUTE, 2, dash="dash")
T(s, 900, 246, 560, 34, "复验达标 → 直接交付，不调用模型", size=12, color=INK2, align="c")
line(s, 1752, 810, 1752, 950, ORANGE, 2, dash="dash"); line(s, 1752, 950, 216, 950, ORANGE, 2, dash="dash"); arrow(s, 216, 950, 216, 600, ORANGE, 2, dash="dash")
T(s, 560, 954, 800, 34, "learn / online 模式：程序提取已验证事实，写回经验", size=13, color=ORANGE, align="c")

# ============================================================== 7 loop table
s = new(hi("研究闭环：每一步", ("谁负责",)), "02 · 研究闭环",
        notes="研究闭环的每一步，模型做什么、程序做什么，分得很清楚。模型只负责提出想法和代码；检查、执行、判定、升级、记账都由程序完成。\n\n来源：docs/presentation/project-overview.md · docs/design/action-model-routing.md")
rows = [["环节", "模型做什么", "程序做什么"],
        ["规划", "用“分析”写下计划", "研究问题、基线、允许修改范围、工具、预算在运行前固定"],
        ["取证", "决定是否需要证据", "沙箱内对候选做 cProfile；返回状态、指标、失败类别与公开反例"],
        ["假设", "写目的、假设、预期与验证方法", "静态检查动作参数与允许范围；假设一律标为“未验证”"],
        ["实验", "生成候选代码", "隔离容器中由固定评测器检查正确性、规则用例，并交替计时"],
        ["修正", "读取判定与反例，提出下一版", "判定支持 / 部分支持 / 反驳 / 未能检验；按规则升级模型"],
        ["分流", "—", "按经验覆盖决定从小模型还是大模型开始"],
        ["交付", "—", "冻结最佳候选，隐藏数据上独立测试一次；导出记录、程序与复核脚本"]]
table(s, L, 290, [200, 520, 1048], rows, rh=84, size=16, hot_col=2)

# ============================================================== 8 action x model
s = new(hi("“做什么”和“谁来做”是", ("两个决策",)), "特色 ① · 动作 × 模型 解耦路由", "动作与模型分开路由，各自可用规则或专用决策模型，组合后单独比较",
        notes="两个正交的决策点：ActionRouter 决定下一步做什么，ModelRouter 决定这一步由哪个模型生成。右边是 ahc026 上的四组组合，同样预算，各 1 次。\n\n来源：docs/design/action-model-routing.md · docs/research/native-routing/20261114/RESULTS.md")
box(s, L, 520, 220, 110, "可见状态", "证据 · 预算", ts=16)
box(s, 350, 500, 250, 150, "ActionRouter", "下一步做什么", hot=True, ts=19)
arrow(s, 296, 575, 350, 575)
for y, a_, gen in [(320, "analyze", True), (390, "propose_candidate", True), (660, "profile_candidate", False), (730, "run_validation", False), (800, "finish", False)]:
    pill(s, 690, y, 300, 52, a_, BLUE_L if gen else "#ECEAE4", BLUE if gen else INK, size=13, font=MONO)
    line(s, 600, 575, 690, y + 26, BLUE if gen else MUTE, 1.5)
box(s, 690, 470, 300, 100, "ModelRouter", "small → large 单向升级", hot=True, ts=17)
arrow(s, 840, 442, 840, 470, BLUE)
T(s, 690, 282, 300, 34, "需要生成 → 交给模型", size=12, color=BLUE, align="c", bold=True)
T(s, 690, 616, 300, 34, "程序直接执行", size=12, color=INK2, align="c")
T(s, L, 700, 560, 200, ["llm：生成模型自选动作", "decisions：gpt-6-luna 从合法项中选", "rule：连续 2 个未达标或 3 次小模型请求即升级"], size=13, color=INK2, space_after=6)
T(s, 1080, 290, 760, 34, "ahc026 · 同预算四组 · 相对 c0 的 final 提升", size=14, bold=True, color=MUTE)
for i, (nm, v, ln, hot) in enumerate([("LLM / rule · 基线", "+5.97%", "392 秒\n请求 小 3 · 大 6 · 决策 0", False), ("Decisions / rule", "+6.15%", "389 秒\n请求 小 2 · 大 5 · 决策 7", True),
                                      ("LLM / Decisions", "+5.84%", "390 秒\n请求 小 7 · 大 4 · 决策 8", False), ("Decisions / Decisions", "+0.51%", "113 秒\n全程只用小模型", False)]):
    x, y = 1080 + (i % 2) * 390, 340 + (i // 2) * 250
    rect(s, x, y, 370, 230, ORANGE_L if hot else CARD, radius=12, line=ORANGE if hot else RULE, line_w=2 if hot else 1.5)
    mono(s, x + 26, y + 22, 330, 34, nm, size=13, color=INK2)
    T(s, x + 22, y + 56, 340, 100, v, size=44, bold=True, color=ORANGE if hot else INK, latin=NUM)
    T(s, x + 26, y + 158, 330, 64, ln, size=12, color=INK2)
T(s, 1080, 860, 760, 60, "路由请求计入同一份 20 次请求预算。每组 1 次，属探索性观察。", size=13, color=MUTE)

# ============================================================== 9 judge
s = new(hi("候选好不好，", ("只由裁判说了算",)), "特色 ② · 零信任外部裁判",
        notes="模型永远看不到、也改不了评测器。每个样本一个全新容器：禁网、只读、非 root、1 CPU 1 GB。性能用预热加 5 轮交替计时，要求候选的 5 个样本全部快于基线的 5 个样本，再加 1.10 倍门槛。研究结束后在隐藏数据上只测一次。\n\n来源：docs/presentation/project-overview.md 第 2 节 · backend/src/quotacrux/evaluator")
rect(s, L, 290, 800, 420, CARD, radius=14, line="#BDBAB2", line_w=1.5)
T(s, L + 24, 302, 760, 36, "宿主机 · 评测器（模型不可见、不可改）", size=15, bold=True)
shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, L + 40, 350, 720, 330, None, line=INK2, line_w=1.5, dash="dash", adj=[0.05])
T(s, L + 64, 362, 680, 34, "每个样本一个全新容器", size=14, bold=True, color=INK2)
rect(s, L + 80, 410, 640, 210, BLUE_L, radius=12, line=BLUE, line_w=2.5)
T(s, L + 104, 420, 600, 34, "候选程序（只挂载候选文件）", size=14, bold=True, color=BLUE)
for i, tg in enumerate(["禁网", "只读根文件系统", "非 root", "1 CPU · 1 GB", "64 进程", "stdin 输入"]):
    pill(s, L + 104 + (i % 3) * 200, 470 + (i // 3) * 62, 186, 46, tg, CARD, INK, size=12)
T(s, L + 64, 634, 700, 34, "参考输出留在宿主机 · 计时从容器内启动器就绪开始", size=12, color=INK2)
T(s, L, 740, 400, 34, "交替计时 · 预热后 5 轮", size=15, bold=True)
for i in range(5):
    x = L + i * 160
    pill(s, x, 784, 70, 38, "B", "#D7D4CC", INK2, size=12, font=MONO)
    pill(s, x + 76, 784, 70, 38, "C", BLUE, "#FFFFFF", size=12, font=MONO)
X = lambda ms: L + 20 + (ms - 130) / 100 * 760  # noqa: E731
line(s, L, 900, L + 800, 900, RULE, 2)
for v in [212, 205, 218, 209, 214]:
    oval(s, X(v), 900, 11, "#A9A69E")
for v in [151, 148, 156, 150, 153]:
    oval(s, X(v), 900, 11, BLUE)
line(s, X(184), 868, X(184), 932, INK2, 1.5, dash="dash")
T(s, X(152) - 120, 850, 240, 30, "候选 5 个样本", size=12, color=BLUE, align="c")
T(s, X(212) - 120, 850, 240, 30, "基线 5 个样本", size=12, color=INK2, align="c")
T(s, L, 936, 800, 34, "全部分开（U = 0）且加速比 ≥ 1.10× 才算达标 · 示意", size=12, color=MUTE)
for i, (t_, d) in enumerate([("静态检查", "动作参数、允许修改范围、只用标准库等"), ("开发集正确性", "输出逐项比对，参考输出只留在宿主机"),
                             ("公开规则用例", "每个任务族 7 个边界用例"), ("预热 + 5 轮交替计时", "基线与候选交替测量，抵消机器漂移"),
                             ("严格判定", "候选样本全部快于基线（U = 0）且 ≥ 1.10×"), ("隐藏 final 只测一次", "冻结开发最佳候选；结果不回流到研究过程")]):
    y = 292 + i * 112
    T(s, 960, y, 80, 90, f"0{i + 1}", size=24, bold=True, color=ORANGE, latin=NUM, anchor="m")
    T(s, 1050, y + 8, 790, 40, t_, size=19, bold=True)
    T(s, 1050, y + 48, 790, 40, d, size=14, color=INK2)
    line(s, 960, y + 104, R, y + 104, RULE, 1)

# ============================================================== 10 hypothesis
s = new(hi("每个候选都是", ("一次实验",)), "特色 ③ · 假设—判定",
        notes="每个候选提交前必须写假设；评测后由程序判定。262 次正式运行一共 536 个实验。下面是一条真实的修正链：c1 被反驳，c2 格式错误未能检验，触发升级，大模型读到具体反馈后做出 1.45 倍。\n\n来源：docs/presentation/project-overview.md 第 5.4 节 · docs/research/ 样例 A-01")
rect(s, L, 290, 820, 390, CARD, radius=12, line=RULE, line_w=1.5)
mono(s, L + 28, 306, 780, 370, ["# 候选提交时必须填写（模型）· 示意", "purpose:     减少逐行解析开销", "hypothesis:  批量 split 比 csv 模块更快", "expected:    加速比 ≥ 1.3×",
                                 "validation:  开发集 + 规则用例 + 交替计时", "", "# 评测后由程序写入（裁判）", "verdict:     supported | partial |", "             refuted | untestable"],
     size=14, color=INK, spacing=1.25)
vrows = [["判定", "条件"], [("支持", {"color": BLUE}), "正确、有改善且达标"], [("部分支持", {"color": BLUE}), "正确、有改善但未达标"], ["反驳", "正确但没有改善"], ["未能检验", "候选出错，无法检验假设"]]
table(s, L, 706, [220, 600], vrows, rh=56, size=15)
T(s, 960, 290, 880, 34, "262 次正式运行 · 536 个实验（复用 215 · 模型 321）", size=14, bold=True, color=MUTE)
x = 960
for nm, v, c in [("支持", 371, BLUE), ("部分支持", 36, BLUE_M), ("反驳", 100, GREY_BAR), ("未能检验", 29, "#6E6C67")]:
    w = v / 536 * 884
    rect(s, x, 340, w - 3, 64, c)
    x += w
for i, (nm, v, c) in enumerate([("支持", "371", BLUE), ("部分支持", "36", BLUE_M), ("反驳", "100", GREY_BAR), ("未能检验", "29", "#6E6C67")]):
    xx = 960 + i * 221
    rect(s, xx, 430, 16, 16, c)
    T(s, xx + 26, 420, 190, 34, nm, size=14, color=INK2)
    T(s, xx, 456, 200, 70, v, size=32, bold=True, color=BLUE if i == 0 else INK, latin=NUM)
T(s, 960, 580, 880, 34, "一条真实的修正链 · 任务 A-01", size=14, bold=True, color=MUTE)
for i, (cid, v, verdict, who, kind) in enumerate([("c1", "0.90×", "反驳", "Qwen", "n"), ("c2", "格式错误", "未能检验", "Qwen", "n"), ("升级", "", "", "rule", "up"), ("c3", "1.45×", "支持", "GPT", "hot")]):
    xx = 960 + i * 226
    if kind == "up":
        shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, xx, 630, 196, 190, ORANGE_L, line=ORANGE, line_w=2, dash="dash", adj=[0.08])
        T(s, xx, 656, 196, 40, "↑ 升级", size=16, bold=True, color=ORANGE, align="c")
        T(s, xx + 6, 704, 184, 110, ["大模型接手", "连续 2 个未达标", "读取具体反馈"], size=11, color=INK2, align="c", space_after=4)
    else:
        rect(s, xx, 630, 196, 190, BLUE_L if kind == "hot" else CARD, radius=10, line=BLUE if kind == "hot" else RULE, line_w=2 if kind == "hot" else 1.5)
        mono(s, xx + 18, 644, 100, 30, cid, size=13, color=INK2)
        mono(s, xx + 90, 644, 90, 30, who, size=11, color=MUTE, align="r")
        T(s, xx + 14, 690, 180, 70, v, size=19 if v == "格式错误" else 30, bold=True, color=BLUE if kind == "hot" else INK, latin=NUM)
        T(s, xx + 18, 768, 170, 34, verdict, size=14, color=BLUE if kind == "hot" else INK2, bold=kind == "hot")
    if i < 3:
        arrow(s, xx + 198, 725, xx + 224, 725, ORANGE if i == 2 else INK2)

# ============================================================== 11 snapshots + triage
s = new(hi("存", ("可运行的程序",), "，再按经验覆盖", ("分流",)), "特色 ④⑤ · 可执行经验快照 · 经验覆盖分流器",
        notes="经验由程序从评测记录中提取：完整代码、输入条件特征、实测结果，成功、无收益、失败三态都存。快照不可变，可回退。复验没达标时，分流器按经验覆盖决定从哪个模型开始：有相近的成功经验，先用便宜的本地小模型；全新任务族或新条件，直接交给大模型。\n\n来源：docs/archive/memory-learning-results.md · router-v1 · T 任务对照")
T(s, L, 290, 820, 40, "可执行经验快照", size=20, bold=True, color=BLUE)
for (cx, cy, lab, filled) in [(140, 450, "v0", False), (400, 450, "v19", True), (660, 450, "v…", True), (400, 360, "v6", False)]:
    oval(s, cx, cy, 34, BLUE if filled else CARD, line=BLUE if filled else MUTE, line_w=2.5)
    mono(s, cx - 40, cy - 18, 80, 36, lab, size=13, bold=True, color="#FFFFFF" if filled else INK, align="c", anchor="m")
line(s, 174, 450, 366, 450, BLUE, 3); line(s, 434, 450, 626, 450, BLUE, 3)
line(s, 166, 428, 368, 366, MUTE, 2, dash="dash")
T(s, 190, 488, 200, 30, "A 批学习两轮", size=12, color=BLUE, align="c")
T(s, 450, 488, 200, 30, "S 在线任务流", size=12, color=BLUE, align="c")
T(s, 446, 336, 420, 60, ["v1 · 只存文字经验 · 13 条", "留出集加速比 1.41× → 1.29×"], size=12, color=MUTE)
for i, (n_, d) in enumerate([("59", "v19 经验条数\n成功 42 · 无收益 13 · 失败 4"), ("21", "可复验的不同程序"), ("5 项", "每族输入条件特征\n至少 3 项相同才检索")]):
    x = L + i * 280
    T(s, x, 540, 260, 70, n_, size=36, bold=True, color=BLUE, latin=NUM)
    T(s, x, 616, 260, 70, d, size=12, color=INK2, spacing=1.15)
kv = [("先复验", "调用模型前，复验条件最接近的 ≤ 3 个已验证程序"), ("失败前科", "失败记录比成功记录更接近当前条件 → 跳过"), ("可回退", "snapshots activate v0：只移动默认指针，快照不变")]
for i, (k, v) in enumerate(kv):
    y = 730 + i * 66
    T(s, L, y, 150, 50, k, size=14, bold=True, color=BLUE, anchor="m")
    T(s, L + 160, y, 660, 50, v, size=14, color=INK2, anchor="m")
    line(s, L, y + 60, L + 820, y + 60, RULE, 1)
line(s, 960, 290, 960, 960, RULE, 1.5)
T(s, 1000, 290, 840, 40, "经验覆盖分流器", size=20, bold=True, color=BLUE)
box(s, 1000, 350, 300, 80, "复验达标？", ts=16)
box(s, 1380, 350, 240, 80, "直接交付", "0 次模型调用", hot=True, ts=15, ss=11)
arrow(s, 1300, 390, 1380, 390, BLUE); T(s, 1310, 352, 60, 30, "是", size=12, color=BLUE, align="c")
box(s, 1000, 480, 300, 90, "经验覆盖如何？", "同族记录 · 匹配 ≥ 3/5", ts=16, ss=11)
arrow(s, 1150, 430, 1150, 480); T(s, 1160, 438, 60, 30, "否", size=12, color=INK2)
for i, (k, a_, hot) in enumerate([("相近成功", "先用本地小模型", False), ("全新任务族", "直接交给大模型", True), ("新条件", "直接交给大模型", True)]):
    x = 1000 + i * 284
    arrow(s, 1150, 570, x + 130, 610, BLUE if hot else INK2, 1.5)
    rect(s, x, 610, 260, 96, BLUE_L if hot else CARD, radius=10, line=BLUE if hot else RULE, line_w=1.5)
    T(s, x + 16, 618, 230, 30, k, size=12, color=INK2)
    T(s, x + 16, 650, 230, 40, a_, size=16, bold=True, color=BLUE if hot else INK)
trows = [["4 个新任务族任务 × 3 次", "先用 Qwen", "直接 GPT"], ["达标", "12/12", "12/12"], ["加速比中位数", "2.11×", ("2.18×", {"color": BLUE, "bold": True})],
         ["循环时长中位数", "49 s", ("33 s", {"color": BLUE, "bold": True})], ["费用", "$0.047", "$0.188"]]
table(s, 1000, 740, [360, 220, 264], trows, rh=46, size=14, aligns=["l", "r", "r"])

# ============================================================== 12 ledger
s = new(hi("每一笔都记账，", ("每个结论都能复现",)), "特色 ⑥ · 资源账本与复现包",
        notes="每次模型调用都记账，未知用量记 null。研究结束可以一键导出复现包，里面有 reproduce.sh。三个样例在最终数据上的复核结果与记录值吻合。\n\n来源：docs/presentation/project-overview.md 第 6 节 · quotacrux export-run")
T(s, L, 290, 820, 34, "每次模型调用记录的字段", size=14, bold=True, color=MUTE)
fields = [("provider / model", "openai · gpt-6.1-sol"), ("role / reasoning", "large · xhigh"), ("tokens", "输入 · 缓存 · 输出 · 推理"), ("latency_s / request_id", "延迟与服务方请求号"),
          ("price_table", "2026-11-13 价表版本"), ("cost", "未返回用量 → null，绝不写 0")]
for i, (k, v) in enumerate(fields):
    y = 336 + i * 76
    mono(s, L, y, 360, 60, k, size=14, color=BLUE, anchor="m")
    T(s, L + 370, y, 450, 60, v, size=15, anchor="m", bold=(i == 5), color=ORANGE if i == 5 else INK)
    line(s, L, y + 68, L + 820, y + 68, RULE, 1)
T(s, L, 810, 820, 60, "本地 Qwen 记“无 API 费用”，机器成本单列为未核算", size=13, color=MUTE)
T(s, 980, 290, 860, 34, "quotacrux export-run <run_id> --bundle", size=14, bold=True, color=MUTE, font=MONO, latin=MONO)
rect(s, 980, 336, 864, 300, CARD, radius=12, line=RULE, line_w=1.5)
mono(s, 1008, 352, 820, 280, ["bundle/", "├── README.md       # 研究记录", "├── best.py         # 最佳程序", "├── candidates/     # 全部候选", "├── model_calls/    # 原始模型调用",
                               "├── report.json     # 结构化报告", "└── reproduce.sh    # 一键复核"], size=14, spacing=1.2)
rrows = [["样例", "记录值", "复核"], ["v1 · A-01", "1.4367×", ("1.44×", {"color": BLUE, "bold": True})], ["v2 · D-01", "1.4481×", ("1.4473×", {"color": BLUE, "bold": True})],
         ["v3 · S-01 新任务族", "6.35×", ("6.69×", {"color": BLUE, "bold": True})]]
table(s, 980, 680, [400, 232, 232], rrows, rh=60, size=15, aligns=["l", "r", "r"])

# ============================================================== 13 ahc026
s = new(hi("测试难题：", ("搬箱子",)), "实测 · ALE-Bench ahc026",
        notes="测试难题是 AtCoder 启发式竞赛第 26 题：200 个箱子分在 10 堆，按编号顺序搬出。搬一摞 k 个箱子耗 k+1 份力气。图是初始程序真实操作的回放：第一步就把 19 个箱子压在箱子 8 上，后面要为此再付 29 份力气。\n\n来源：ALE-Bench ahc026 题面 · video/data/make_replay.py")
rect(s, L - 2, 288, 1064, 600, RULE)
pic(s, A("bad-placement.png"), L, 290, 1060, 596)
kv = [("规模", "200 个箱子 · 10 堆 · 每堆 20"), ("目标", "按 1、2、3… 的顺序搬出仓库"), ("操作 1", "把箱子 v 及上方一摞移到另一堆，搬 k 个耗 k+1"), ("操作 2", "最小编号的箱子在顶上时搬出，不耗能"), ("得分", "max(1, 10000 − 总能耗)，最多 5000 步")]
for i, (k, v) in enumerate(kv):
    y = 288 + i * 92
    T(s, 1190, y, 130, 84, k, size=15, bold=True, color=BLUE, anchor="m")
    T(s, 1320, y, 524, 84, v, size=15, anchor="m", spacing=1.1)
    line(s, 1190, y + 88, R, y + 88, RULE, 1)
rect(s, 1190, 770, 654, 140, ORANGE_L, radius=10)
T(s, 1216, 780, 600, 30, "图中是真实回放", size=13, bold=True, color=ORANGE)
T(s, 1216, 816, 610, 90, [[("初始程序第一步把 19 个箱子压在箱子 8 上，到第 15 步得再付 ", {}), ("29", {"color": ORANGE, "bold": True}), (" 份力气挪开。", {})]], size=16, spacing=1.25)

# ============================================================== 14 step chart
s = new(hi("360 秒里的 ", ("7 个候选",)), "实测 · 一轮研究的全过程", "开发集得分随研究时间变化 · 预算 360 秒 · 20 次请求 · 10 个候选",
        notes="这是一轮真实研究，横轴是已用时间。小模型两次交了同一份代码，分数不动；按规则升级到大模型；大模型学会分段规划，一下涨 2,386；局部搜索再上一步；c5 改坏了被裁判拦下；最后复用相同后缀，拿到这一轮最高 46,849。\n\n来源：docs/research/native-routing/20261114/short-results/run-20261114T085616-894b · 研究报告第 5 节")
x0, x1, y0, y1, lo, hi_ = 250, 1740, 330, 900, 43800, 47100
X = lambda t: x0 + t / 360 * (x1 - x0)  # noqa: E731
Y = lambda v: y1 - (v - lo) / (hi_ - lo) * (y1 - y0)  # noqa: E731
rect(s, x0, y0 - 10, X(26) - x0, y1 - y0 + 10, "#EEF0F6")
for v in [44000, 45000, 46000, 47000]:
    line(s, x0, Y(v), x1, Y(v), RULE, 1)
    T(s, x0 - 170, Y(v) - 18, 150, 36, f"{v:,}", size=13, color=MUTE, align="r", anchor="m")
for t_ in [0, 60, 120, 180, 240, 300]:
    T(s, X(t_) - 60, y1 + 10, 120, 34, f"{t_}s", size=13, color=MUTE, align="c", font=MONO, latin=MONO)
line(s, x0, y1, x1, y1, INK, 2)
line(s, X(360), y0 - 10, X(360), y1, INK, 2, dash="dash")
T(s, X(360) - 120, y1 + 10, 240, 34, "360s 预算", size=13, bold=True, align="c")
T(s, x0 + 10, y1 - 44, 200, 34, "Qwen", size=12, color=MUTE, font=MONO, latin=MONO)
T(s, X(26) + 14, y1 - 44, 300, 34, "gpt-6.1-sol", size=12, color=BLUE, font=MONO, latin=MONO)
line(s, X(26), y0 - 10, X(26), y1, ORANGE, 3, dash="dash")
T(s, X(26) + 18, Y(46150), 420, 90, [[("连续两次没进步", {})], [("→ 按规则升级大模型", {"color": ORANGE})]], size=17, bold=True)
C = [(12.851, 44120, "s", "44,120", "b"), (22.792, 44120, "s", "同一份代码", "a"), (94.286, 46506, "l", "分段规划 · 46,506", "a"), (178.438, 46798, "l", "局部搜索 · 46,798", "a"),
     (244.796, 46725, "x", "46,725 · 下降，被拦下", "b"), (311.463, 46800, "l", "46,800", "b"), (357.026, 46849, "l", "复用后缀 · 46,849", "e")]
pts, best = [], None
for t_, v, m, *_ in C:
    if m == "x":
        continue
    if best is None:
        pts.append((X(t_), Y(v)))
    else:
        pts += [(X(t_), Y(best)), (X(t_), Y(max(best, v)))]
    best = max(best or 0, v)
pts.append((X(360), Y(best)))
for (a1, b1), (a2, b2) in zip(pts, pts[1:]):
    line(s, a1, b1, a2, b2, BLUE, 5)
T(s, X(110), Y(45200), 600, 140, "+2,386", size=64, bold=True, color=ORANGE, latin=NUM)
for i, (t_, v, m, lab, pos) in enumerate(C):
    cx, cy = X(t_), Y(v)
    if m == "x":
        oval(s, cx, cy, 15, CARD, line=ORANGE, line_w=3)
        T(s, cx - 15, cy - 16, 30, 32, "×", size=16, bold=True, color=ORANGE, align="c", anchor="m")
    else:
        oval(s, cx, cy, 12, "#A9A69E" if m == "s" else BLUE, line=BG, line_w=3)
    if pos == "b":
        T(s, cx - 200, cy + 18, 400, 36, lab, size=14, bold=True, align="c", color=ORANGE if m == "x" else INK)
    elif pos == "e":
        T(s, cx - 380, cy - 56, 400, 36, lab, size=14, bold=True, align="r")
    elif i == 1:
        T(s, cx - 330, cy - 52, 340, 36, lab, size=14, bold=True, align="r")
    else:
        T(s, cx - 200, cy - 54, 400, 36, lab, size=14, bold=True, align="c")

# ============================================================== 15 result
s = new(hi("冻结最好的版本，", ("只测一次",)), "实测 · 隐藏测试",
        notes="冻结最好的版本，在 15 个没见过的用例上只测一次：全部通过，总能耗从 18,136 降到 10,028。右图是同一个用例上初始程序和最终版本的同步回放：这个用例的能耗从 1,158 降到 649。\n\n来源：研究报告 deep-analysis.json · ahc026_movement_energy · video/data/replay.json")
T(s, L, 300, 640, 34, "15 个隐藏用例 · 总能耗", size=15, bold=True, color=ORANGE)
T(s, L - 6, 340, 700, 200, "−44.7%", size=96, bold=True, color=ORANGE, latin=NUM)
T(s, L, 560, 700, 90, [[("18,136", {"color": MUTE}), ("  →  ", {"color": MUTE}), ("10,028", {})]], size=40, bold=True, latin=NUM)
pill(s, L, 690, 170, 48, "15/15 通过", BLUE, "#FFFFFF", size=14)
T(s, L + 190, 690, 460, 48, "总分 131,864 → 139,972", size=17, anchor="m")
T(s, L, 790, 640, 120, "冻结开发最佳候选，在从没见过的 15 个用例上只测一次，结果不回流。", size=15, color=INK2, spacing=1.3)
rect(s, 822, 298, 1022, 576, RULE)
pic(s, A("split.png"), 823, 299, 1020, 574)
for x, lab, v, c in [(846, "初始程序 · 本用例能耗", "1,158", INK), (1350, "最终版本 · 本用例能耗", "649", BLUE)]:
    rect(s, x, 318, 470, 56, CARD, radius=8)
    T(s, x + 18, 318, 450, 56, [[(lab + "  ", {"color": INK2, "size": 14}), (v, {"color": c, "bold": True, "size": 22})]], size=14, anchor="m", wrap=False)
T(s, 822, 890, 1022, 40, "同一个用例上两个程序同步回放（截图为回放中途），能耗为回放结束时的总数", size=12, color=MUTE)

# ============================================================== 16 routing (compressed)
s = new(hi("谁来决定下一步，", ("同样影响结果",)), "实测 · 调度对照",
        notes="左：四组路由组合，同一预算，各 1 次。仅动作 Decisions 得分最高；双 Decisions 全程没升级大模型、主动提前结束，用时少七成但提升只剩 0.5%。右：补充实验在两台机器上各跑四种策略；固定小模型没有提升，有大模型参与的六格都在 5.4% 到 6.4%。每格只有一次，不宣称稳定领先。\n\n来源：docs/research/native-routing/20261114/RESULTS.md · docs/research/onehour-20261114/README.md")
T(s, L, 290, 600, 34, "四组路由 · 同预算 · 相对 c0 的 final 提升", size=14, bold=True, color=MUTE)
T(s, 830, 290, 200, 34, "用时", size=14, bold=True, color=MUTE, align="r")
for i, (nm, k, g, sec) in enumerate([("LLM / rule", "基线", 5.970, 392), ("Decisions / rule", "仅动作", 6.149, 389), ("LLM / Decisions", "仅模型", 5.836, 390), ("Decisions / Decisions", "双决策", 0.513, 113)]):
    y = 345 + i * 110
    mono(s, L, y, 330, 34, nm, size=12, bold=True, color=ORANGE if i == 1 else INK)
    T(s, L, y + 36, 300, 30, k, size=12, color=MUTE)
    w = g / 7 * 330
    rect(s, 420, y + 8, w, 46, ORANGE if i == 1 else BLUE)
    T(s, 430 + w, y + 6, 160, 50, f"+{g:.2f}%", size=18, bold=True, anchor="m", color=ORANGE if i == 1 else INK)
    T(s, 830, y + 6, 200, 50, f"{sec} 秒", size=18, bold=True, anchor="m", align="r", color=ORANGE if i == 3 else INK)
for i, (v, d) in enumerate([("2.26%", "决策层费用占比\n（路由 $0.0068 / 已知 $0.3006）"), ("1.34 s", "单次动作决策耗时中位数\n（14 次）"), ("−71%", "全权交给决策模型的用时\n提升却只剩 +0.51%")]):
    x = L + i * 330
    T(s, x, 790, 320, 70, v, size=34, bold=True, color=BLUE, latin=NUM)
    T(s, x, 862, 320, 70, d, size=12, color=INK2, spacing=1.15)
line(s, 1080, 290, 1080, 960, RULE, 1.5)
T(s, 1120, 290, 720, 34, "双机补充对照 · 每台每策略 1 次", size=14, bold=True, color=MUTE)
hrows = [["策略", "desktop", "laptop"], ["固定小模型", "+0.00%", "+0.00%"], ["固定大模型", "+5.73%", "+5.50%"], ["规则自适应", ("+6.37%", {"bold": True, "color": BLUE}), "+5.43% †"],
         ["Decisions 动作路由", "+5.82%", ("+6.34%", {"bold": True, "color": BLUE})]]
table(s, 1120, 340, [330, 195, 199], hrows, rh=70, size=15, aligns=["l", "r", "r"])
T(s, 1120, 710, 724, 220, ["强模型参与是提升的前提；混合策略接近固定大模型，胜负有波动。", "† laptop 规则自适应因 API 超时结束；8 份交付候选均通过 final。"], size=14, color=INK2, spacing=1.3, space_after=10)

# ============================================================== 17 memory (compressed)
s = new(hi("同样的模型，", ("换上经验快照",), "之后"), "实测 · 经验记忆",
        notes="经验记忆的两组受控对照：D 是封存留出集，v19 快照让 18 次运行全部零模型调用直接交付，加速比中位数从 1.20 到 1.73。S 是在线任务流，新任务族第一次出现时交给大模型，之后同类任务全部复用，大模型请求从 27 降到 6。\n\n来源：docs/archive/memory-learning-results.md · README 核心实测成果第 3 节")
B_ = {"bold": True, "color": BLUE}
mrows = [["指标", "D 封存留出 · v0 → v19", "S 在线任务流 · 不带记忆 → 带记忆"],
         ["达标 / 运行", [[("15/18 → ", {}), ("18/18", B_)]], "36/36 → 36/36"],
         ["最终加速比中位数", [[("1.20× → ", {}), ("1.73×", B_)]], "1.86× → 1.86×"],
         ["大模型（GPT）请求", [[("7 → ", {}), ("0", B_)]], [[("27 → ", {}), ("6", B_)]]],
         ["零模型调用的运行", [[("0/18 → ", {}), ("18/18", B_)]], [[("9/36 → ", {}), ("30/36", B_)]]],
         ["模型费用（估算）", [[("$0.376 → ", {}), ("$0.000", B_)]], [[("$0.402 → ", {}), ("$0.086", B_)]]],
         ["总耗时", [[("1782 s → ", {}), ("669 s", B_)]], [[("1486 s → ", {}), ("1064 s", B_)]]]]
table(s, L, 290, [520, 624, 624], mrows, rh=82, size=20)
T(s, L, 880, W, 80, "D 批所用 v19 来自两轮 A 批学习（学习费用另计 $0.455）；S 流中新任务族首次出现时两侧都交给大模型，之后同类任务 30/30 零调用。", size=13, color=MUTE, spacing=1.3)

# ============================================================== 18 evolution
s = new(hi("用同样的严格对照，", ("改进系统本身",)), "实测 · 系统研究自己",
        notes="我们用同样的严格对照来改进系统本身。v1 发现文字经验让加速比变低；v2 改存可执行程序并先复验；v3 加上分流器和在线记忆；最后把同一套闭环接到外部基准上。每一步都是先封存测试集再动手。\n\n来源：docs/archive/memory-learning-results.md · docs/research/README.md")
line(s, L, 380, R, 380, RULE, 3)
for i, (v, h, a_, b_) in enumerate([("v1", "只存文字经验", "更省，但留出集加速比 1.41× → 1.29×；好程序被小模型重写一遍", "诊断：达标即停，经验不能直接运行"),
                                    ("v2", "可执行经验 + 先复验", "D 封存留出：15/18 → 18/18，1.20× → 1.73×，零模型调用", "学习运行以已知最佳为起点继续超越"),
                                    ("v3", "分流器 + 在线记忆", "S 任务流：GPT 请求 27 → 6，后续 30/30 零调用", "新任务族直接交给大模型，之后复用"),
                                    ("native", "外部基准 + 路由消融", "ahc026 −44.7% · PageRank 25.0× · 四组路由对照", "动作 × 模型解耦，决策开销单独记账")]):
    x = L + i * 450
    hot = i == 3
    T(s, x, 300, 400, 50, v, size=22, bold=True, color=ORANGE, font=MONO, latin=MONO)
    oval(s, x + 14, 380, 14, BLUE if hot else BG, line=BLUE, line_w=4)
    rect(s, x, 430, 420, 460, BLUE_L if hot else CARD, radius=12, line=BLUE if hot else RULE, line_w=2 if hot else 1.5)
    T(s, x + 28, 456, 370, 50, h, size=19, bold=True, color=BLUE if hot else INK)
    T(s, x + 28, 524, 370, 170, a_, size=16, color=INK2, spacing=1.35)
    line(s, x + 28, 710, x + 392, 710, RULE, 1.5, dash="dash")
    T(s, x + 28, 726, 370, 140, "→ " + b_, size=16, bold=True, color=BLUE, spacing=1.3)
T(s, L, 920, W, 40, "每一版都先封存新的留出集，再动手实现；结论只在封存集上测一次", size=14, color=MUTE)

# ============================================================== 19 algotune + benchmarks
s = new(hi("同一套闭环，", ("换一个优化对象",)), "实测 · 函数级优化与支持的基准",
        notes="同一套闭环也能做函数级优化：PageRank 绕过 NetworkX 图对象，直接用 SciPy 稀疏矩阵做幂迭代，快了 25 倍；一维卷积在误差容限内改用 float32 实数 FFT，快了 2.67 倍。右边是通过任务与评测 adapter 接入的五类基准。\n\n来源：README 核心实测成果第 2 节 · README「支持的 Benchmark 与任务族」")
T(s, L, 290, 840, 34, "AlgoTune · 固定 gpt-6.1-sol · 每项 180 秒 / 5 次请求", size=14, bold=True, color=MUTE)
for i, (t_, st_, v, how) in enumerate([("PageRank", "feedback", 25.04, "稀疏矩阵直接幂迭代 · 11.15 → 0.45 ms"), ("PageRank", "independent", 23.05, "邻接表直接建稀疏表示"),
                                       ("一维卷积", "independent", 2.67, "float32 实数 FFT · 1.12 → 0.42 ms"), ("一维卷积", "feedback", 1.30, "实数 FFT 批处理与缓冲复用")]):
    y = 345 + i * 140
    T(s, L, y, 200, 36, t_, size=16, bold=True)
    mono(s, L, y + 36, 200, 30, st_, size=12, color=MUTE)
    w = v / 26 * 470
    rect(s, 290, y + 6, max(w, 6), 48, ORANGE if i == 0 else BLUE)
    T(s, 300 + max(w, 6), y + 2, 160, 56, f"{v:.2f}×", size=20, bold=True, anchor="m", color=ORANGE if i == 0 else INK)
    T(s, 290, y + 62, 600, 34, how, size=12, color=INK2)
line(s, 960, 290, 960, 960, RULE, 1.5)
T(s, 1000, 290, 840, 34, "五类基准，各有独立裁判", size=14, bold=True, color=MUTE)
for i, (n_, scope, judge) in enumerate([("自建任务族", "分组聚合 · 访问日志 · 区间合并；43 个冻结任务包", "Docker 沙箱 · 7 个规则用例 · 交替计时"),
                                        ("ALE-Bench", "AtCoder 启发式 ahc024、ahc026", "独立容器运行上游 Rust vis 裁判"),
                                        ("AlgoTune", "convolve_1d、pagerank", "上游 is_solution 校验 + 配对交替计时"),
                                        ("EffiBench-X", "623 道 Python 题（io 与 functional）", "独立容器校验，沿用上游输出归一化"),
                                        ("KernelBench", "Level 1 方阵乘法（PyTorch / CUDA C++）", "远端 GPU Docker worker · CUDA events")]):
    y = 340 + i * 122
    T(s, 1000, y, 260, 40, n_, size=17, bold=True, color=BLUE)
    T(s, 1000, y + 40, 844, 34, scope, size=14)
    T(s, 1000, y + 74, 844, 34, judge, size=13, color=INK2)
    line(s, 1000, y + 112, R, y + 112, RULE, 1)

# ============================================================== 20 console
s = new(hi("过程看得见：", ("Web 控制台",)), "控制台",
        notes="Web 控制台：总览、研究对照、运行详情。每一步的假设、判定、用量都能在界面上看到。\n\n来源：frontend/docs/screenshots · uv run quotacrux serve")
for x, y, w, f, cap in [(L, 300, 860, "console-home.png", "总览：批次、轮次、候选、用量与费用"), (984, 300, 860, "console-research.png", "研究对照：各策略逐轮结果")]:
    h = w * 900 / 1440
    rect(s, x - 2, y - 2, w + 4, h + 4, RULE)
    pic(s, A(f), x, y, w, h)
    T(s, x, y + h + 18, w, 40, cap, size=15, bold=True, align="c")
T(s, L, 920, W, 40, "uv run quotacrux serve → http://127.0.0.1:8000", size=13, color=MUTE, align="c", font=MONO, latin=MONO)

# ============================================================== 21 advantages
s = new(hi("同一个系统里的", ("受控对比",)), "分析 · 优势对比",
        notes="对比的每一列都来自我们自己的受控实验，而不是对其他产品的推测。各列口径不同（ahc026 得分提升 / 自建任务加速比），只在各自实验内比较。\n\n来源：双机补充实验、v1 文字经验消融、S 任务流、D 留出")
arows = [["", "固定小模型", "固定大模型", "小模型 + 文字经验", "QuotaCrux"],
         ["质量", "0% 提升", "+5.50% ~ +5.73%", "加速比 1.41× → 1.29×", "+5.82% ~ +6.37% · D 留出 1.20× → 1.73×"],
         ["大模型调用", "0", "每轮 6–7 次", "升级 11 → 5 次", "S 流 27 → 6 · D 留出 7 → 0"],
         ["正确性由谁判", "同一外部裁判", "同一外部裁判", "同一外部裁判", "外部裁判 · 模型不自评"],
         ["经验能否直接用", "—", "—", "需要重新写一遍", "已验证程序先复验，18/18 零调用交付"],
         ["新问题", "原地打转", "每次都付费", "没有相近经验", "分流器直接交给大模型，之后复用"],
         ["回退与审计", "—", "—", "—", "不可变快照 · 全量账本 · 复现包"]]
table(s, L, 290, [260, 250, 290, 330, 638], arows, rh=88, size=15, hot_col=4, aligns=["l", "c", "c", "c", "c"])
T(s, L, 920, W, 40, "各列口径不同（ahc026 得分提升 / 自建任务加速比），只在各自实验内比较，不做跨基准平均。", size=12, color=MUTE)

# ============================================================== 22 boundaries
s = new(hi("说清楚：", ("证明了什么，没证明什么",)), "分析 · 边界",
        notes="我们把已经证明的和尚未证明的分开讲。路由策略每组只跑了一次，不宣称稳定领先；费用总额因为超时缺失用量而未知；经验只在同族内复用。\n\n来源：docs/boundaries.md · docs/research/onehour-20261114/README.md · project-overview 第 7 节")
for i, (head, c, items) in enumerate([("已有直接证据", BLUE, ["强模型参与对 ahc026 有效：六格提升 5.43%–6.37%", "可执行经验让封存留出集全面变好（D：18/18、1.73×、零调用）", "在线记忆让后续同类任务 30/30 零调用交付",
                                                            "决策层开销小：中位 1.34 秒，费用占比 2.26%", "交付候选全部通过隐藏测试；复现包复核与记录值吻合"]),
                                     ("尚未证明 · 限制", ORANGE, ["路由策略每组 1 次：Decisions 相对规则一胜一负，不宣称稳定领先", "双 Decisions 的“快速档位”未复现", "多个大模型请求超时缺用量，费用总额保持未知",
                                                            "经验只在同族内复用，跨任务族不迁移", "计时在一台 Mac 上，小输入任务固定开销约占一半"])]):
    x = L + i * 904
    rect(s, x, 300, 10, 40, c)
    T(s, x + 26, 300, 800, 40, head, size=22, bold=True, color=c, anchor="m")
    for j, it in enumerate(items):
        y = 372 + j * 118
        T(s, x, y, 840, 104, it, size=17, spacing=1.25, color=INK if i == 0 else INK2, anchor="m")
        line(s, x, y + 110, x + 840, y + 110, RULE, 1)

# ============================================================== 23 summary
s = new(notes="总结：QuotaCrux 在预算里做研究。小模型干主力，关键节点请大模型；模型只提出想法，裁判决定结果；验证过的程序沉淀为可回退的经验。欢迎扫码查看代码、报告和视频。")
T(s, L, 150, 1300, 220, [[("在预算里做研究，", {})], [("每一步都有据可查", {"color": BLUE})]], size=50, bold=True, spacing=1.15)
line(s, L, 432, L + 340, 432, ORANGE, 6)
for i, (k, v) in enumerate([("分工", "小模型干主力\n关键节点请大模型"), ("验证", "模型提出想法\n裁判决定结果"), ("进化", "验证过的程序\n沉淀为可回退快照")]):
    x = L + i * 440
    T(s, x, 490, 400, 34, k, size=15, bold=True, color=ORANGE)
    T(s, x, 532, 400, 120, v, size=22, bold=True, spacing=1.25)
    if i:
        line(s, x - 30, 490, x - 30, 650, RULE, 1.5)
for i, (n_, d) in enumerate([("−44.7%", "ahc026 隐藏测试总能耗"), ("25.0×", "PageRank 函数级提速"), ("18/18", "封存留出零调用交付")]):
    x = L + i * 440
    T(s, x, 720, 400, 90, n_, size=40, bold=True, color=ORANGE if i == 0 else BLUE, latin=NUM)
    T(s, x, 812, 400, 40, d, size=14, color=INK2)
rect(s, 1494, 300, 350, 350, CARD, radius=12, line=RULE, line_w=1.5)
pic(s, A("qr.png"), 1519, 325, 300, 300)
T(s, 1494, 664, 350, 40, "扫码查看代码、报告与视频", size=14, color=INK2, align="c")
T(s, L, 940, W, 40, "github.com/bohack-2026-hw/QuotaCrux　·　docs/video/QuotaCrux-showcase.mp4", size=14, color=MUTE, latin=NUM)

assert len(SLIDES) == TOTAL, len(SLIDES)
prs.core_properties.title = "QuotaCrux 枢决 · 技术演示"
prs.save(OUT)
print(f"{len(SLIDES)} slides -> {OUT}")
