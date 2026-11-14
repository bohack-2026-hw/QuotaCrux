"""Builds docs/presentation/QuotaCrux.pptx: native PowerPoint shapes and text on a 1920 x 1080 px grid,
morph transitions between slides and auto-playing entrance animations on every slide.

    uv run --with python-pptx --with lxml --with pillow python build.py [out.pptx]
Numbers mirror the sources listed in each slide's speaker notes.
"""
import os
import sys

from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Emu

from pptkit import CJK, MONO, NUM, Timeline, line, oval, pic, rect, set_bg, set_transition, shape, text

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "QuotaCrux.pptx")
A = lambda n: os.path.join(HERE, "assets", n)  # noqa: E731

BG, CARD = "#F7F6F1", "#FFFFFF"
INK, INK2, MUTE, RULE = "#111111", "#4A4A4F", "#8C8A85", "#D9D6CD"
BLUE, BLUE_L, BLUE_M = "#2E49D6", "#E9EDFC", "#9AA9EE"
ORANGE, ORANGE_L = "#F0532D", "#FDECE6"
GREY_BAR = "#C9C6BE"
L, R, W = 76, 1844, 1768
SECTIONS = ["为什么", "怎么做", "效果", "总结"]

# a quiet paper background (slide background, so morph never touches it)
PAPER = os.path.join(HERE, "build", "paper-flat.png")
os.makedirs(os.path.dirname(PAPER), exist_ok=True)
Image.new("RGB", (192, 108), BG).save(PAPER)
# bohack.top lockup, in its own CSS px: mark (0,0,56,38) and text block (70,3.2,101,31.6); 171 x 38 overall


def imgshape(s, path, x, y, w, h, name=None):
    """A rectangle filled with an image: animates like any shape (WPS drops pictures that carry entrance effects)."""
    from pptx.oxml.ns import qn
    from pptkit import frag
    shp = rect(s, x, y, w, h, None, name=name)
    _, rid = s.part.get_or_add_image_part(path)
    sp = shp._element.spPr
    sp.remove(sp.find(qn("a:noFill")))
    sp.find(qn("a:prstGeom")).addnext(frag(f'<a:blipFill rotWithShape="1"><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></a:blipFill>'))
    return shp


def lockup(s, x, y, k, shapes=False):
    """BoHack mark + text at scale k; shared names let morph carry them from the intro to the header."""
    f = imgshape if shapes else pic
    return [f(s, A("bohack-mark.png"), x, y, 56 * k, 38 * k, name="!!bhmark"),
            f(s, A("bohack-text.png"), x + 70 * k, y + 3.2 * k, 101 * k, 31.6 * k, name="!!bhtext")]


HDR_K = 1.2  # header lockup: 205 x 46 px, centred on y = 56

prs = Presentation()
prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)
BLANK = prs.slide_layouts[6]
TLS = []


def T(s, x, y, w, h, paras, size=16, **kw):
    if isinstance(paras, str) and "\n" in paras:
        paras = paras.split("\n")
    elif isinstance(paras, str) and len(paras) <= 16:
        kw.setdefault("wrap", False)
    return text(s, x, y, w, h, paras, size=size, **kw)


def mono(s, x, y, w, h, paras, size=14, **kw):
    return text(s, x, y, w, h, paras, size=size, font=MONO, latin=MONO, **kw)


def hi(*parts):
    """Title runs: plain strings in ink, (text,) tuples in blue."""
    return [[(p[0], {"color": BLUE}) if isinstance(p, tuple) else (p, {}) for p in parts]]


def new(section=None, title=None, kicker=None, notes=""):
    s = prs.slides.add_slide(BLANK)
    set_bg(s, PAPER)
    set_transition(s, "morph", 900)
    tl = Timeline(s)
    TLS.append(tl)
    if section is not None:
        # header: brand left, section route right; same names on every slide so morph keeps them still
        lockup(s, L, 56 - 19 * HDR_K, HDR_K)
        line(s, 304, 38, 304, 74, RULE, 2, name="!!divider")
        T(s, 322, 32, 400, 48, [[("QuotaCrux", {"color": BLUE, "bold": True}), ("  枢决", {"color": INK, "bold": True})]], size=17, anchor="m", name="!!brand")
        line(s, L, 88, R, 88, INK, 2, name="!!rule")
        x0, labw = 1250, [84, 84, 56, 56]
        for i, nm in enumerate(SECTIONS):
            on = i == section
            cx = x0 + 10 + i * 160
            oval(s, cx, 56, 9 if on else 6, BLUE if on else BG, line=BLUE if on else MUTE, line_w=2, name=f"!!navdot{i}")
            T(s, cx + 16, 36, 130, 40, nm, size=14, bold=on, color=BLUE if on else MUTE, anchor="m", name=f"!!nav{i}")
            if i < 3:
                line(s, cx + 22 + labw[i], 56, cx + 160 - 16, 56, RULE, 2, name=f"!!navseg{i}")
    if kicker:
        tl.fade(T(s, L, 116, 1400, 36, kicker, size=15, color=ORANGE, bold=True, name="hdr_kicker"), 0, 500)
    if title:
        tl.rise(T(s, L, 152, W, 84, title, size=32, bold=True, name="hdr_title"), 80, 700, off=0.02)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s, tl


def each(tl, shapes, kind, delay, dur=600, step=0, **kw):
    for i, sh in enumerate(shapes):
        tl.add(sh, kind, delay + i * step, dur, **kw)
    return tl


def box(s, x, y, w, h, title, sub=None, hot=False, ts=17, ss=12, fill=CARD):
    out = [shape(s, MSO_SHAPE.SNIP_1_RECTANGLE, x, y, w, h, fill, line=BLUE if hot else "#BDBAB2", line_w=3 if hot else 1.5, adj=[0.12])]
    paras = [[(title, {"size": ts, "bold": True, "color": BLUE if hot else INK})]]
    if sub:
        paras.append([(sub, {"size": ss, "bold": False, "color": INK2})])
    out.append(T(s, x + 6, y, w - 12, h, paras, size=ts, align="c", anchor="m", spacing=1.15, wrap=False))
    return out


def card2(s, x, y, w, h, k, v, hot=False, ks=14, vs=17):
    """Rounded card with a small label over a value, vertically centred."""
    return [rect(s, x, y, w, h, BLUE_L if hot else CARD, radius=10, line=BLUE if hot else RULE, line_w=1.5),
            T(s, x + 20, y, w - 40, h, [[(k, {"size": ks, "color": INK2, "bold": False})], [(v, {"size": vs, "bold": True, "color": BLUE if hot else INK})]],
              size=vs, anchor="m", spacing=1.2, wrap=False)]


def arrow(s, x1, y1, x2, y2, color=INK2, w=2, dash=None):
    return line(s, x1, y1, x2, y2, color, w, dash=dash, arrow=True)


def pill(s, x, y, w, h, label, fill, color, size=12, font=CJK):
    return [rect(s, x, y, w, h, fill, radius=h / 2),
            T(s, x, y, w, h, label, size=size, color=color, bold=True, align="c", anchor="m", font=font, latin=MONO if font == MONO else NUM)]


def stat(s, x, y, w, label, value, desc, color=BLUE, vs=60):
    return [T(s, x, y, w, 36, label, size=15, bold=True, color=color),
            T(s, x, y + 36, w, vs * 2.6, value, size=vs, bold=True, color=color, latin=NUM, anchor="m"),
            T(s, x, y + 44 + vs * 2.6, w, 90, desc, size=15, color=INK2, spacing=1.2)]


def table(s, x, y, cols, rows, rh=64, head_size=13, size=15, hot_col=None, aligns=None):
    """cols: widths; rows[0] is the header. Returns ([header shapes], [[row shapes]...], hot band or None)."""
    tw = sum(cols)
    band = rect(s, x + sum(cols[:hot_col]), y, cols[hot_col], rh * len(rows), BLUE_L) if hot_col is not None else None
    groups = []
    for r, row in enumerate(rows):
        cx, yy, g = x, y + r * rh, []
        for c, cell in enumerate(row):
            al = (aligns or ["l"] * len(cols))[c]
            if r == 0:
                g.append(T(s, cx + 12, yy, cols[c] - 24, rh, cell, size=head_size, color=BLUE if c == hot_col else MUTE, bold=True, anchor="m", align=al))
            else:
                st = dict(size=size, anchor="m", align=al, spacing=1.1)
                if c == 0:
                    st.update(bold=True)
                if isinstance(cell, tuple):
                    cell, extra = cell
                    st.update(extra)
                g.append(T(s, cx + 12, yy, cols[c] - 24, rh, cell, **st))
            cx += cols[c]
        g.append(line(s, x, yy + rh, x + tw, yy + rh, INK if r == 0 else RULE, 2 if r == 0 else 1))
        groups.append(g)
    return groups[0], groups[1:], band


B_ = {"bold": True, "color": BLUE}


def autoplay(slide, spid, ms):
    """Timing that starts a video as soon as the slide shows and plays it once."""
    from pptkit import frag
    from pptx.oxml.ns import qn
    old = slide._element.find(qn("p:timing"))
    if old is not None:
        slide._element.remove(old)
    nav = ('<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
           '<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>')
    xml = (f'<p:timing><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>'
           f'<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>'
           f'<p:par><p:cTn id="3" fill="hold"><p:stCondLst><p:cond delay="indefinite"/><p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond></p:stCondLst><p:childTnLst>'
           f'<p:par><p:cTn id="4" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
           f'<p:par><p:cTn id="5" presetID="1" presetClass="mediacall" presetSubtype="0" fill="hold" nodeType="afterEffect"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
           f'<p:cmd type="call" cmd="playFrom(0.0)"><p:cBhvr><p:cTn id="6" dur="{ms}" fill="hold"/><p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cBhvr></p:cmd>'
           f'</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par>'
           f'</p:childTnLst></p:cTn>{nav}</p:seq>'
           f'<p:video><p:cMediaNode vol="0"><p:cTn id="7" fill="hold" display="0"><p:stCondLst><p:cond delay="indefinite"/></p:stCondLst></p:cTn>'
           f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cMediaNode></p:video>'
           f'</p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>')
    el = frag(xml)
    ext = slide._element.find(qn("p:extLst"))
    if ext is not None:
        ext.addprevious(el)
    else:
        slide._element.append(el)

# ============================================================== 1 cover
s, tl = new(notes="开场（先自动播放 BoHack 开场动画）：QuotaCrux（枢决）是一个在预算里做研究的 Agent。三个关键词：动作与模型解耦路由、隔离沙箱里的独立裁判、可回退的可执行经验快照。")
# the bohack.top opening, captured frame by frame from the site, plays on the cover itself (once): the pen draws
# the logo, it settles top-left exactly where every later slide keeps it, and the cover builds on top of it.
mov = s.shapes.add_movie(A("bohack-intro.mp4"), 0, 0, prs.slide_width, prs.slide_height, poster_frame_image=A("bohack-intro-poster.png"), mime_type="video/mp4")
tl.add(mov, "play", 0, 2733)
# the same lockup appears over the video's last frame the moment it ends, so nothing changes on screen when the
# player drops the finished video back to its blank poster
for sh in lockup(s, L, 56 - 19 * HDR_K, HDR_K, shapes=True):
    tl.fade(sh, 2700, 60)
INTRO_MS = 2800
t1 = T(s, 1144, 32, 700, 48, "倍漾量化 · Research Agent 赛道", size=15, align="r", anchor="m")
rule = line(s, L, 88, R, 88, INK, 2, name="!!rule")
brand = T(s, 60, 120, 1300, 240, "QuotaCrux", size=118, bold=True, color=BLUE, latin=NUM, name="!!brand")
cn = T(s, 76, 360, 400, 170, "枢决", size=80, bold=True)
tag = T(s, 420, 420, 900, 60, "预算感知的 Research Agent", size=24, color=INK2)
slogan = T(s, 76, 560, 1400, 96, [[("把有限预算，用在", {}), ("关键节点", {"color": BLUE})]], size=40, bold=True)
uline = line(s, 76 + 8 * 80, 666, 76 + 12 * 80, 666, ORANGE, 5)
tl.fade(t1, 0, 400).wipe(rule, 0, 700)
tl.rise(brand, 150, 800, off=0.04)
tl.fade(cn, 900, 600).rise(tag, 1000, 600).rise(slogan, 1200, 700).wipe(uline, 1700, 500)
steps = ["规划", "取证", "假设", "实验", "验证", "修正"]
for i, st_ in enumerate(steps):
    x = L + i * 300
    g = box(s, x, 760, 200, 96, st_, hot=(st_ == "验证"), ts=22)
    each(tl, g, "pop", 1900 + i * 160, 450)
    if i < 5:
        tl.wipe(arrow(s, x + 210, 808, x + 290, 808, BLUE, 2.5), 2000 + i * 160, 300)
fb = [line(s, L + 100, 866, L + 100, 902, ORANGE, 2.5), line(s, L + 100, 902, L + 5 * 300 + 100, 902, ORANGE, 2.5), arrow(s, L + 5 * 300 + 100, 902, L + 5 * 300 + 100, 866, ORANGE, 2.5)]
fbt = T(s, L + 560, 908, 700, 40, "验证反馈 → 更新假设与预算", size=16, color=ORANGE, align="c", bold=True)
tl.wipe(fb[0], 2900, 200, direction="up").wipe(fb[1], 3000, 600).wipe(fb[2], 3550, 200, direction="down").fade(fbt, 3600, 500)
pts = [(1380, 600), (1500, 600), (1500, 470), (1640, 470), (1640, 400), (1760, 400), (1760, 360), (1844, 360)]
for k, ((x1, y1), (x2, y2)) in enumerate(zip(pts, pts[1:])):
    tl.wipe(line(s, x1, y1, x2, y2, BLUE, 6), 1300 + k * 120, 200, direction="left" if y1 == y2 else "down")
for k, (x, y) in enumerate([(1380, 600), (1500, 470), (1640, 400), (1760, 360)]):
    tl.pop(oval(s, x, y, 12, BG, line=BLUE, line_w=4), 1350 + k * 240, 400)
tl.pop(oval(s, 1844, 360, 14, ORANGE), 2200, 500)

# ============================================================== 2 numbers
s, tl = new(0, hi("五个数字看懂 ", ("QuotaCrux",)), "一页看懂",
            notes="先给结论。最大的数字来自 AtCoder 启发式竞赛真题 ahc026：15 个隐藏用例总能耗降 44.7%。其余四个数字分别代表函数级优化、经验复用、在线任务流和交付可靠性。\n\n来源：docs/research/native-routing/20261114 · docs/archive/memory-learning-results.md · README 核心实测成果")
lab = T(s, L, 300, 840, 36, "ALE-Bench ahc026 搬箱子 · 15 个隐藏用例总能耗", size=16, bold=True, color=ORANGE)
big = T(s, L - 6, 336, 900, 290, "−44.7%", size=110, bold=True, color=ORANGE, latin=NUM, anchor="m")
tl.fade(lab, 300, 500).zoom(big, 400, 700)
for i, (lb, v, w, c) in enumerate([("初始程序", "18,136", 560, GREY_BAR), ("QuotaCrux", "10,028", 310, BLUE)]):
    y = 630 + i * 74
    a1 = T(s, L, y, 170, 50, lb, size=16, anchor="m", bold=(i == 1))
    b1 = rect(s, L + 180, y + 10, w, 30, c)
    v1 = T(s, L + 180 + w + 16, y, 200, 50, v, size=19, bold=True, anchor="m", latin=NUM)
    tl.fade(a1, 900 + i * 250, 400).wipe(b1, 950 + i * 250, 700).fade(v1, 1500 + i * 250, 400)
p_ = pill(s, L, 800, 170, 48, "15/15 通过", BLUE, "#FFFFFF", size=14)
pt = T(s, L + 190, 800, 600, 48, "总分 131,864 → 139,972", size=18, anchor="m")
each(tl, p_, "pop", 1900, 450).fade(pt, 2000, 500)
for ln in [line(s, 960, 300, 960, 940, RULE, 1.5), line(s, 1000, 625, R, 625, RULE, 1.5), line(s, 1422, 300, 1422, 940, RULE, 1.5)]:
    tl.fade(ln, 600, 600)
cells = [("AlgoTune · 函数级", "25.0×", "PageRank 提速\n稀疏矩阵直接幂迭代", BLUE), ("D 封存留出 · 经验复用", "18/18", "零模型调用直接交付\n加速比 1.20× → 1.73×", BLUE),
         ("S 在线任务流 · 分流器", "−78%", "大模型请求 27 → 6 次\n费用 $0.402 → $0.086", ORANGE), ("ALE 正式消融 · 交付", "15/15", "交付候选全部通过\n隐藏测试", BLUE)]
for i, (lb, v, d, c) in enumerate(cells):
    g = stat(s, 1000 + (i % 2) * 462, 310 + (i // 2) * 345, 430, lb, v, d, color=c, vs=54)
    each(tl, g, "rise", 900 + i * 220, 600, 60, off=0.03)

# ============================================================== 3 problem
s, tl = new(0, hi("研究型 Agent 贵在一次又一次的", ("“再试一次”",)), "问题",
            notes="研究型 Agent 常见两种低效：一直用大模型试错，钱花在重复改写上；或者只用小模型、只存文字心得，原地打转。两条证据都来自我们自己的受控实验：固定大模型每轮 6–7 次大模型请求；固定小模型两台机器都没有提升，文字经验让加速比 1.41× 降到 1.29×。\n\n来源：docs/research/onehour-20261114 · docs/archive/memory-learning-results.md 第 3 节")
for i, (k, h, items, ev_n, ev_t) in enumerate([
        ("低效 A", "一直让大模型盲目试错", ["每一次改写都要付费、要等待", "预算消耗在重复改写和无效分析上", "没有外部裁判，“看起来变好了”无法验证"], "6–7 次", "固定大模型每轮的大模型请求"),
        ("低效 B", "弱模型 + 文字经验原地打转", ["小模型在复杂约束下难以突破", "只存文字心得：好程序要重新写一遍", "达标即停，更好的方案不会被再用"], "0%", "固定小模型的得分提升")]):
    x, d = L + i * 904, 300 + i * 400
    g = [T(s, x, 300, 800, 34, k, size=16, bold=True, color=ORANGE), T(s, x, 342, 840, 60, h, size=27, bold=True),
         T(s, x, 426, 840, 200, ["·  " + t for t in items], size=18, color=INK2, space_after=10)]
    each(tl, g, "rise", d, 600, 100, off=0.03)
    ln = line(s, x, 650, x + 840, 650, RULE, 1.5)
    n_ = T(s, x, 672, 320, 96, ev_n, size=46, bold=True, color=ORANGE, latin=NUM)
    e_ = T(s, x + 330, 672, 510, 96, ev_t, size=17, color=INK2, anchor="m")
    tl.wipe(ln, d + 500, 600).pop(n_, d + 700, 500).fade(e_, d + 800, 500)
band = rect(s, L, 830, W, 120, ORANGE_L)
bar_ = rect(s, L, 830, 10, 120, ORANGE)
q = T(s, L + 50, 830, 1700, 120, "有限预算下：何时思考、何时实验、何时升级模型、何时停止？", size=28, bold=True, anchor="m")
tl.wipe(band, 1600, 700).fade(bar_, 1600, 300).rise(q, 1900, 700, off=0.02)

# ============================================================== 4 inspiration
s, tl = new(0, hi("灵感来源：把", ("研究决策",), "独立出来"), "灵感来源",
            notes="三个灵感：DeepSeek SuperAgent 的 Router/Worker 分层；中间是赛题的 Built for Better——会自我进化的智能；右边是 Jev 与 OpenAI Decisions 的类型化决策。\n\n来源：README「设计定位与灵感」 · github.com/deepseek-ai/dsh-superagent-prototype · docs.typesafe.ai")
cards = [(L, 310, 540, 640, False, "DeepSeek SuperAgent", "编排与执行分离", "Router 负责交互与任务分派，Worker 在独立会话和工作目录中执行。", "拆成三个边界：动作、模型、任务与评测 adapter", 700),
         (L + 590, 280, 588, 700, True, "BUILT FOR BETTER", "会自我进化的智能", "每次沙箱评测的真实反馈，都沉淀为可检验、可对比、可回退的资产。", "下一次运行更快、更省、更稳——而且能拿数据证明", 300),
         (L + 1228, 310, 540, 640, False, "Jev · OpenAI Decisions", "类型化的小决策", "把“状态 + 类型化问题”映射为选择及概率；gpt-6-luna 已接入。", "下一步做什么交给决策模型；与生成共用一份预算", 900)]
for x, y, w, h, bigc, tg, head, idea, to, d in cards:
    fg, fg2 = ("#FFFFFF", "#DCE2FB") if bigc else (INK, INK2)
    g = [rect(s, x, y, w, h, BLUE if bigc else CARD, radius=14, line=None if bigc else RULE, line_w=1.5),
         T(s, x + 40, y + 40, w - 80, 34, tg, size=18 if bigc else 15, bold=True, color="#FFD2C4" if bigc else ORANGE, latin=NUM),
         T(s, x + 40, y + 90, w - 80, 70, head, size=30 if bigc else 26, bold=True, color=fg),
         T(s, x + 40, y + 190, w - 80, 200, idea, size=20 if bigc else 17, color=fg2, spacing=1.3),
         line(s, x + 40, y + h - 220, x + w - 40, y + h - 220, "#FFFFFF" if bigc else RULE, 1.5, alpha=0.5 if bigc else None),
         T(s, x + 40, y + h - 200, w - 80, 34, "在 QuotaCrux 中", size=14, bold=True, color="#FFD2C4" if bigc else BLUE),
         T(s, x + 40, y + h - 160, w - 80, 140, to, size=20 if bigc else 17, bold=True, color=fg, spacing=1.3)]
    tl.add(g[0], "zoom" if bigc else "rise", d, 700, **({} if bigc else {"off": 0.04}))
    each(tl, g[1:], "rise" if not bigc else "fade", d + 250, 600, 80, **({"off": 0.02} if not bigc else {}))

# ============================================================== 5 principles
s, tl = new(1, "五条设计原则", "设计原则", notes="五条原则贯穿所有设计。\n\n来源：README · docs/design/action-model-routing.md")
for i, (p, d) in enumerate([("预算是一等公民", "请求数、候选数、研究时长由程序硬约束，耗尽即停"),
                            ("模型不自评", "正确性与性能只由外部裁判实测，判定由程序给出"),
                            ("经验必须可执行", "保存已验证的完整程序与它成立的输入条件"),
                            ("每一笔都记账", "角色、Token、延迟、费用逐次落账，未知记为 null"),
                            ("任何进化都可回退", "经验以不可变快照原子发布，切换留审计记录")]):
    y = 300 + i * 136
    g = [T(s, L, y, 120, 100, f"0{i + 1}", size=38, bold=True, color=BLUE, latin=NUM, anchor="m"),
         T(s, L + 140, y, 520, 100, p, size=27, bold=True, anchor="m"),
         T(s, L + 700, y, 1068, 100, d, size=19, color=INK2, anchor="m")]
    ln = line(s, L, y + 118, R, y + 118, RULE, 1)
    tl.pop(g[0], 300 + i * 220, 450)
    each(tl, g[1:], "rise", 380 + i * 220, 600, 80, off=0.02)
    tl.wipe(ln, 450 + i * 220, 600)

# ============================================================== 6 architecture
s, tl = new(1, "系统架构", "系统架构",
            notes="一次运行的完整路径：先复验经验里最接近的已验证程序；不达标再由分流器决定从哪个模型开始；进入受预算约束的研究循环；动作路由和模型路由分别决定做什么、由谁做；所有候选进隔离沙箱实测；冻结最佳候选做一次隐藏测试；最后导出报告并发布新快照。\n\n来源：README「系统架构与研究闭环」 · backend/src/quotacrux/agent/{runner,routing}.py")
d = 300
each(tl, box(s, L, 340, 280, 100, "冻结任务包", "契约 · c0 · 开发 / final"), "pop", d, 450)
each(tl, box(s, L, 500, 280, 100, "经验快照 vN", "不可变 · 已验证程序"), "pop", d + 120, 450)
tl.wipe(arrow(s, 356, 390, 430, 450), d + 400, 300).wipe(arrow(s, 356, 550, 430, 485), d + 400, 300)
each(tl, box(s, 430, 410, 300, 110, "模型前复验", "≤ 3 个最相近程序"), "pop", d + 600, 450)
tl.wipe(arrow(s, 580, 520, 580, 620), d + 900, 300, direction="up").fade(T(s, 594, 550, 120, 40, "未达标", size=14, color=INK2), d + 950, 400)
each(tl, box(s, 430, 620, 300, 110, "经验覆盖分流器", "相近 → 小 · 新族 → 大", hot=True), "pop", d + 1100, 450)
tl.wipe(arrow(s, 730, 675, 800, 675), d + 1400, 300)
cont = shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 800, 300, 820, 620, None, line=ORANGE, line_w=2, dash="dash", adj=[0.04])
ct = T(s, 830, 312, 500, 40, "受预算约束的研究循环", size=17, bold=True, color=ORANGE)
cb = T(s, 1200, 312, 400, 40, "360 s · 20 次请求 · 10 个候选", size=13, color=INK2, align="r")
tl.zoom(cont, d + 1500, 600).fade(ct, d + 1700, 400).fade(cb, d + 1700, 400)
dl = d + 1900
for k, (args, hot) in enumerate([((840, 370, 320, 100, "可见状态", "契约 · 候选 · 裁判事实"), False), ((1220, 370, 320, 100, "ActionRouter", "llm | decisions"), True),
                                 ((1220, 550, 320, 100, "ModelRouter", "rule | decisions"), True), ((840, 550, 320, 100, "生成", "Qwen · gpt-6.1-sol"), False),
                                 ((840, 730, 320, 100, "静态检查", "动作参数 · 允许范围"), False), ((1220, 730, 320, 100, "隔离沙箱裁判", "正确性 · 用例 · 计时"), True)]):
    each(tl, box(s, *args, hot=hot), "pop", dl + k * 220, 400)
for k, (a, b_, c, d2, dr) in enumerate([(1160, 420, 1220, 420, "left"), (1380, 470, 1380, 550, "up"), (1220, 600, 1160, 600, "right"), (1000, 650, 1000, 730, "up"), (1160, 780, 1220, 780, "left")]):
    tl.wipe(arrow(s, a, b_, c, d2), dl + 150 + k * 220, 250, direction=dr)
tl.fade(T(s, 1190, 492, 176, 36, "分析 / 提出候选", size=13, color=INK2, align="r"), dl + 400, 400)
byp = [line(s, 1540, 420, 1580, 420, INK2, 2), line(s, 1580, 420, 1580, 780, INK2, 2), arrow(s, 1580, 780, 1540, 780)]
each(tl, byp, "fade", dl + 1400, 400)
tl.fade(T(s, 1586, 500, 34, 220, list("取证复验结束"), size=12, color=INK2, align="c", spacing=1.0), dl + 1400, 400)
fbk = [line(s, 1380, 830, 1380, 866, ORANGE, 2, dash="dash"), line(s, 1380, 866, 822, 866, ORANGE, 2, dash="dash"),
       line(s, 822, 866, 822, 420, ORANGE, 2, dash="dash"), arrow(s, 822, 420, 840, 420, ORANGE, 2)]
each(tl, fbk, "fade", dl + 1600, 400)
tl.fade(T(s, 840, 874, 420, 36, "仅严格优于当前最佳才更新", size=13, color=ORANGE), dl + 1700, 400)
dl2 = dl + 1900
for k, (y, t_, sb, hot) in enumerate([(340, "冻结最佳", "隐藏 final 一次", False), (520, "报告 · 账本", "复现包", False), (700, "快照 vN+1", "原子发布", True)]):
    each(tl, box(s, 1660, y, 184, 110, t_, sb, hot=hot, ts=16), "pop", dl2 + k * 220, 400)
tl.wipe(arrow(s, 1620, 395, 1660, 395), dl2 - 100, 250).wipe(arrow(s, 1752, 450, 1752, 520), dl2 + 150, 250, direction="up").wipe(arrow(s, 1752, 630, 1752, 700), dl2 + 370, 250, direction="up")
top = [line(s, 580, 410, 580, 280, MUTE, 2, dash="dash"), line(s, 580, 280, 1752, 280, MUTE, 2, dash="dash"), arrow(s, 1752, 280, 1752, 340, MUTE, 2, dash="dash")]
each(tl, top, "fade", dl2 + 700, 400)
tl.fade(T(s, 900, 242, 560, 36, "复验达标 → 直接交付，不调用模型", size=14, color=INK2, align="c"), dl2 + 750, 400)
lrn = [line(s, 1752, 810, 1752, 970, ORANGE, 2, dash="dash"), line(s, 1752, 970, 216, 970, ORANGE, 2, dash="dash"), arrow(s, 216, 970, 216, 600, ORANGE, 2, dash="dash")]
each(tl, lrn, "fade", dl2 + 900, 400)
tl.fade(T(s, 560, 980, 800, 36, "learn / online 模式：程序提取已验证事实，写回经验", size=14, color=ORANGE, align="c"), dl2 + 950, 400)

# ============================================================== 7 loop table
s, tl = new(1, hi("研究闭环：每一步", ("谁负责",)), "研究闭环",
            notes="研究闭环的每一步，模型做什么、程序做什么，分得很清楚。模型只负责提出想法和代码；检查、执行、判定、升级、记账都由程序完成。\n\n来源：docs/presentation/project-overview.md · docs/design/action-model-routing.md")
rows = [["环节", "模型做什么", "程序做什么"],
        ["规划", "用“分析”写下计划", "研究问题、基线、允许修改范围、工具、预算在运行前固定"],
        ["取证", "决定是否需要证据", "沙箱内对候选做 cProfile；返回状态、指标、失败类别与公开反例"],
        ["假设", "写目的、假设、预期与验证方法", "静态检查动作参数与允许范围；假设一律标为“未验证”"],
        ["实验", "生成候选代码", "隔离容器中由固定评测器检查正确性、规则用例，并交替计时"],
        ["修正", "读取判定与反例，提出下一版", "判定支持 / 部分支持 / 反驳 / 未能检验；按规则升级模型"],
        ["分流", "—", "按经验覆盖决定从小模型还是大模型开始"],
        ["交付", "—", "冻结最佳候选，隐藏数据上独立测试一次；导出记录与复核脚本"]]
hd, body, band = table(s, L, 300, [200, 520, 1048], rows, rh=84, size=17, hot_col=2)
tl.wipe(band, 300, 800, direction="down")
each(tl, hd, "fade", 300, 400)
for i, g in enumerate(body):
    each(tl, g, "rise", 500 + i * 160, 500, 0, off=0.015)

# ============================================================== 8 action x model
s, tl = new(1, hi("“做什么”和“谁来做”是", ("两个决策",)), "特色 ① · 动作 × 模型 解耦路由",
            notes="两个正交的决策点：ActionRouter 决定下一步做什么，ModelRouter 决定这一步由哪个模型生成。两层都可以用规则或生成模型，也可以交给专用决策模型 gpt-6-luna。右边是 ahc026 上的四组组合，同样预算。\n\n来源：docs/design/action-model-routing.md · docs/research/native-routing/20261114/RESULTS.md")
each(tl, box(s, L, 520, 220, 110, "可见状态", "证据 · 预算", ts=17), "pop", 300, 450)
tl.wipe(arrow(s, 296, 575, 330, 575), 600, 250)
each(tl, box(s, 330, 500, 280, 150, "ActionRouter", "下一步做什么", hot=True, ts=19), "pop", 750, 450)
for k, (y, a_, gen) in enumerate([(320, "analyze", True), (390, "propose_candidate", True), (680, "profile_candidate", False), (750, "run_validation", False), (820, "finish", False)]):
    tl.fade(line(s, 610, 575, 690, y + 26, BLUE if gen else MUTE, 1.5), 1100 + k * 120, 300)
    each(tl, pill(s, 690, y, 300, 52, a_, BLUE_L if gen else "#ECEAE4", BLUE if gen else INK, size=14, font=MONO), "pop", 1150 + k * 120, 400)
tl.fade(T(s, 690, 280, 300, 36, "需要生成 → 交给模型", size=13, color=BLUE, align="c", bold=True), 1300, 400)
tl.fade(T(s, 690, 636, 300, 36, "程序直接执行", size=13, color=INK2, align="c"), 1700, 400)
tl.wipe(arrow(s, 840, 442, 840, 482, BLUE), 1900, 250, direction="up")
each(tl, box(s, 690, 482, 300, 100, "ModelRouter", "small → large 单向升级", hot=True, ts=18), "pop", 2000, 450)
tl.fade(T(s, 1080, 290, 760, 36, "ahc026 · 同预算四组 · 最终得分提升", size=15, bold=True, color=MUTE), 2200, 400)
for i, (nm, v, ln_, hot) in enumerate([("LLM / rule · 基线", "+5.97%", "用时 392 秒", False), ("Decisions / rule", "+6.15%", "用时 389 秒", True),
                                       ("LLM / Decisions", "+5.84%", "用时 390 秒", False), ("双 Decisions", "+0.51%", "用时 113 秒", False)]):
    x, y = 1080 + (i % 2) * 390, 346 + (i // 2) * 270
    g = [rect(s, x, y, 370, 250, ORANGE_L if hot else CARD, radius=12, line=ORANGE if hot else RULE, line_w=2 if hot else 1.5),
         mono(s, x + 26, y + 22, 330, 36, nm, size=14, color=INK2, wrap=False),
         T(s, x + 22, y + 66, 340, 118, v, size=46, bold=True, color=ORANGE if hot else INK, latin=NUM, anchor="m"),
         T(s, x + 26, y + 192, 330, 36, ln_, size=15, color=INK2)]
    tl.rise(g[0], 2300 + i * 180, 600, off=0.03)
    each(tl, g[1:], "fade", 2450 + i * 180, 500)

# ============================================================== 9 judge
s, tl = new(1, hi("候选好不好，", ("只由裁判说了算",)), "特色 ② · 零信任外部裁判",
            notes="模型永远看不到、也改不了评测器。每个样本一个全新容器：禁网、只读、非 root、1 CPU 1 GB。性能用预热加 5 轮交替计时，要求候选的样本全部快于基线的样本，再加 1.10 倍门槛。研究结束后在隐藏数据上只测一次。\n\n来源：docs/presentation/project-overview.md 第 2 节 · backend/src/quotacrux/evaluator")
o1 = rect(s, L, 300, 800, 400, CARD, radius=14, line="#BDBAB2", line_w=1.5)
o1t = T(s, L + 24, 312, 760, 36, "宿主机 · 评测器（模型不可见、不可改）", size=16, bold=True)
o2 = shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, L + 40, 362, 720, 310, None, line=INK2, line_w=1.5, dash="dash", adj=[0.05])
o2t = T(s, L + 64, 374, 680, 34, "每个样本一个全新容器", size=15, bold=True, color=INK2)
o3 = rect(s, L + 80, 424, 640, 220, BLUE_L, radius=12, line=BLUE, line_w=2.5)
o3t = T(s, L + 104, 436, 600, 34, "候选程序（只挂载候选文件）", size=15, bold=True, color=BLUE)
tl.zoom(o1, 300, 600).fade(o1t, 500, 400).zoom(o2, 650, 500).fade(o2t, 800, 400).zoom(o3, 950, 500).fade(o3t, 1100, 400)
for i, tg in enumerate(["禁网", "只读根文件系统", "非 root", "1 CPU · 1 GB", "64 进程", "stdin 输入"]):
    each(tl, pill(s, L + 104 + (i % 3) * 200, 490 + (i // 3) * 64, 186, 48, tg, CARD, INK, size=13), "pop", 1250 + i * 110, 400)
tl.fade(T(s, L, 740, 600, 36, "预热后 5 轮交替计时", size=16, bold=True), 2000, 400)
for i in range(5):
    x = L + i * 160
    each(tl, pill(s, x, 788, 70, 40, "B", "#D7D4CC", INK2, size=13, font=MONO), "pop", 2100 + i * 140, 350)
    each(tl, pill(s, x + 76, 788, 70, 40, "C", BLUE, "#FFFFFF", size=13, font=MONO), "pop", 2170 + i * 140, 350)
X = lambda ms: L + 30 + (ms - 130) / 100 * 740  # noqa: E731
tl.wipe(line(s, L, 910, L + 800, 910, RULE, 2), 2900, 500)
for k, v in enumerate([151, 148, 156, 150, 153]):
    tl.pop(oval(s, X(v + k * 2.5), 910, 11, BLUE), 3000 + k * 60, 300)
for k, v in enumerate([212, 205, 218, 209, 214]):
    tl.pop(oval(s, X(v), 910, 11, "#A9A69E"), 3000 + k * 60, 300)
tl.fade(T(s, X(152) - 120, 858, 240, 34, "候选更快", size=14, color=BLUE, align="c", bold=True), 3400, 400)
tl.fade(T(s, X(212) - 120, 858, 240, 34, "基线", size=14, color=INK2, align="c"), 3400, 400)
for i, (t_, d_) in enumerate([("静态检查", "动作参数、允许修改范围"), ("开发集正确性", "输出逐项比对，参考输出只留在宿主机"),
                              ("公开规则用例", "每个任务族 7 个边界用例"), ("预热 + 5 轮交替计时", "基线与候选交替测量，抵消机器漂移"),
                              ("严格判定", "候选样本全部快于基线，且 ≥ 1.10×"), ("隐藏 final 只测一次", "冻结开发最佳候选，结果不回流")]):
    y = 300 + i * 110
    g = [T(s, 960, y, 80, 90, f"0{i + 1}", size=26, bold=True, color=ORANGE, latin=NUM, anchor="m"),
         T(s, 1050, y + 6, 790, 42, t_, size=20, bold=True), T(s, 1050, y + 50, 790, 40, d_, size=15, color=INK2)]
    tl.pop(g[0], 400 + i * 200, 400)
    each(tl, g[1:], "rise", 450 + i * 200, 500, 60, off=0.02)
    tl.wipe(line(s, 960, y + 102, R, y + 102, RULE, 1), 500 + i * 200, 500)

# ============================================================== 10 hypothesis
s, tl = new(1, hi("每个候选都是", ("一次实验",)), "特色 ③ · 假设—判定",
            notes="每个候选提交前必须写假设；评测后由程序判定。262 次正式运行一共 536 个实验。下面是一条真实的修正链：c1 被反驳，c2 格式错误未能检验，触发升级，大模型读到具体反馈后做出 1.45 倍。\n\n来源：docs/presentation/project-overview.md 第 5.4 节 · docs/research/ 样例 A-01")
cbx = rect(s, L, 300, 820, 400, CARD, radius=12, line=RULE, line_w=1.5)
c1 = mono(s, L + 30, 322, 770, 190, ["# 提交时由模型填写", "purpose:     减少逐行解析开销", "hypothesis:  批量 split 比 csv 更快", "expected:    加速比 ≥ 1.3×"], size=15, spacing=1.15)
c2 = mono(s, L + 30, 530, 770, 150, ["# 评测后由程序写入", "verdict:     supported | partial", "             refuted | untestable"], size=15, spacing=1.15, color=BLUE)
tl.rise(cbx, 300, 600, off=0.03).wipe(c1, 600, 700, direction="up").wipe(c2, 1200, 600, direction="up")
vrows = [["判定", "条件"], [("支持", {"color": BLUE}), "正确、有改善且达标"], [("部分支持", {"color": BLUE}), "正确、有改善但未达标"], ["反驳", "正确但没有改善"], ["未能检验", "候选出错，无法检验"]]
hd, body, _ = table(s, L, 730, [240, 580], vrows, rh=54, size=16)
each(tl, hd, "fade", 1600, 400)
for i, g in enumerate(body):
    each(tl, g, "rise", 1700 + i * 120, 450, 0, off=0.015)
tl.fade(T(s, 960, 300, 884, 36, "262 次正式运行 · 536 个实验", size=15, bold=True, color=MUTE), 400, 400)
x = 960
for k, (nm, v, c) in enumerate([("支持", 371, BLUE), ("部分支持", 36, BLUE_M), ("反驳", 100, GREY_BAR), ("未能检验", 29, "#6E6C67")]):
    w = v / 536 * 884
    tl.wipe(rect(s, x, 350, w - 3, 64, c), 600 + k * 250, 400 if k else 900)
    x += w
for i, (nm, v, c) in enumerate([("支持", "371", BLUE), ("部分支持", "36", BLUE_M), ("反驳", "100", GREY_BAR), ("未能检验", "29", "#6E6C67")]):
    xx = 960 + i * 221
    g = [rect(s, xx, 442, 16, 16, c), T(s, xx + 26, 432, 190, 36, nm, size=15, color=INK2),
         T(s, xx, 470, 210, 76, [[(v, {}), (" 个", {"size": 16, "bold": False, "color": INK2})]], size=34, bold=True, color=BLUE if i == 0 else INK, latin=NUM, anchor="m", wrap=False)]
    each(tl, g, "pop", 1500 + i * 150, 400)
tl.fade(T(s, 960, 590, 884, 36, "一条真实的修正链 · 任务 A-01", size=15, bold=True, color=MUTE), 2100, 400)
for i, (cid, v, verdict, who, kind) in enumerate([("c1", "0.90×", "反驳", "Qwen", "n"), ("c2", "格式错误", "未能检验", "Qwen", "n"), ("升级", "", "", "rule", "up"), ("c3", "1.45×", "支持", "GPT", "hot")]):
    xx, dd = 960 + i * 226, 2250 + i * 300
    if kind == "up":
        g = [shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, xx, 640, 196, 200, ORANGE_L, line=ORANGE, line_w=2, dash="dash", adj=[0.08]),
             T(s, xx + 6, 640, 184, 200, [[("↑ 升级", {"size": 18, "bold": True, "color": ORANGE})], [("大模型接手", {"size": 14, "color": INK2})], [("读取具体反馈", {"size": 14, "color": INK2})]],
               size=14, align="c", anchor="m", spacing=1.3, wrap=False)]
    else:
        g = [rect(s, xx, 640, 196, 200, BLUE_L if kind == "hot" else CARD, radius=10, line=BLUE if kind == "hot" else RULE, line_w=2 if kind == "hot" else 1.5),
             mono(s, xx + 18, 656, 170, 32, f"{cid} · {who}", size=14, color=INK2, anchor="m", wrap=False),
             T(s, xx + 16, 696, 172, 76, v, size=20 if v == "格式错误" else 32, bold=True, color=BLUE if kind == "hot" else INK, latin=NUM, anchor="m", wrap=False),
             T(s, xx + 18, 792, 170, 32, ("加速比 · " if v != "格式错误" else "") + verdict, size=13, color=BLUE if kind == "hot" else INK2, bold=kind == "hot", anchor="m")]
    tl.rise(g[0], dd, 500, off=0.03)
    each(tl, g[1:], "fade", dd + 150, 400)
    if i < 3:
        tl.wipe(arrow(s, xx + 198, 740, xx + 224, 740, ORANGE if i == 2 else INK2), dd + 250, 200)

# ============================================================== 11 snapshots + triage
s, tl = new(1, hi("存", ("可运行的程序",), "，再按经验覆盖", ("分流",)), "特色 ④⑤ · 可执行经验快照 · 经验覆盖分流器",
            notes="经验由程序从评测记录中提取：完整代码、输入条件特征、实测结果，成功、无收益、失败三态都存。快照不可变，可回退。复验没达标时，分流器按经验覆盖决定从哪个模型开始：有相近的成功经验，先用便宜的本地小模型；全新任务族或新条件，直接交给大模型。\n\n来源：docs/archive/memory-learning-results.md · router-v1 · T 任务对照")
tl.fade(T(s, L, 300, 820, 44, "可执行经验快照", size=21, bold=True, color=BLUE), 300, 400)
nodes = [(140, 460, "v0", False, 500), (400, 460, "v19", True, 900), (660, 460, "v…", True, 1300)]
tl.wipe(line(s, 174, 460, 366, 460, BLUE, 3), 650, 400).wipe(line(s, 434, 460, 626, 460, BLUE, 3), 1050, 400)
for cx, cy, lb, filled, dd in nodes:
    tl.pop(oval(s, cx, cy, 34, BLUE if filled else CARD, line=BLUE if filled else MUTE, line_w=2.5), dd, 400)
    tl.pop(mono(s, cx - 40, cy - 18, 80, 36, lb, size=14, bold=True, color="#FFFFFF" if filled else INK, align="c", anchor="m"), dd, 400)
tl.fade(T(s, 190, 500, 200, 34, "A 批学习两轮", size=14, color=BLUE, align="c"), 750, 400)
tl.fade(T(s, 450, 500, 200, 34, "S 在线任务流", size=14, color=BLUE, align="c"), 1150, 400)
for i, (n_, d_) in enumerate([("59", "v19 经验条数"), ("21", "可复验的不同程序"), ("5 项", "每族输入条件特征")]):
    x = L + i * 280
    g = [T(s, x, 560, 260, 76, n_, size=38, bold=True, color=BLUE, latin=NUM), T(s, x, 640, 260, 40, d_, size=15, color=INK2)]
    tl.pop(g[0], 1500 + i * 150, 400).fade(g[1], 1550 + i * 150, 400)
for i, (k_, v) in enumerate([("先复验", "调用模型前，复验最接近的 ≤ 3 个程序"), ("避前科", "失败记录更接近当前条件时跳过"), ("可回退", "只移动默认指针，快照本身不变")]):
    y = 720 + i * 72
    g = [T(s, L, y, 150, 56, k_, size=16, bold=True, color=BLUE, anchor="m"), T(s, L + 160, y, 660, 56, v, size=16, color=INK2, anchor="m")]
    each(tl, g, "rise", 2000 + i * 150, 500, 0, off=0.02)
    tl.wipe(line(s, L, y + 64, L + 820, y + 64, RULE, 1), 2050 + i * 150, 400)
tl.fade(line(s, 960, 300, 960, 980, RULE, 1.5), 300, 400)
tl.fade(T(s, 1000, 300, 840, 44, "经验覆盖分流器", size=21, bold=True, color=BLUE), 2400, 400)
each(tl, box(s, 1000, 362, 300, 80, "复验达标？", ts=17), "pop", 2500, 400)
tl.wipe(arrow(s, 1300, 402, 1380, 402, BLUE), 2700, 250).fade(T(s, 1310, 362, 60, 34, "是", size=14, color=BLUE, align="c"), 2700, 300)
each(tl, box(s, 1380, 362, 260, 80, "直接交付", "0 次模型调用", hot=True, ts=16, ss=12), "pop", 2800, 400)
tl.wipe(arrow(s, 1150, 442, 1150, 494), 2950, 250, direction="up").fade(T(s, 1162, 448, 60, 34, "否", size=14, color=INK2), 2950, 300)
each(tl, box(s, 1000, 494, 300, 90, "经验覆盖如何？", "同族记录 · 匹配 ≥ 3/5", ts=17, ss=12), "pop", 3050, 400)
for i, (k_, a_, hot) in enumerate([("相近成功", "先用本地小模型", False), ("全新任务族", "直接交给大模型", True), ("新条件", "直接交给大模型", True)]):
    x = 1000 + i * 284
    tl.fade(arrow(s, 1150, 584, x + 130, 624, BLUE if hot else INK2, 1.5), 3250 + i * 150, 300)
    g = card2(s, x, 624, 260, 100, k_, a_, hot=hot, ks=14, vs=16)
    each(tl, g, "pop", 3300 + i * 150, 400)
trows = [["新任务族 · 4 任务 × 3 次", "先用 Qwen", "直接 GPT"], ["达标", "12/12", "12/12"], ["加速比中位数", "2.11×", ("2.18×", B_)], ["循环时长中位数", "49 s", ("33 s", B_)]]
hd, body, _ = table(s, 1000, 756, [380, 220, 244], trows, rh=54, size=16, aligns=["l", "r", "r"])
each(tl, hd, "fade", 3800, 400)
for i, g in enumerate(body):
    each(tl, g, "rise", 3900 + i * 120, 400, 0, off=0.015)

# ============================================================== 12 ledger
s, tl = new(1, hi("每一笔都记账，", ("每个结论都能复现",)), "特色 ⑥ · 资源账本与复现包",
            notes="每次模型调用都记账，未知用量记 null。研究结束可以一键导出复现包，里面有 reproduce.sh。三个样例在最终数据上的复核结果与记录值吻合。本地 Qwen 记无 API 费用。\n\n来源：docs/presentation/project-overview.md 第 6 节 · quotacrux export-run")
tl.fade(T(s, L, 300, 820, 36, "每次模型调用记录", size=15, bold=True, color=MUTE), 300, 400)
for i, (k_, v) in enumerate([("provider / model", "openai · gpt-6.1-sol"), ("role / reasoning", "large · xhigh"), ("tokens", "输入 · 缓存 · 输出 · 推理"),
                             ("latency / request_id", "延迟与服务方请求号"), ("price_table", "2026-11-13 价表版本"), ("cost", "缺用量记 null，不写 0")]):
    y = 350 + i * 86
    g = [mono(s, L, y, 360, 66, k_, size=15, color=BLUE, anchor="m"), T(s, L + 370, y, 450, 66, v, size=17, anchor="m", bold=(i == 5), color=ORANGE if i == 5 else INK)]
    each(tl, g, "rise", 400 + i * 150, 500, 0, off=0.015)
    tl.wipe(line(s, L, y + 76, L + 820, y + 76, RULE, 1), 450 + i * 150, 400)
tl.fade(T(s, 980, 300, 860, 36, "quotacrux export-run --bundle", size=15, bold=True, color=MUTE, font=MONO, latin=MONO), 1200, 400)
bx = rect(s, 980, 350, 864, 320, CARD, radius=12, line=RULE, line_w=1.5)
bt = mono(s, 1010, 368, 820, 300, ["bundle/", "├── README.md       # 研究记录", "├── best.py         # 最佳程序", "├── candidates/     # 全部候选", "├── model_calls/    # 原始模型调用",
                                    "├── report.json     # 结构化报告", "└── reproduce.sh    # 一键复核"], size=15, spacing=1.1)
tl.rise(bx, 1300, 600, off=0.03).wipe(bt, 1500, 900, direction="up")
rrows = [["样例", "记录加速比", "复核加速比"], ["v1 · A-01", "1.4367×", ("1.44×", B_)], ["v2 · D-01", "1.4481×", ("1.4473×", B_)], ["v3 · S-01 新任务族", "6.35×", ("6.69×", B_)]]
hd, body, _ = table(s, 980, 710, [400, 232, 232], rrows, rh=62, size=17, aligns=["l", "r", "r"])
each(tl, hd, "fade", 2300, 400)
for i, g in enumerate(body):
    each(tl, g, "rise", 2400 + i * 160, 450, 0, off=0.015)

# ============================================================== 13 ahc026
s, tl = new(2, hi("测试难题：", ("搬箱子",)), "实测 · ALE-Bench ahc026",
            notes="测试难题是 AtCoder 启发式竞赛第 26 题：200 个箱子分在 10 堆，按编号顺序搬出。搬一摞 k 个箱子耗 k+1 份力气。初始程序的真实操作里，第一步就把 19 个箱子压在了箱子 8 上，后面要为此再付 29 份力气。\n\n来源：ALE-Bench ahc026 题面 · video/data/make_replay.py")
im1 = pic(s, A("still-warehouse.png"), L - 20, 300, 820, 537)
for i, (k_, v) in enumerate([("规模", "200 个箱子 · 10 堆 · 每堆 20"), ("目标", "按 1、2、3… 的顺序搬出仓库"), ("搬动", "搬走一摞 k 个箱子，耗 k+1 份力气"), ("搬出", "最小编号的箱子在顶上时搬出，不耗力气"), ("得分", "10000 − 总能耗，越省越高")]):
    y = 300 + i * 100
    g = [T(s, 900, y, 120, 84, k_, size=18, bold=True, color=BLUE, anchor="m"), T(s, 1020, y, 824, 84, v, size=20, anchor="m")]
    each(tl, g, "rise", 700 + i * 160, 500, 0, off=0.02)
    tl.wipe(line(s, 900, y + 92, R, y + 92, RULE, 1), 750 + i * 160, 400)
cl = rect(s, 900, 820, 944, 140, ORANGE_L, radius=10)
ct = T(s, 930, 820, 890, 140, [[("一步放错，后面就要多付代价：", {"bold": True}), ("初始程序第一步把 19 个箱子压在箱子 8 上，之后为此再付 ", {}), ("29", {"color": ORANGE, "bold": True}), (" 份力气。", {})]], size=17, anchor="m", spacing=1.3)
tl.wipe(cl, 1700, 600).fade(ct, 1900, 600)

# ============================================================== 14 step chart
s, tl = new(2, hi("360 秒里的 ", ("7 个候选",)), "实测 · 一轮研究的全过程",
            notes="这是一轮真实研究，横轴是已用时间，纵轴是开发集得分。小模型两次交了同一份代码，分数不动；按规则升级到大模型；大模型学会分段规划，一下涨 2,386；局部搜索再上一步；c5 改坏了被裁判拦下；最后复用相同后缀，拿到这一轮最高 46,849。预算 360 秒 · 20 次请求 · 10 个候选。\n\n来源：docs/research/native-routing/20261114/short-results/run-20261114T085616-894b · 研究报告第 5 节")
x0, x1, y0, y1, lo, hi_ = 260, 1740, 300, 900, 43500, 47200
X = lambda t: x0 + t / 360 * (x1 - x0)  # noqa: E731
Y = lambda v: y1 - (v - lo) / (hi_ - lo) * (y1 - y0)  # noqa: E731
axes = []
for v in [44000, 45000, 46000, 47000]:
    axes += [line(s, x0, Y(v), x1, Y(v), RULE, 1), T(s, x0 - 180, Y(v) - 20, 160, 40, f"{v:,}", size=14, color=MUTE, align="r", anchor="m")]
for t_ in [0, 60, 120, 180, 240, 300]:
    axes.append(T(s, X(t_) - 60, y1 + 14, 120, 36, f"{t_}s", size=14, color=MUTE, align="c", font=MONO, latin=MONO))
axes += [line(s, x0, y1, x1, y1, INK, 2), line(s, X(360), y0, X(360), y1, INK, 2, dash="dash"), T(s, X(360) - 120, y1 + 14, 240, 36, "360s 预算", size=14, bold=True, align="c")]
axes += [T(s, x0 - 180, y0 - 50, 300, 36, "开发集得分（分）", size=14, bold=True, color=INK2), T(s, x1 - 300, y1 + 52, 300, 36, "已用研究时间", size=14, bold=True, color=INK2, align="r")]
each(tl, axes, "fade", 300, 500)
C = [(12.851, 44120, "s"), (22.792, 44120, "s"), (94.286, 46506, "l"), (178.438, 46798, "l"), (244.796, 46725, "x"), (311.463, 46800, "l"), (357.026, 46849, "l")]
TIMES = [700, 1100, 2500, 3300, 3900, 4500, 5000]  # when each candidate appears
best, prev = None, None
for (t_, v, m), at in zip(C, TIMES):
    if m == "x":
        continue
    cx = X(t_)
    if best is not None:
        tl.wipe(line(s, prev, Y(best), cx, Y(best), BLUE, 5), at - 450, 400)
        if v > best:
            tl.wipe(line(s, cx, Y(best), cx, Y(v), BLUE, 5), at - 60, 300, direction="down")
    best, prev = max(best or 0, v), cx
tl.wipe(line(s, prev, Y(best), X(360), Y(best), BLUE, 5), 5300, 300)
for (t_, v, m), at in zip(C, TIMES):
    cx, cy = X(t_), Y(v)
    if m == "x":
        tl.pop(oval(s, cx, cy, 16, CARD, line=ORANGE, line_w=3), at, 400)
        tl.pop(line(s, cx - 7, cy - 7, cx + 7, cy + 7, ORANGE, 3), at, 400)
        tl.pop(line(s, cx - 7, cy + 7, cx + 7, cy - 7, ORANGE, 3), at, 400)
    else:
        tl.pop(oval(s, cx, cy, 13, "#A9A69E" if m == "s" else BLUE, line=BG, line_w=3), at, 400)
tl.fade(T(s, X(0) + 20, Y(44120) - 88, 420, 40, "c1 · c2  同一份代码", size=17, bold=True), 1300, 400)
tl.fade(T(s, X(0) + 20, Y(44120) - 50, 420, 36, "44,120 分", size=15, color=INK2, latin=NUM), 1300, 400)
tl.wipe(line(s, X(26), y0, X(26), y1, ORANGE, 3, dash="dash"), 1600, 600, direction="up")
tl.fade(T(s, X(26) + 18, Y(46200), 440, 92, [[("连续两次没进步", {})], [("→ 按规则升级大模型", {"color": ORANGE})]], size=18, bold=True), 1900, 500)
tl.pop(T(s, X(108), Y(45300), 700, 150, [[("+2,386", {}), (" 分", {"size": 28})]], size=64, bold=True, color=ORANGE, latin=NUM, anchor="m", wrap=False), 2700, 600)
tl.fade(T(s, X(94.286) - 230, Y(46506) - 56, 460, 40, "分段规划 · 46,506 分", size=16, bold=True, align="c"), 2600, 400)
tl.fade(T(s, X(178.438) - 230, Y(46798) - 56, 460, 40, "局部搜索 · 46,798 分", size=16, bold=True, align="c"), 3400, 400)
tl.fade(line(s, X(244.796), Y(46725) + 18, X(244.796), Y(46725) + 70, ORANGE, 1.5), 4000, 300)
tl.fade(T(s, X(244.796) - 200, Y(46725) + 72, 400, 40, "c5 下降 · 被裁判拦下", size=16, bold=True, color=ORANGE, align="c"), 4000, 400)
tl.fade(T(s, X(311.463) - 120, Y(46800) + 22, 240, 40, "46,800 分", size=16, bold=True, align="c"), 4600, 400)
tl.fade(T(s, X(357.026) - 420, Y(46849) - 58, 440, 40, "复用后缀 · 46,849 分", size=16, bold=True, align="r", color=BLUE), 5100, 400)

# ============================================================== 15 result
s, tl = new(2, hi("冻结最好的版本，", ("只测一次",)), "实测 · 隐藏测试",
            notes="冻结最好的版本，在 15 个没见过的用例上只测一次：全部通过，总能耗从 18,136 降到 10,028。右边是同一个用例、同样进度时两个程序的仓库：最终版本把不急用的箱子码成高堆，给后面要拿的箱子让路；这个用例的能耗从 1,158 降到 649。\n\n来源：研究报告 deep-analysis.json · ahc026_movement_energy · video/data/replay.json")
lb = T(s, L, 300, 640, 36, "15 个隐藏用例 · 总能耗", size=16, bold=True, color=ORANGE)
bg_ = T(s, L - 6, 340, 720, 230, "−44.7%", size=88, bold=True, color=ORANGE, latin=NUM, anchor="m")
nm = T(s, L, 590, 720, 90, [[("总能耗  ", {"size": 18, "bold": False, "color": INK2}), ("18,136", {"color": MUTE}), ("  →  ", {"color": MUTE}), ("10,028", {})]], size=30, bold=True, latin=NUM, anchor="m", wrap=False)
tl.fade(lb, 300, 400).zoom(bg_, 400, 700).rise(nm, 900, 600, off=0.02)
each(tl, pill(s, L, 720, 170, 50, "15/15 通过", BLUE, "#FFFFFF", size=15), "pop", 1300, 400)
tl.fade(T(s, L + 190, 720, 520, 50, "总分 131,864 → 139,972 分", size=18, anchor="m"), 1400, 400)
for i, (f, lab_, v, c) in enumerate([("still-c0.png", "初始程序", "1,158", INK), ("still-c7.png", "最终版本", "649", BLUE)]):
    x = 820 + i * 520
    im = pic(s, A(f), x, 290, 500, 638)
    hd_ = T(s, x, 936, 500, 50, [[(lab_ + " · 本用例总能耗  ", {"color": INK2, "size": 16}), (v, {"color": c, "bold": True, "size": 24})]], size=16, anchor="m", align="c", wrap=False)
    tl.fade(hd_, 1700 + i * 300, 500)

# ============================================================== 16 routing
s, tl = new(2, hi("谁来决定下一步，", ("同样影响结果",)), "实测 · 调度对照",
            notes="左：四组路由组合，同一预算。仅动作 Decisions 得分最高；双 Decisions 全程没升级大模型、主动提前结束，用时少七成，提升只有 0.5%。决策层费用只占 2.26%，单次决策中位 1.34 秒。右：补充实验在两台机器上各跑四种策略：固定小模型没有提升，有大模型参与的策略都在 5.4% 到 6.4%。\n\n来源：docs/research/native-routing/20261114/RESULTS.md · docs/research/onehour-20261114/README.md")
tl.fade(T(s, L, 300, 700, 36, "四组路由 · 同预算 · 最终得分提升", size=15, bold=True, color=MUTE), 300, 400)
tl.fade(T(s, 830, 300, 200, 36, "用时", size=15, bold=True, color=MUTE, align="r"), 300, 400)
for i, (nm_, k_, g_, sec) in enumerate([("LLM / rule", "基线", 5.970, 392), ("Decisions / rule", "仅动作", 6.149, 389), ("LLM / Decisions", "仅模型", 5.836, 390), ("双 Decisions", "两层都交给决策模型", 0.513, 113)]):
    y = 352 + i * 112
    w = g_ / 7 * 330
    g = [mono(s, L, y, 330, 34, nm_, size=13, bold=True, color=ORANGE if i == 1 else INK), T(s, L, y + 38, 300, 32, k_, size=14, color=MUTE)]
    each(tl, g, "fade", 500 + i * 180, 400)
    tl.wipe(rect(s, 420, y + 8, w, 48, ORANGE if i == 1 else BLUE), 600 + i * 180, 700)
    tl.fade(T(s, 430 + w, y + 6, 170, 52, f"+{g_:.2f}%", size=19, bold=True, anchor="m", color=ORANGE if i == 1 else INK), 1200 + i * 180, 400)
    tl.fade(T(s, 830, y + 6, 200, 52, f"{sec} 秒", size=19, bold=True, anchor="m", align="r", color=ORANGE if i == 3 else INK), 1200 + i * 180, 400)
for i, (v, d_) in enumerate([("2.26%", "决策层费用占比"), ("1.34 s", "单次决策耗时"), ("−71%", "双 Decisions 用时")]):
    x = L + i * 330
    tl.pop(T(s, x, 806, 320, 76, v, size=36, bold=True, color=BLUE, latin=NUM), 2000 + i * 150, 450)
    tl.fade(T(s, x, 884, 320, 40, d_, size=15, color=INK2), 2050 + i * 150, 400)
tl.fade(line(s, 1080, 300, 1080, 960, RULE, 1.5), 300, 400)
tl.fade(T(s, 1120, 300, 720, 36, "双机补充对照 · 最终得分提升", size=15, bold=True, color=MUTE), 2400, 400)
hrows = [["策略", "台式机", "笔记本"], ["固定小模型", "+0.00%", "+0.00%"], ["固定大模型", "+5.73%", "+5.50%"], ["规则自适应", ("+6.37%", B_), "+5.43%"], ["Decisions 动作", "+5.82%", ("+6.34%", B_)]]
hd, body, _ = table(s, 1120, 350, [330, 195, 199], hrows, rh=74, size=17, aligns=["l", "r", "r"])
each(tl, hd, "fade", 2500, 400)
for i, g in enumerate(body):
    each(tl, g, "rise", 2600 + i * 150, 450, 0, off=0.015)
tl.rise(T(s, 1120, 760, 724, 120, "强模型参与是提升的前提；\n混合策略接近固定大模型。", size=19, bold=True, spacing=1.35), 3300, 600, off=0.02)

# ============================================================== 17 memory
s, tl = new(2, hi("同样的模型，", ("换上经验快照",), "之后"), "实测 · 经验记忆",
            notes="经验记忆的两组受控对照：D 是封存留出集，v19 快照让 18 次运行全部零模型调用直接交付，加速比中位数从 1.20 到 1.73（v19 来自两轮 A 批学习，学习费用另计 $0.455）。S 是在线任务流，新任务族第一次出现时交给大模型，之后同类任务全部复用，大模型请求从 27 降到 6。\n\n来源：docs/archive/memory-learning-results.md · README 核心实测成果第 3 节")
mrows = [["指标", "D 封存留出 · v0 → v19", "S 在线任务流 · 无记忆 → 带记忆"],
         ["达标 / 运行", [[("15/18 → ", {}), ("18/18", B_)]], "36/36 → 36/36"],
         ["最终加速比中位数", [[("1.20× → ", {}), ("1.73×", B_)]], "1.86× → 1.86×"],
         ["大模型（GPT）请求", [[("7 → ", {}), ("0", B_)]], [[("27 → ", {}), ("6", B_)]]],
         ["零模型调用的运行", [[("0/18 → ", {}), ("18/18", B_)]], [[("9/36 → ", {}), ("30/36", B_)]]],
         ["模型费用（估算）", [[("$0.376 → ", {}), ("$0.000", B_)]], [[("$0.402 → ", {}), ("$0.086", B_)]]],
         ["总耗时", [[("1782 s → ", {}), ("669 s", B_)]], [[("1486 s → ", {}), ("1064 s", B_)]]]]
hd, body, _ = table(s, L, 310, [520, 624, 624], mrows, rh=90, size=21)
each(tl, hd, "fade", 300, 400)
for i, g in enumerate(body):
    each(tl, g, "rise", 450 + i * 180, 500, 0, off=0.015)

# ============================================================== 18 evolution
s, tl = new(2, hi("用同样的严格对照，", ("改进系统本身",)), "实测 · 系统研究自己",
            notes="我们用同样的严格对照来改进系统本身。v1 发现文字经验让加速比变低；v2 改存可执行程序并先复验；v3 加上分流器和在线记忆；最后把同一套闭环接到外部基准上。每一版都先封存新的留出集，再动手实现。\n\n来源：docs/archive/memory-learning-results.md · docs/research/README.md")
tl.wipe(line(s, L, 390, R, 390, RULE, 3), 300, 1200)
for i, (v, h, a_, b_) in enumerate([("v1", "只存文字经验", "更省，但留出集加速比 1.41× → 1.29×；好程序被小模型重写一遍", "诊断：达标即停，经验不能直接运行"),
                                    ("v2", "可执行经验", "D 封存留出：15/18 → 18/18，1.20× → 1.73×，零模型调用", "学习运行以已知最佳为起点继续超越"),
                                    ("v3", "分流 · 在线记忆", "S 任务流：GPT 请求 27 → 6，后续 30/30 零调用", "新任务族直接交给大模型，之后复用"),
                                    ("native", "外部基准 · 路由", "ahc026 −44.7% · PageRank 25.0× · 四组路由对照", "动作 × 模型解耦，决策开销单独记账")]):
    x, hot, dd = L + i * 450, i == 3, 500 + i * 400
    g0 = [T(s, x, 306, 400, 50, v, size=24, bold=True, color=ORANGE, font=MONO, latin=MONO), oval(s, x + 14, 390, 14, BLUE if hot else BG, line=BLUE, line_w=4)]
    each(tl, g0, "pop", dd, 400)
    g = [rect(s, x, 440, 420, 470, BLUE_L if hot else CARD, radius=12, line=BLUE if hot else RULE, line_w=2 if hot else 1.5),
         T(s, x + 28, 466, 370, 50, h, size=20, bold=True, color=BLUE if hot else INK),
         T(s, x + 28, 536, 370, 170, a_, size=17, color=INK2, spacing=1.35),
         line(s, x + 28, 726, x + 392, 726, RULE, 1.5, dash="dash"),
         T(s, x + 28, 742, 370, 140, "→ " + b_, size=17, bold=True, color=BLUE, spacing=1.3)]
    tl.rise(g[0], dd + 100, 600, off=0.03)
    each(tl, g[1:], "fade", dd + 300, 400, 80)

# ============================================================== 19 algotune + benchmarks
s, tl = new(2, hi("同一套闭环，", ("换一个优化对象",)), "实测 · 函数级优化与支持的基准",
            notes="同一套闭环也能做函数级优化：PageRank 绕过 NetworkX 图对象，直接用 SciPy 稀疏矩阵做幂迭代，快了 25 倍；一维卷积在误差容限内改用 float32 实数 FFT，快了 2.67 倍。固定 gpt-6.1-sol，每项 180 秒 / 5 次请求。右边是通过任务与评测 adapter 接入的五类基准。\n\n来源：README 核心实测成果第 2 节 · README「支持的 Benchmark 与任务族」")
tl.fade(T(s, L, 300, 840, 36, "AlgoTune · 相对参考实现的提速倍数", size=15, bold=True, color=MUTE), 300, 400)
for i, (t_, st_, v, how) in enumerate([("PageRank", "feedback", 25.04, "稀疏矩阵直接幂迭代"), ("PageRank", "independent", 23.05, "邻接表直接建稀疏表示"),
                                       ("一维卷积", "independent", 2.67, "float32 实数 FFT"), ("一维卷积", "feedback", 1.30, "实数 FFT 批处理")]):
    y = 356 + i * 145
    w = v / 26 * 470
    g = [T(s, L, y, 200, 38, t_, size=18, bold=True), mono(s, L, y + 40, 200, 30, st_, size=13, color=MUTE)]
    each(tl, g, "fade", 500 + i * 200, 400)
    tl.wipe(rect(s, 290, y + 6, max(w, 6), 50, ORANGE if i == 0 else BLUE), 600 + i * 200, 800)
    tl.fade(T(s, 300 + max(w, 6), y + 2, 170, 58, f"{v:.2f}×", size=21, bold=True, anchor="m", color=ORANGE if i == 0 else INK), 1300 + i * 200, 400)
    tl.fade(T(s, 290, y + 66, 600, 36, how, size=15, color=INK2), 1350 + i * 200, 400)
tl.fade(line(s, 960, 300, 960, 980, RULE, 1.5), 300, 400)
tl.fade(T(s, 1000, 300, 840, 36, "五类基准 · 各有独立裁判", size=15, bold=True, color=MUTE), 2000, 400)
for i, (n_, scope, judge) in enumerate([("自建任务族", "分组聚合 · 访问日志 · 区间合并", "Docker 沙箱 · 规则用例 · 交替计时"),
                                        ("ALE-Bench", "AtCoder 启发式 ahc024、ahc026", "上游 Rust vis 裁判"),
                                        ("AlgoTune", "convolve_1d、pagerank", "is_solution 校验 + 配对计时"),
                                        ("EffiBench-X", "623 道 Python 题", "独立容器校验"),
                                        ("KernelBench", "Level 1 方阵乘法", "远端 GPU worker · CUDA events")]):
    y = 352 + i * 124
    g = [T(s, 1000, y, 300, 40, n_, size=18, bold=True, color=BLUE), T(s, 1000, y + 42, 844, 32, scope, size=15), T(s, 1000, y + 74, 844, 30, judge, size=13, color=INK2)]
    each(tl, g, "rise", 2100 + i * 160, 500, 50, off=0.02)
    tl.wipe(line(s, 1000, y + 116, R, y + 116, RULE, 1), 2150 + i * 160, 400)

# ============================================================== 20 console
s, tl = new(3, hi("过程看得见：", ("Web 控制台",)), "控制台",
            notes="Web 控制台：总览与研究对照。每一步的假设、判定、用量和费用都能在界面上看到。启动：uv run quotacrux serve。\n\n来源：frontend/docs/screenshots")
for i, (x, f, cap) in enumerate([(L, "console-home.png", "总览：批次、轮次、候选、用量与费用"), (984, "console-research.png", "研究对照：各策略逐轮结果")]):
    w = 860
    h = w * 900 / 1440
    fr = rect(s, x - 3, 320 - 3, w + 6, h + 6, RULE, radius=6)
    im = pic(s, A(f), x, 320, w, h)
    c_ = T(s, x, 320 + h + 24, w, 44, cap, size=18, bold=True, align="c")
    tl.fade(c_, 800 + i * 400, 500)

# ============================================================== 21 advantages
s, tl = new(3, hi("同一个系统里的", ("受控对比",)), "优势对比",
            notes="对比的每一列都来自我们自己的受控实验：固定小模型、固定大模型、小模型加文字经验，以及 QuotaCrux。各列口径不同（ahc026 得分提升 / 自建任务加速比），只在各自实验内比较。\n\n来源：双机补充实验、v1 文字经验消融、S 任务流、D 留出")
arows = [["", "固定小模型", "固定大模型", "小模型 + 文字经验", "QuotaCrux"],
         ["质量", "0% 提升", "+5.5% ~ +5.7%", "1.41× → 1.29×", "+5.8% ~ +6.4% · 1.20× → 1.73×"],
         ["大模型调用", "0", "每轮 6–7 次", "升级 11 → 5 次", "S 流 27 → 6 · D 留出 7 → 0"],
         ["正确性由谁判", "外部裁判", "外部裁判", "外部裁判", "外部裁判 · 模型不自评"],
         ["经验能否直接用", "—", "—", "需要重新写一遍", "先复验已验证程序，18/18 零调用"],
         ["新问题", "原地打转", "每次都付费", "没有相近经验", "直接交给大模型，之后复用"],
         ["回退与审计", "—", "—", "—", "不可变快照 · 全量账本 · 复现包"]]
hd, body, band = table(s, L, 300, [260, 250, 290, 330, 638], arows, rh=96, size=16, hot_col=4, aligns=["l", "c", "c", "c", "c"])
each(tl, hd, "fade", 300, 400)
for i, g in enumerate(body):
    each(tl, g[:-2] + [g[-1]], "rise", 500 + i * 160, 450, 0, off=0.015)
    tl.fade(g[-2], 1600 + i * 150, 500)
tl.wipe(band, 1400, 800, direction="down")

# ============================================================== 22 summary
s, tl = new(3, notes="总结：QuotaCrux 在预算里做研究。小模型干主力，关键节点请大模型；模型只提出想法，裁判决定结果；验证过的程序沉淀为可回退的经验。欢迎扫码查看代码与报告。")
t1 = T(s, L, 160, 1300, 120, "在预算里做研究，", size=50, bold=True)
t2 = T(s, L, 280, 1300, 120, "每一步都有据可查", size=50, bold=True, color=BLUE)
ul = line(s, L, 412, L + 340, 412, ORANGE, 6)
tl.rise(t1, 200, 700, off=0.03).add(t2, "rise", 600, 500, letters=True, lt_pct=12000, off=0.03).wipe(ul, 1300, 500)
for i, (k_, v) in enumerate([("分工", "小模型干主力\n关键节点请大模型"), ("验证", "模型提出想法\n裁判决定结果"), ("进化", "验证过的程序\n沉淀为可回退快照")]):
    x = L + i * 440
    g = [T(s, x, 480, 400, 36, k_, size=16, bold=True, color=ORANGE), T(s, x, 522, 400, 120, v, size=23, bold=True, spacing=1.3)]
    each(tl, g, "rise", 1500 + i * 200, 600, 80, off=0.02)
    if i:
        tl.fade(line(s, x - 30, 480, x - 30, 650, RULE, 1.5), 1500, 400)
for i, (n_, d_) in enumerate([("−44.7%", "ahc026 隐藏测试总能耗"), ("25.0×", "PageRank 函数级提速"), ("18/18", "封存留出零调用交付")]):
    x = L + i * 440
    tl.pop(T(s, x, 720, 400, 100, n_, size=44, bold=True, color=ORANGE if i == 0 else BLUE, latin=NUM), 2300 + i * 200, 500)
    tl.fade(T(s, x, 822, 400, 40, d_, size=16, color=INK2), 2400 + i * 200, 400)
qf = rect(s, 1494, 300, 350, 350, CARD, radius=12, line=RULE, line_w=1.5)
qi = pic(s, A("qr.png"), 1519, 325, 300, 300)
qt = T(s, 1494, 668, 350, 40, "扫码查看代码与报告", size=16, color=INK2, align="c")
tl.fade(qt, 3300, 400)
tl.fade(T(s, L, 930, 1000, 44, "github.com/bohack-2026-hw/QuotaCrux", size=17, color=INK2, latin=NUM), 3300, 500)

for f in TLS[0].fx[3:]:
    f["delay"] += INTRO_MS
for t in TLS:
    t.build()
prs.core_properties.title = "QuotaCrux 枢决 · 技术演示"
prs.save(OUT)
print(f"{len(TLS)} slides -> {OUT}")
